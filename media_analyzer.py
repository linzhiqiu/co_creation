#!/usr/bin/env python3
"""
Media File Analyzer - Counts images/videos, calculates storage and aspect ratios
"""
import os
import argparse
from pathlib import Path
from collections import defaultdict
from PIL import Image
import subprocess
import json


def get_video_dimensions(video_path):
    """Get video dimensions using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    return width, height
    except Exception:
        pass
    return None, None


def classify_aspect_ratio(width, height):
    """Classify aspect ratio into predefined categories"""
    if not width or not height:
        return "Others"
    
    ratio = width / height
    
    # Define aspect ratios with tolerance
    aspect_ratios = {
        "16:9": 16/9,
        "9:16": 9/16,
        "1:1": 1.0,
        "4:3": 4/3,
        "3:4": 3/4,
        "4:5": 4/5,
        "5:4": 5/4,
        "3:5": 3/5,
        "5:3": 5/3,
        "2.39:1": 2.39,
        "1:2.39": 1/2.39,
    }
    
    tolerance = 0.02  # 2% tolerance
    
    for name, target_ratio in aspect_ratios.items():
        if abs(ratio - target_ratio) / target_ratio < tolerance:
            return name
    
    return "Others"


def analyze_media_folder(folder_path):
    """Analyze all images and videos in the given folder"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Error: Folder '{folder_path}' does not exist")
        return
    
    # Supported extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
    
    total_count = 0
    total_size = 0
    aspect_ratio_counts = defaultdict(int)
    file_sizes = []
    
    print(f"Scanning folder: {folder.absolute()}\n")
    
    for file_path in folder.rglob('*'):
        if not file_path.is_file():
            continue
        
        ext = file_path.suffix.lower()
        
        if ext in image_extensions or ext in video_extensions:
            total_count += 1
            file_size = file_path.stat().st_size
            total_size += file_size
            file_sizes.append(file_size)
            
            # Get dimensions
            width, height = None, None
            
            if ext in image_extensions:
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                except Exception:
                    pass
            elif ext in video_extensions:
                width, height = get_video_dimensions(file_path)
            
            # Classify aspect ratio
            aspect_ratio = classify_aspect_ratio(width, height)
            aspect_ratio_counts[aspect_ratio] += 1
    
    # Print results
    print("=" * 60)
    print("MEDIA ANALYSIS RESULTS")
    print("=" * 60)
    print(f"\nTotal files: {total_count}")
    print(f"Total storage: {format_size(total_size)}")
    
    if file_sizes:
        avg_size = sum(file_sizes) / len(file_sizes)
        print(f"Average file size: {format_size(avg_size)}")
    
    print(f"\n{'ASPECT RATIO DISTRIBUTION':^60}")
    print("-" * 60)
    print(f"{'Aspect Ratio':<15} {'Count':>10} {'Percentage':>15}")
    print("-" * 60)
    
    # Sort by count (descending)
    sorted_ratios = sorted(aspect_ratio_counts.items(), key=lambda x: x[1], reverse=True)
    
    for aspect_ratio, count in sorted_ratios:
        percentage = (count / total_count * 100) if total_count > 0 else 0
        bar = "█" * int(percentage / 2)
        print(f"{aspect_ratio:<15} {count:>10} {percentage:>14.1f}% {bar}")
    
    print("=" * 60)


def format_size(bytes_size):
    """Format bytes into human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def main():
    parser = argparse.ArgumentParser(
        description='Analyze images and videos in a folder'
    )
    parser.add_argument(
        'folder',
        nargs='?',
        default='./frameset/images/',
        help='Folder path to analyze (default: ./frameset/images/)'
    )
    
    args = parser.parse_args()
    analyze_media_folder(args.folder)


if __name__ == '__main__':
    main()