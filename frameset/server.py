#!/usr/bin/env python3
"""
Server for Frameset Viewer - displays video frame images.

Usage:
    python server.py [--port 8084] [--host 0.0.0.0] [--images_dir ./images]
"""

import http.server
import socketserver
import json
import argparse
from pathlib import Path
from urllib.parse import unquote
import mimetypes
import signal
import sys
from PIL import Image

# Default configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
PORT = 8084
HOST = "0.0.0.0"


class ReusableTCPServer(socketserver.TCPServer):
    """TCP Server that allows address reuse to prevent 'Address already in use' errors."""
    allow_reuse_address = True
    
    def server_bind(self):
        """Bind the server with SO_REUSEADDR set."""
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


class FramesetViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for the frameset viewer."""

    def __init__(self, *args, images_dir=None, **kwargs):
        self.images_dir = images_dir
        self._data_cache = None
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        
        # API endpoint: Get all images
        if self.path == "/api/images":
            self.send_json_response(self.get_images())
            return
        
        # API endpoint: Get statistics
        if self.path == "/api/stats":
            self.send_json_response(self.get_stats())
            return
        
        # API endpoint: Serve image
        if self.path.startswith("/api/image/"):
            image_file = unquote(self.path.split("/api/image/")[1])
            self.serve_image(image_file)
            return
        
        # Serve static files (HTML, CSS, JS)
        super().do_GET()

    def load_data(self):
        """Load and cache image data."""
        if self._data_cache is not None:
            return self._data_cache
        
        images = []
        try:
            if self.images_dir.exists():
                # Supported image formats
                extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp']
                
                for ext in extensions:
                    for img_path in self.images_dir.glob(ext):
                        try:
                            # Get image dimensions and file size
                            with Image.open(img_path) as img:
                                width, height = img.size
                            
                            file_size = img_path.stat().st_size
                            
                            images.append({
                                "filename": img_path.name,
                                "width": width,
                                "height": height,
                                "file_size": file_size,
                                "format": img_path.suffix[1:].upper()
                            })
                        except Exception as e:
                            print(f"Error loading {img_path.name}: {e}")
            
            # Sort by filename
            images.sort(key=lambda x: x['filename'])
            
            self._data_cache = images
            print(f"✓ Loaded {len(images)} images from {self.images_dir}")
            return images
        except Exception as e:
            print(f"Error loading images: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_images(self):
        """Get all images."""
        return self.load_data()

    def get_stats(self):
        """Calculate statistics about the images."""
        images = self.load_data()
        
        if not images:
            return {
                "total": 0,
                "total_size": 0,
                "avg_width": 0,
                "avg_height": 0
            }
        
        total = len(images)
        total_size = sum(img['file_size'] for img in images)
        avg_width = sum(img['width'] for img in images) / total
        avg_height = sum(img['height'] for img in images) / total
        
        return {
            "total": total,
            "total_size": total_size,
            "avg_width": round(avg_width, 1),
            "avg_height": round(avg_height, 1)
        }

    def serve_image(self, image_file):
        """Serve an image file."""
        try:
            image_path = self.images_dir / image_file
            
            if not image_path.exists():
                self.send_error(404, f"Image not found: {image_file}")
                return
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(str(image_path))
            if not content_type:
                content_type = 'application/octet-stream'
            
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


def create_handler(images_dir):
    """Create a handler with the specified paths."""
    def handler(*args, **kwargs):
        return FramesetViewerHandler(*args, images_dir=images_dir, **kwargs)
    return handler


def main():
    parser = argparse.ArgumentParser(description="Frameset Viewer Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to run server on (default: {PORT})")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--images_dir", type=str, default="images", help="Path to images directory (default: ./images)")
    args = parser.parse_args()

    # Set paths
    images_dir = Path(args.images_dir).resolve()
    
    # Check if directory exists
    print("=" * 60)
    print("🔍 Checking directories...")
    print("=" * 60)
    
    if not images_dir.exists():
        print(f"⚠️  Warning: Images directory not found at {images_dir}")
        images_dir.mkdir(parents=True, exist_ok=True)
        print(f"    Created empty directory")
    else:
        # Count images
        image_count = sum(1 for _ in images_dir.glob('*.[jJ][pP]*[gG]'))
        image_count += sum(1 for _ in images_dir.glob('*.[pP][nN][gG]'))
        print(f"✓ Found {image_count} images in {images_dir}")
    
    # Change to the script directory to serve index.html
    import os
    os.chdir(SCRIPT_DIR)
    
    # Create handler with custom paths
    handler = create_handler(images_dir)
    
    # Create server with address reuse
    httpd = ReusableTCPServer((args.host, args.port), handler)
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n👋 Shutting down server gracefully...")
        httpd.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n" + "=" * 60)
    print(f"🎞️  Frameset Viewer Server")
    print("=" * 60)
    print(f"📁 Images dir:   {images_dir}")
    print(f"🌐 Server:       http://{args.host}:{args.port}")
    if args.host == "0.0.0.0":
        import socket
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
            print(f"🔗 Local URL:    http://{local_ip}:{args.port}")
        except:
            pass
        print(f"🔗 Localhost:    http://localhost:{args.port}")
    print("=" * 60)
    print("\n✨ Server is running. Press Ctrl+C to stop.\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        httpd.shutdown()


if __name__ == "__main__":
    main()