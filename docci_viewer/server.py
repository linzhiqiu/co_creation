#!/usr/bin/env python3
"""
Server for DOCCI Viewer - displays original and compressed descriptions.

Usage:
    python server.py [--port 8082] [--host 0.0.0.0] [--image_dir /path/to/images] [--jsonl docci/oct_21_examples.jsonlines]
"""

import http.server
import socketserver
import json
import argparse
from pathlib import Path
from urllib.parse import unquote, parse_qs, urlparse
import base64

# Default configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_JSONL = SCRIPT_DIR.parent / "docci" / "oct_22_examples.jsonlines"
DEFAULT_IMAGE_DIR = Path("/project_data/ramanan/yuhanhua/test_images")
PORT = 8082
HOST = "0.0.0.0"


class DOCCIViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for the DOCCI viewer."""

    def __init__(self, *args, jsonl_path=None, image_dir=None, **kwargs):
        self.jsonl_path = jsonl_path
        self.image_dir = image_dir
        self._data_cache = None
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        
        # API endpoint: Get all DOCCI examples
        if self.path == "/api/examples":
            self.send_json_response(self.get_examples())
            return
        
        # API endpoint: Get statistics
        if self.path == "/api/stats":
            self.send_json_response(self.get_stats())
            return
        
        # API endpoint: Serve images
        if self.path.startswith("/api/image/"):
            image_file = unquote(self.path.split("/api/image/")[1])
            self.serve_image(image_file)
            return
        
        # Serve static files (HTML, CSS, JS)
        super().do_GET()

    def load_data(self):
        """Load and cache JSONL data."""
        if self._data_cache is not None:
            return self._data_cache
        
        examples = []
        try:
            with open(self.jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        examples.append(json.loads(line))
            
            self._data_cache = examples
            print(f"Loaded {len(examples)} examples from {self.jsonl_path}")
            return examples
        except Exception as e:
            print(f"Error loading JSONL: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_examples(self):
        """Get all examples."""
        return self.load_data()

    def get_stats(self):
        """Calculate statistics about the dataset."""
        examples = self.load_data()
        
        if not examples:
            return {
                "total": 0,
                "avg_original_length": 0,
                "avg_compressed_length": 0,
                "compression_ratio": 0
            }
        
        total = len(examples)
        total_orig_len = sum(len(ex.get('description_original', '')) for ex in examples)
        total_comp_len = sum(len(ex.get('description', '')) for ex in examples)
        
        avg_orig = total_orig_len / total if total > 0 else 0
        avg_comp = total_comp_len / total if total > 0 else 0
        compression_ratio = (1 - avg_comp / avg_orig) * 100 if avg_orig > 0 else 0
        
        return {
            "total": total,
            "avg_original_length": round(avg_orig, 1),
            "avg_compressed_length": round(avg_comp, 1),
            "compression_ratio": round(compression_ratio, 1)
        }

    def serve_image(self, image_file):
        """Serve an image file."""
        try:
            image_path = self.image_dir / image_file
            
            if not image_path.exists():
                self.send_error(404, f"Image not found: {image_file}")
                return
            
            # Determine content type
            suffix = image_path.suffix.lower()
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_types.get(suffix, 'application/octet-stream')
            
            # Read and send image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(image_data))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(image_data)
            
        except Exception as e:
            print(f"Error serving image {image_file}: {e}")
            self.send_error(500, str(e))

    def send_json_response(self, data):
        """Send a JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to customize logging."""
        try:
            if args and len(args) > 0 and isinstance(args[0], str) and "api" in args[0]:
                print(f"{self.address_string()} - {format % args}")
        except:
            pass


def create_handler(jsonl_path, image_dir):
    """Create a handler with the specified paths."""
    def handler(*args, **kwargs):
        return DOCCIViewerHandler(*args, jsonl_path=jsonl_path, image_dir=image_dir, **kwargs)
    return handler


def main():
    parser = argparse.ArgumentParser(description="DOCCI Viewer Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to run server on (default: {PORT})")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--image_dir", type=str, default=None, help=f"Path to image directory (default: {DEFAULT_IMAGE_DIR})")
    parser.add_argument("--jsonl", type=str, default=None, help=f"Path to JSONL file (default: {DEFAULT_JSONL})")
    args = parser.parse_args()

    # Set paths
    jsonl_path = Path(args.jsonl) if args.jsonl else DEFAULT_JSONL
    image_dir = Path(args.image_dir) if args.image_dir else DEFAULT_IMAGE_DIR
    
    # Check if files exist
    if not jsonl_path.exists():
        print(f"⚠️  Warning: JSONL file not found at {jsonl_path}")
        print(f"    Please provide a valid path with --jsonl")
    else:
        print(f"✓ Found JSONL file: {jsonl_path.resolve()}")
    
    if not image_dir.exists():
        print(f"⚠️  Warning: Image directory not found at {image_dir}")
        print(f"    Please provide a valid path with --image_dir")
    else:
        image_count = len(list(image_dir.glob('*.jpg'))) + len(list(image_dir.glob('*.png')))
        print(f"✓ Found image directory with {image_count} images")
    
    # Change to the script directory to serve index.html
    import os
    os.chdir(SCRIPT_DIR)
    
    # Create handler with custom paths
    handler = create_handler(jsonl_path, image_dir)
    
    # Create server
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print("=" * 60)
        print(f"🖼️  DOCCI Viewer Server")
        print("=" * 60)
        print(f"📁 JSONL:        {jsonl_path.resolve()}")
        print(f"📁 Images:       {image_dir.resolve()}")
        print(f"🌐 Server:       http://{args.host}:{args.port}")
        if args.host == "0.0.0.0":
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"🔗 Local URL:    http://{local_ip}:{args.port}")
            print(f"🔗 Localhost:    http://localhost:{args.port}")
        print("=" * 60)
        print("\n✨ Server is running. Press Ctrl+C to stop.\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down server...")


if __name__ == "__main__":
    main()