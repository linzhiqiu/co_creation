"""
Flask Server for FLUX Batch Image Generation and Captioning
Fixed version with Server-Sent Events (SSE) to stream progress and avoid timeouts
"""
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import os
import uuid
from pathlib import Path
import traceback
from datetime import datetime
import toml
from PIL import Image
import argparse
from concurrent.futures import ThreadPoolExecutor
import time
import json

# Import our modules (same as original flux_server.py)
from flux_generator import generate_image_from_text_prompt as flux_generate
import google_imagen_generator
import llm

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'batch_outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create folders if they don't exist
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
Path(OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Load secrets
SECRETS_PATH = "llm/secrets.toml"
secrets = None

def load_secrets():
    """Load API keys from llm/secrets.toml"""
    global secrets
    if os.path.exists(SECRETS_PATH):
        try:
            secrets = toml.load(SECRETS_PATH)
            print("✓ Secrets loaded from llm/secrets.toml")
        except Exception as e:
            print(f"⚠ Warning: Could not load secrets.toml: {e}")
    else:
        print(f"⚠ Warning: {SECRETS_PATH} not found")

# Load secrets on startup
load_secrets()

# Default captioning prompt
DEFAULT_CAPTION_PROMPT = """You are given an image. Write a detailed natural language prompt that could have been used to generate this image. Focus on the most salient and unique visual elements such as the subjects, their clothing, expressions, actions, background, and composition. Describe the color palette, lighting, and overall style, including any cinematic or artistic qualities like camera angle, depth of field, or motion. Make the description as accurate and faithful to the image as possible. If small details are uncertain or ambiguous, omit them and prioritize capturing the overall scene, mood, and visual impression. The final prompt should be coherent, evocative, written as if by an expert visual artist or filmmaker recreating the exact scene."""

# Short version prompt addition
SHORT_VERSION_ADDITION = "Keep your response to at most 30 to 60 words."


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('flux_batch.html')


def generate_caption_with_model(image_path, prompt, model_name):
    """
    Generate a caption using a specific model
    Returns: (caption, model_name)
    """
    try:
        print(f"  Generating caption with {model_name}...")
        start_time = time.time()
        
        # Get LLM instance from llm module (same as original flux_server.py)
        llm_instance = llm.get_llm(model=model_name, secrets=secrets)
        
        # Generate caption using llm.generate() with images parameter
        caption = llm_instance.generate(
            prompt=prompt,
            images=[image_path],  # Pass image path in a list
            temperature=0.0
        )
        
        elapsed = time.time() - start_time
        print(f"  ✓ {model_name} completed in {elapsed:.1f}s")
        
        return (caption, model_name)
    except Exception as e:
        print(f"  ✗ Error with {model_name}: {e}")
        return (f"Error: {str(e)}", model_name)


def generate_image_with_model(prompt, model_type, width, height, seed, index):
    """
    Generate an image using a specific model
    Returns: (filename, model_type, prompt_used, index)
    """
    try:
        print(f"    Generating image {index} with {model_type}...")
        start_time = time.time()
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'batch_{timestamp}_{index}_{model_type}.png'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        
        if model_type == 'flux':
            # Generate with FLUX
            image = flux_generate(
                prompt=prompt,
                width=width,
                height=height,
                seed=seed
            )
        else:  # nano_banana
            # Generate with Nano Banana
            image = google_imagen_generator.generate_image_from_text_prompt(
                prompt=prompt,
                width=width,
                height=height,
                seed=seed
            )
        
        # Save image
        image.save(output_path)
        
        elapsed = time.time() - start_time
        print(f"    ✓ {model_type} image {index} completed in {elapsed:.1f}s")
        
        return (filename, model_type, prompt, index)
    except Exception as e:
        print(f"    ✗ Error generating image {index} with {model_type}: {e}")
        return (None, model_type, prompt, index)


def batch_generate_stream(folder, filename, caption_prompt, short_addition, width, height, seed):
    """
    Generator function that yields SSE events for streaming progress
    """
    try:
        print("\n" + "="*60)
        print("BATCH GENERATION REQUEST (STREAMING)")
        print("="*60)
        print(f"Folder: {folder}")
        print(f"Image: {filename}")
        print(f"Size: {width}x{height}")
        print(f"Seed: {seed if seed else 'random'}")
        
        # Validate folder and get image path
        if folder not in ['civitai', 'frameset']:
            yield f"data: {json.dumps({'error': 'Invalid folder name'})}\n\n"
            return
        
        image_path = Path(f'{folder}/images') / secure_filename(filename)
        
        if not image_path.exists():
            yield f"data: {json.dumps({'error': 'Image not found'})}\n\n"
            return
        
        # Send initial status
        yield f"data: {json.dumps({'status': 'starting', 'message': 'Starting batch generation...'})}\n\n"
        
        # STEP 1: Generate 4 captions
        yield f"data: {json.dumps({'status': 'captions', 'message': 'Generating 4 captions...'})}\n\n"
        
        print("\nSTEP 1: Generating 4 captions...")
        print("-" * 60)
        
        caption_models = ['gemini-2.5-pro', 'gpt-4.1-2025-04-14']
        caption_configs = [
            (caption_prompt, 'normal'),
            (f"{caption_prompt}\n\n{short_addition}", 'short')
        ]
        
        captions = []
        caption_details = []
        
        # Build list of (model, prompt, length_type) tuples to maintain order
        caption_tasks = []
        for model in caption_models:
            for prompt, length_type in caption_configs:
                caption_tasks.append((model, prompt, length_type))
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for model, prompt, length_type in caption_tasks:
                futures.append((executor.submit(generate_caption_with_model, str(image_path), prompt, model), model, length_type))
            
            for idx, (future, expected_model, length_type) in enumerate(futures, 1):
                caption, model = future.result()
                captions.append(caption)
                word_count = len(caption.split())
                
                caption_detail = {
                    'caption': caption,
                    'model': model,
                    'length_type': length_type,
                    'word_count': word_count
                }
                caption_details.append(caption_detail)
                
                # Stream caption completion
                yield f"data: {json.dumps({'status': 'caption_complete', 'caption_index': idx, 'detail': caption_detail})}\n\n"
        
        # STEP 2: Generate 16 images with progress updates
        yield f"data: {json.dumps({'status': 'images', 'message': 'Generating 16 images...', 'total': 16})}\n\n"
        
        print("\nSTEP 2: Generating 16 images...")
        print("-" * 60)
        
        results = []
        
        # Generate images SEQUENTIALLY to avoid memory issues
        # FLUX loads large model on CPU and can't run multiple instances in parallel
        image_index = 1
        
        for caption_idx, (caption, caption_detail) in enumerate(zip(captions, caption_details), 1):
            print(f"\n  Processing caption {caption_idx}/4...")
            print(f"    Model: {caption_detail['model']}, Type: {caption_detail['length_type']}")
            
            # Create caption label for display
            caption_label = f"{caption_detail['model']} ({caption_detail['length_type']})"
            
            # Generate FLUX image
            print(f"    Generating FLUX image {image_index}...")
            filename_result, model_type, prompt_used, index = generate_image_with_model(
                caption,
                'flux',
                width,
                height,
                seed,
                image_index
            )
            
            # ALWAYS add result, even if generation failed
            image_data = {
                'filename': filename_result,
                'model': model_type,
                'caption': prompt_used,
                'caption_label': caption_label,
                'index': image_index,
                'url': f'/batch_outputs/{filename_result}' if filename_result else None,
                'failed': filename_result is None
            }
            results.append(image_data)
            yield f"data: {json.dumps({'status': 'image_complete', 'image_index': len(results), 'total': 16, 'image': image_data})}\n\n"
            image_index += 1
            
            # Generate Nano Banana image
            print(f"    Generating Nano Banana image {image_index}...")
            filename_result, model_type, prompt_used, index = generate_image_with_model(
                caption,
                'nano_banana',
                width,
                height,
                seed,
                image_index
            )
            
            # ALWAYS add result, even if generation failed
            image_data = {
                'filename': filename_result,
                'model': model_type,
                'caption': prompt_used,
                'caption_label': caption_label,
                'index': image_index,
                'url': f'/batch_outputs/{filename_result}' if filename_result else None,
                'failed': filename_result is None
            }
            results.append(image_data)
            yield f"data: {json.dumps({'status': 'image_complete', 'image_index': len(results), 'total': 16, 'image': image_data})}\n\n"
            image_index += 1
        
        # Send final completion
        print(f"\n✓ Generated {len(results)} images successfully")
        print("="*60 + "\n")
        
        yield f"data: {json.dumps({'status': 'complete', 'captions': caption_details, 'images': results, 'total_images': len(results)})}\n\n"
        
    except Exception as e:
        print(f"\n✗ Error in batch generation: {str(e)}")
        traceback.print_exc()
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"


@app.route('/api/batch-generate', methods=['POST'])
def batch_generate():
    """
    Stream batch generation progress using Server-Sent Events (SSE)
    """
    try:
        data = request.get_json()
        folder = data.get('folder')
        filename = data.get('filename')
        caption_prompt = data.get('caption_prompt', DEFAULT_CAPTION_PROMPT)
        short_addition = data.get('short_addition', SHORT_VERSION_ADDITION)
        width = int(data.get('width', 512))
        height = int(data.get('height', 512))
        seed = data.get('seed')
        if seed:
            seed = int(seed)
        
        return Response(
            batch_generate_stream(folder, filename, caption_prompt, short_addition, width, height, seed),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        print(f"\n✗ Error in batch generation endpoint: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/batch_outputs/<filename>')
def serve_batch_output(filename):
    """Serve generated batch images"""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/images/<folder>')
def list_images(folder):
    """
    List all images from civitai/images or frameset/images folder
    """
    try:
        # Validate folder name
        if folder not in ['civitai', 'frameset']:
            return jsonify({'error': 'Invalid folder name'}), 400

        # Get the images directory path
        images_dir = Path(f'{folder}/images')

        if not images_dir.exists():
            return jsonify({'error': f'Folder not found: {images_dir}'}), 404

        # Supported image extensions
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp']

        images = []
        for ext in extensions:
            for img_path in images_dir.glob(ext):
                try:
                    # Get basic info
                    file_size = img_path.stat().st_size

                    images.append({
                        'filename': img_path.name,
                        'folder': folder,
                        'file_size': file_size,
                        'path': str(img_path.relative_to('.'))
                    })
                except Exception as e:
                    print(f"Error reading {img_path.name}: {e}")

        # Sort by filename
        images.sort(key=lambda x: x['filename'])

        return jsonify({
            'success': True,
            'folder': folder,
            'count': len(images),
            'images': images
        })

    except Exception as e:
        print(f"Error listing images: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/images/<folder>/<filename>')
def serve_folder_image(folder, filename):
    """Serve an image from civitai/images or frameset/images folder"""
    try:
        # Validate folder name
        if folder not in ['civitai', 'frameset']:
            return jsonify({'error': 'Invalid folder name'}), 400

        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)

        # Get the images directory path
        images_dir = Path(f'{folder}/images')
        filepath = images_dir / filename

        if not filepath.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(filepath, mimetype='image/jpeg')

    except Exception as e:
        print(f"Error serving image: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'mode': 'batch_generation',
        'flux_model': 'black-forest-labs/FLUX.1-Kontext-dev',
        'nano_banana_model': 'gemini-2.5-flash-image',
        'caption_models': ['gemini-2.5-pro', 'gpt-4.1-2025-04-14'],
        'available_models': llm.get_all_llms()
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FLUX Batch Image Generation Server')
    parser.add_argument('--port', type=int, default=8119, help='Port to run the server on (default: 8119)')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("FLUX Batch Image Generation Server (SSE Streaming)")
    print("="*60)
    print("\nStarting server...")
    print(f"Access the web interface at: http://localhost:{args.port}")
    print("\nFeatures:")
    print("  • Batch generate 16 images from a single source")
    print("  • 4 captions using Gemini 2.0 Flash & GPT-4o")
    print("  • 2 prompt versions (normal + short)")
    print("  • 2 image models per caption (FLUX + Nano Banana)")
    print("  • Real-time progress streaming (no timeout!)")
    print("\nAPI Endpoints:")
    print("  POST /api/batch-generate - Stream batch generation progress")
    print("  GET  /api/images/<folder> - List images")
    print("  GET  /api/health   - Health check")
    print("\n" + "="*60 + "\n")

    app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)