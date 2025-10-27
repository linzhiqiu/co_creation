#!/usr/bin/env python3
"""
Caption Generation Script for Civitai and Frameset Images

Generates both normal and short captions for all images in specified datasets.
Uses GPT-4.1 as default LLM and saves results as JSON files.

Features:
- Batch processing of entire datasets
- Dry-run mode to check status
- Resume capability (skips already generated)
- Detailed status reporting
- Single image mode
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
import toml
import traceback
from typing import Dict, List, Tuple
from tqdm import tqdm
import time

# Import LLM module
import llm

# Caption prompts (from flux_batch_server.py)
NORMAL_CAPTION_PROMPT = """You are given an image. Write a detailed natural language prompt that could have been used to generate this image. Focus on the most salient and unique visual elements such as the subjects, their clothing, expressions, actions, background, and composition. Describe the color palette, lighting, and overall style, including any cinematic or artistic qualities like camera angle, depth of field, or motion. Make the description as accurate and faithful to the image as possible. If small details are uncertain or ambiguous, omit them and prioritize capturing the overall scene, mood, and visual impression. The final prompt should be coherent, evocative, written as if by an expert visual artist or filmmaker recreating the exact scene."""

SHORT_CAPTION_PROMPT = """You are given an image. Write a detailed natural language prompt that could have been used to generate this image. Focus on the most salient and unique visual elements such as the subjects, their clothing, expressions, actions, background, and composition. Describe the color palette, lighting, and overall style, including any cinematic or artistic qualities like camera angle, depth of field, or motion. Make the description as accurate and faithful to the image as possible. If small details are uncertain or ambiguous, omit them and prioritize capturing the overall scene, mood, and visual impression. The final prompt should be coherent, evocative, written as if by an expert visual artist or filmmaker recreating the exact scene.

Keep your response to at most 30 to 60 words."""

# Configuration
DATASETS = ['civitai', 'frameset']
CAPTION_TYPES = ['normal', 'short']
DEFAULT_MODEL = 'gpt-4.1-2025-04-14'
SECRETS_PATH = "llm/secrets.toml"
OUTPUT_BASE_DIR = "captions"
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']

# Performance settings
DEFAULT_MAX_WORKERS = 10  # Safe for Tier 5: 10,000 RPM limit
DEFAULT_IMAGE_LIMIT = 10000  # Max images per dataset


def load_secrets():
    """Load API keys from llm/secrets.toml"""
    if os.path.exists(SECRETS_PATH):
        try:
            secrets = toml.load(SECRETS_PATH)
            print("✓ Secrets loaded from llm/secrets.toml")
            return secrets
        except Exception as e:
            print(f"⚠ Warning: Could not load secrets.toml: {e}")
            return None
    else:
        print(f"⚠ Warning: {SECRETS_PATH} not found")
        return None


def get_caption_prompt(caption_type: str) -> str:
    """Get the prompt text for the specified caption type"""
    if caption_type == 'normal':
        return NORMAL_CAPTION_PROMPT
    elif caption_type == 'short':
        return SHORT_CAPTION_PROMPT
    else:
        raise ValueError(f"Invalid caption type: {caption_type}")


def get_caption_json_path(dataset: str, caption_type: str, image_filename: str) -> Path:
    """Get the path where the caption JSON should be saved"""
    output_dir = Path(OUTPUT_BASE_DIR) / dataset / caption_type
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{image_filename}.json"


def load_caption_json(json_path: Path) -> Dict:
    """Load existing caption JSON if it exists"""
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"  ⚠ Error loading {json_path}: {e}")
            return None
    return None


def save_caption_json(json_path: Path, data: Dict):
    """Save caption data to JSON file"""
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"  ✗ Error saving {json_path}: {e}")
        return False


def generate_caption(image_path: Path, caption_type: str, model: str, secrets) -> Tuple[str, bool, str]:
    """
    Generate caption for an image with retry logic for rate limits
    
    Returns:
        (caption_text, success, error_message)
    """
    max_retries = 5
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            prompt = get_caption_prompt(caption_type)
            
            # Get LLM instance
            llm_instance = llm.get_llm(model=model, secrets=secrets)
            
            # Generate caption
            caption = llm_instance.generate(
                prompt=prompt,
                images=[str(image_path)],
                temperature=0.0
            )
            
            return (caption, True, None)
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error
            if '429' in error_msg or 'rate limit' in error_msg.lower():
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    error_msg = f"Rate limit exceeded after {max_retries} retries: {error_msg}"
            
            # Non-rate-limit error or max retries reached
            return (None, False, f"{type(e).__name__}: {error_msg}")


def get_image_files(dataset: str, limit: int = None) -> List[Path]:
    """
    Get list of all image files in a dataset
    
    Args:
        dataset: Dataset name ('civitai' or 'frameset')
        limit: Maximum number of images to return (None = all)
    
    Returns:
        Sorted list of image paths (deterministic order)
    """
    images_dir = Path(f"{dataset}/images")
    
    if not images_dir.exists():
        print(f"⚠ Warning: Directory not found: {images_dir}")
        return []
    
    image_files = []
    for ext in IMAGE_EXTENSIONS:
        image_files.extend(images_dir.glob(f"*{ext}"))
        image_files.extend(images_dir.glob(f"*{ext.upper()}"))
    
    # Sort for deterministic order
    image_files = sorted(image_files)
    
    # Apply limit if specified
    if limit is not None and limit > 0:
        image_files = image_files[:limit]
    
    return image_files


def load_all_captions(datasets: List[str] = None, caption_types: List[str] = None) -> Dict:
    """
    Load all successful captions from the captions/ folder into a dictionary.
    
    Args:
        datasets: List of datasets to load (default: all datasets)
        caption_types: List of caption types to load (default: all types)
    
    Returns:
        Dictionary with structure:
        {
            'civitai': {
                'image001.jpg': {
                    'normal': 'caption text...',
                    'short': 'short caption...'
                },
                ...
            },
            'frameset': {...}
        }
    
    Example:
        # Load all captions
        captions = load_all_captions()
        
        # Access a specific caption
        normal_caption = captions['civitai']['image001.jpg']['normal']
        short_caption = captions['civitai']['image001.jpg']['short']
        
        # Load only civitai normal captions
        captions = load_all_captions(datasets=['civitai'], caption_types=['normal'])
    """
    if datasets is None:
        datasets = DATASETS
    if caption_types is None:
        caption_types = CAPTION_TYPES
    
    result = {}
    
    for dataset in datasets:
        result[dataset] = {}
        
        for caption_type in caption_types:
            caption_dir = Path(OUTPUT_BASE_DIR) / dataset / caption_type
            
            if not caption_dir.exists():
                continue
            
            for json_file in caption_dir.glob("*.json"):
                data = load_caption_json(json_file)
                
                # Only load successful captions
                if data and data.get('status') == 'success':
                    image_filename = data['image_filename']
                    caption_text = data['caption']
                    
                    # Initialize image entry if needed
                    if image_filename not in result[dataset]:
                        result[dataset][image_filename] = {}
                    
                    # Store caption
                    result[dataset][image_filename][caption_type] = caption_text
    
    return result


def get_status_summary(dataset: str, caption_type: str) -> Dict[str, int]:
    """Get summary of caption generation status for a dataset/type combination"""
    # Get total images that should have captions
    image_files = get_image_files(dataset)
    total_images = len(image_files)
    
    caption_dir = Path(OUTPUT_BASE_DIR) / dataset / caption_type
    
    if not caption_dir.exists():
        return {
            'success': 0,
            'failed': 0,
            'not_generated': total_images,
            'total': total_images
        }
    
    success_count = 0
    failed_count = 0
    
    for json_file in caption_dir.glob("*.json"):
        data = load_caption_json(json_file)
        if data:
            if data.get('status') == 'success':
                success_count += 1
            elif data.get('status') == 'failed':
                failed_count += 1
    
    not_generated = total_images - success_count - failed_count
    
    return {
        'success': success_count,
        'failed': failed_count,
        'not_generated': not_generated,
        'total': total_images
    }


def process_image(
    image_path: Path,
    dataset: str,
    caption_type: str,
    model: str,
    secrets,
    force: bool = False,
    dry_run: bool = False
) -> Tuple[str, float]:
    """
    Process a single image to generate caption
    
    Returns:
        (status, elapsed_time): Status is 'success', 'failed', 'skipped', or 'dry_run'
                                elapsed_time is the time taken in seconds
    """
    start_time = time.time()
    
    image_filename = image_path.name
    json_path = get_caption_json_path(dataset, caption_type, image_filename)
    
    # Check if already exists
    existing_data = load_caption_json(json_path)
    if existing_data and not force:
        if existing_data.get('status') == 'success':
            return ('skipped', time.time() - start_time)
    
    if dry_run:
        return ('dry_run', time.time() - start_time)
    
    # Generate caption
    caption_text, success, error_msg = generate_caption(image_path, caption_type, model, secrets)
    
    # Prepare JSON data
    caption_data = {
        'image_filename': image_filename,
        'dataset': dataset,
        'caption_type': caption_type,
        'prompt_used': get_caption_prompt(caption_type),
        'llm_model': model,
        'caption': caption_text,
        'status': 'success' if success else 'failed',
        'timestamp': datetime.now().isoformat(),
        'word_count': len(caption_text.split()) if caption_text else 0,
        'error_message': error_msg
    }
    
    # Save to JSON
    if save_caption_json(json_path, caption_data):
        elapsed = time.time() - start_time
        return (('success' if success else 'failed'), elapsed)
    else:
        return ('failed', time.time() - start_time)


def dry_run_report(datasets: List[str]):
    """Generate a dry-run report showing status of all captions"""
    print("\n" + "="*80)
    print("DRY RUN REPORT - Caption Generation Status")
    print("="*80)
    
    total_success = 0
    total_failed = 0
    total_not_generated = 0
    total_captions_needed = 0
    
    for dataset in datasets:
        print(f"\n📁 Dataset: {dataset}")
        print("-" * 80)
        
        for caption_type in CAPTION_TYPES:
            status = get_status_summary(dataset, caption_type)
            total_success += status['success']
            total_failed += status['failed']
            total_not_generated += status['not_generated']
            total_captions_needed += status['total']  # Each type needs 'total' captions
            
            print(f"  {caption_type.capitalize():10s}: "
                  f"✓ {status['success']:4d} success  "
                  f"✗ {status['failed']:4d} failed  "
                  f"○ {status['not_generated']:4d} not generated  "
                  f"({status['total']} total images)")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    total_images = sum(len(get_image_files(d)) for d in datasets)
    print(f"Total Images: {total_images}")
    print(f"Total Captions Needed: {total_captions_needed}")
    print(f"✓ Success: {total_success}")
    print(f"✗ Failed: {total_failed}")
    print(f"○ Not Generated: {total_not_generated}")
    completion_pct = (total_success / total_captions_needed * 100) if total_captions_needed > 0 else 0
    print(f"Completion: {completion_pct:.1f}%")
    print("="*80 + "\n")


def process_dataset(
    dataset: str,
    caption_types: List[str],
    model: str,
    secrets,
    force: bool = False,
    dry_run: bool = False,
    single_image: str = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    image_limit: int = None
):
    """Process all images in a dataset with parallel processing"""
    
    # Get image files
    if single_image:
        image_path = Path(f"{dataset}/images") / single_image
        if not image_path.exists():
            print(f"✗ Error: Image not found: {image_path}")
            return
        image_files = [image_path]
    else:
        image_files = get_image_files(dataset, limit=image_limit)
    
    if not image_files:
        print(f"⚠ No images found in {dataset}")
        return
    
    print(f"\n{'='*80}")
    print(f"Processing Dataset: {dataset}")
    print(f"{'='*80}")
    print(f"Images to process: {len(image_files)}")
    if image_limit and len(image_files) == image_limit:
        print(f"  (Limited to first {image_limit} images in sorted order)")
    print(f"Caption types: {', '.join(caption_types)}")
    print(f"Model: {model}")
    print(f"Workers: {max_workers} parallel threads")
    if dry_run:
        print("Mode: DRY RUN (no actual generation)")
    elif force:
        print("Mode: FORCE (regenerate existing)")
    else:
        print("Mode: RESUME (skip existing successful)")
    print(f"{'='*80}\n")
    
    # Create task list: (image_path, caption_type)
    tasks = []
    for image_path in image_files:
        for caption_type in caption_types:
            tasks.append((image_path, caption_type))
    
    # Statistics
    stats = {
        'success': 0,
        'failed': 0,
        'skipped': 0
    }
    
    # Process with ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                process_image,
                image_path,
                dataset,
                caption_type,
                model,
                secrets,
                force,
                dry_run
            ): (image_path, caption_type)
            for image_path, caption_type in tasks
        }
        
        # Process with progress bar
        with tqdm(total=len(tasks), desc=f"Processing {dataset}", unit="caption") as pbar:
            for future in as_completed(future_to_task):
                image_path, caption_type = future_to_task[future]
                
                try:
                    status, elapsed = future.result()
                    
                    # Update statistics
                    if status == 'success':
                        stats['success'] += 1
                        pbar.set_postfix_str(f"✓ {stats['success']} ✗ {stats['failed']} ○ {stats['skipped']}")
                    elif status == 'failed':
                        stats['failed'] += 1
                        pbar.set_postfix_str(f"✓ {stats['success']} ✗ {stats['failed']} ○ {stats['skipped']}")
                    elif status == 'skipped':
                        stats['skipped'] += 1
                        pbar.set_postfix_str(f"✓ {stats['success']} ✗ {stats['failed']} ○ {stats['skipped']}")
                    
                except Exception as e:
                    stats['failed'] += 1
                    print(f"\n✗ Error processing {image_path.name} ({caption_type}): {e}")
                
                pbar.update(1)
    
    # Final summary
    print(f"\n{'='*80}")
    print(f"Dataset {dataset} Complete")
    print(f"{'='*80}")
    print(f"✓ Success: {stats['success']}")
    print(f"✗ Failed: {stats['failed']}")
    print(f"○ Skipped: {stats['skipped']}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Generate captions for Civitai and Frameset images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to check status
  python generate_captions.py --dry-run
  
  # Generate all missing captions (10 threads, 10k images per dataset)
  python generate_captions.py --dataset civitai frameset
  
  # Use more threads for faster processing (if within rate limits)
  python generate_captions.py --dataset civitai --workers 20
  
  # Process all images (remove limit)
  python generate_captions.py --dataset civitai --limit 0
  
  # Generate only normal captions for first 1000 civitai images
  python generate_captions.py --dataset civitai --type normal --limit 1000
  
  # Force regenerate all captions
  python generate_captions.py --dataset civitai --force
  
  # Generate caption for single image
  python generate_captions.py --dataset civitai --image image001.jpg
  
  # Use different model
  python generate_captions.py --dataset civitai --model gemini-2.5-pro
        """
    )
    
    parser.add_argument(
        '--dataset',
        nargs='+',
        choices=DATASETS + ['all'],
        default=['all'],
        help='Dataset(s) to process (default: all)'
    )
    
    parser.add_argument(
        '--type',
        nargs='+',
        choices=CAPTION_TYPES + ['all'],
        default=['all'],
        help='Caption type(s) to generate (default: all)'
    )
    
    parser.add_argument(
        '--model',
        default=DEFAULT_MODEL,
        help=f'LLM model to use (default: {DEFAULT_MODEL})'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help=f'Number of parallel workers (default: {DEFAULT_MAX_WORKERS})'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=DEFAULT_IMAGE_LIMIT,
        help=f'Max images per dataset, 0 for unlimited (default: {DEFAULT_IMAGE_LIMIT})'
    )
    
    parser.add_argument(
        '--image',
        help='Process only this specific image file'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regenerate even if caption already exists'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - check status without generating'
    )
    
    args = parser.parse_args()
    
    # Handle 'all' selections
    datasets = DATASETS if 'all' in args.dataset else args.dataset
    caption_types = CAPTION_TYPES if 'all' in args.type else args.type
    
    # Handle limit (0 means unlimited)
    image_limit = None if args.limit == 0 else args.limit
    
    # Load secrets
    print("\n" + "="*80)
    print("Caption Generation Script")
    print("="*80)
    secrets = load_secrets()
    
    if args.dry_run:
        # Run dry-run report
        dry_run_report(datasets)
    else:
        # Show configuration
        print(f"Configuration:")
        print(f"  Workers: {args.workers} parallel threads")
        print(f"  Image limit: {image_limit if image_limit else 'unlimited'} per dataset")
        print(f"  Model: {args.model}")
        print("="*80)
        
        # Process datasets
        for dataset in datasets:
            process_dataset(
                dataset,
                caption_types,
                args.model,
                secrets,
                force=args.force,
                dry_run=False,
                single_image=args.image,
                max_workers=args.workers,
                image_limit=image_limit
            )
        
        # Show final summary
        print("\n" + "="*80)
        print("FINAL STATUS SUMMARY")
        print("="*80)
        dry_run_report(datasets)


if __name__ == '__main__':
    main()