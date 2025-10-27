"""
Flask Server for FLUX Image Generation and Captioning
"""
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import uuid
from pathlib import Path
import traceback
from datetime import datetime
import toml
from PIL import Image
import argparse

# Import our modules
from flux_generator import generate_image_from_text_prompt as flux_generate
import google_imagen_generator
import llm

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
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


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('flux.html')


@app.route('/api/generate', methods=['POST'])
def generate_image():
    """
    Generate image from text prompt using FLUX or Google Imagen

    Expected JSON:
    {
        "prompt": "description of image",
        "model": "flux" or "google",  // default: "flux"
        "width": 1024,
        "height": 1024,
        "num_inference_steps": 28,  // FLUX only
        "guidance_scale": 3.5,       // FLUX only
        "seed": null or integer
    }
    """
    try:
        data = request.get_json()

        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400

        prompt = data['prompt']
        model = data.get('model', 'flux').lower()
        width = data.get('width', 512)
        height = data.get('height', 512)
        seed = data.get('seed', None)

        print(f"\n{'='*60}")
        print(f"Generating image at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Model: {model.upper()}")
        print(f"Prompt: {prompt}")
        print(f"Settings: {width}x{height}")

        # Generate image based on selected model
        if model == 'google':
            print("Using Google Imagen")
            print(f"{'='*60}\n")

            # Generate with Google Imagen
            image = google_imagen_generator.generate_image_from_text_prompt(
                prompt=prompt,
                width=width,
                height=height,
                seed=seed
            )
        else:  # Default to FLUX
            num_inference_steps = data.get('num_inference_steps', 28)
            guidance_scale = data.get('guidance_scale', 3.5)

            print(f"Using FLUX (steps={num_inference_steps}, guidance={guidance_scale})")
            print(f"{'='*60}\n")

            # Generate with FLUX
            image = flux_generate(
                prompt=prompt,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                width=width,
                height=height,
                seed=seed
            )
        
        # Save image with unique filename
        unique_id = str(uuid.uuid4())
        filename = f"{model}_{unique_id}.png"
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        image.save(filepath)
        
        print(f"\n✓ Image saved: {filepath}\n")
        
        return jsonify({
            'success': True,
            'image_url': f'/outputs/{filename}',
            'filename': filename
        })
        
    except Exception as e:
        print(f"\n✗ Error generating image: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/caption', methods=['POST'])
def caption_image_endpoint():
    """
    Generate caption for uploaded image using llm module
    
    Expected multipart/form-data:
    - image: image file
    - model: model name (e.g., 'gemini-2.5-pro', 'gpt-4o-2024-08-06')
    - prompt: optional custom prompt (defaults to DEFAULT_CAPTION_PROMPT)
    """
    try:
        # Check if image was provided
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'Invalid file type. Allowed: {ALLOWED_EXTENSIONS}'}), 400
        
        # Get parameters
        model = request.form.get('model', 'gemini-2.5-pro')
        custom_prompt = request.form.get('prompt', DEFAULT_CAPTION_PROMPT)
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())
        filename = f"{unique_id}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"\n{'='*60}")
        print(f"Captioning image at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"File: {filename}")
        print(f"Model: {model}")
        print(f"{'='*60}\n")
        
        # Get LLM instance from llm module
        llm_instance = llm.get_llm(model=model, secrets=secrets)
        
        # Generate caption using llm.generate() with images parameter
        caption = llm_instance.generate(
            prompt=custom_prompt,
            images=[filepath],  # Pass image path in a list
            temperature=0.0
        )
        
        print(f"\n✓ Caption generated: {caption}\n")
        
        # Clean up uploaded file
        try:
            os.remove(filepath)
        except:
            pass
        
        # Determine provider from model name for UI display
        if model in llm.ALL_MODELS["ChatGPT"]:
            provider = 'ChatGPT'
        elif model in llm.ALL_MODELS["Gemini"]:
            provider = 'Gemini'
        elif model in llm.ALL_MODELS["OpenSource"]:
            provider = 'OpenSource'
        else:
            provider = 'Unknown'
        
        return jsonify({
            'success': True,
            'caption': caption,
            'provider': provider,
            'model': model
        })
        
    except Exception as e:
        print(f"\n✗ Error captioning image: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/outputs/<filename>')
def serve_output(filename):
    """Serve generated images"""
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'flux_model': 'black-forest-labs/FLUX.1-Kontext-dev',
        'available_models': llm.get_all_llms()
    })


@app.route('/api/images/<folder>')
def list_images(folder):
    """
    List all images from civitai/images or frameset/images folder

    Args:
        folder: 'civitai' or 'frameset'
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FLUX Image Generation & Captioning Server')
    parser.add_argument('--port', type=int, default=8118, help='Port to run the server on (default: 8118)')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("FLUX Image Generation & Captioning Server")
    print("="*60)
    print("\nStarting server...")
    print(f"Access the web interface at: http://localhost:{args.port}")
    print("\nAPI Endpoints:")
    print("  POST /api/generate - Generate image from text prompt")
    print("  POST /api/caption  - Generate caption from image")
    print("  GET  /api/health   - Health check")
    print("\nUsing llm module with models:")
    for model_type, models in llm.ALL_MODELS.items():
        print(f"  {model_type}: {', '.join(models)}")
    print("\n" + "="*60 + "\n")

    app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)