#!/usr/bin/env python3
"""
Unified Server - serves all viewers (Civitai, Frameset) on a single port.

Usage:
    python server.py [--port 8080]
"""

import http.server
import socketserver
import json
import argparse
from pathlib import Path
from urllib.parse import unquote, urlparse
import mimetypes
import signal
import sys
from PIL import Image

SCRIPT_DIR = Path(__file__).parent.resolve()
PORT = 8080
HOST = "0.0.0.0"


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    
    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()


class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
    """Handler that serves hub, civitai, and frameset from one server."""

    def __init__(self, *args, **kwargs):
        self.civitai_cache = None
        self.frameset_cache = None
        super().__init__(*args, directory=str(SCRIPT_DIR), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        
        # === CIVITAI API ENDPOINTS ===
        if path == '/civitai/api/items':
            self.send_json(self.get_civitai_items())
            return
        
        if path == '/civitai/api/stats':
            self.send_json(self.get_civitai_stats())
            return
        
        if path == '/civitai/api/configs':
            self.send_json(self.get_civitai_configs())
            return
        
        if path.startswith('/civitai/api/media/'):
            media_file = unquote(path.split('/civitai/api/media/')[1])
            self.serve_civitai_media(media_file)
            return
        
        # === FRAMESET API ENDPOINTS ===
        if path == '/frameset/api/images':
            self.send_json(self.get_frameset_images())
            return
        
        if path == '/frameset/api/stats':
            self.send_json(self.get_frameset_stats())
            return
        
        if path.startswith('/frameset/api/image/'):
            image_file = unquote(path.split('/frameset/api/image/')[1])
            self.serve_frameset_image(image_file)
            return
        
        # === STATIC FILE ROUTING ===
        # Route /civitai/ to civitai/index.html
        if path == '/civitai/' or path == '/civitai':
            self.serve_file(SCRIPT_DIR / 'civitai' / 'index.html')
            return
        
        # Route /frameset/ to frameset/index.html
        if path == '/frameset/' or path == '/frameset':
            self.serve_file(SCRIPT_DIR / 'frameset' / 'index.html')
            return
        
        # Default: serve normally (including root index.html)
        super().do_GET()

    # ==================== CIVITAI METHODS ====================
    
    def get_civitai_items(self):
        if self.civitai_cache is not None:
            return self.civitai_cache
        
        items = []
        civitai_dir = SCRIPT_DIR / 'civitai'
        metadata_dir = civitai_dir / 'metadata'
        images_dir = civitai_dir / 'images'
        videos_dir = civitai_dir / 'videos'
        
        if metadata_dir.exists():
            for json_file in metadata_dir.glob('civitai_*.json'):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        item_id = data.get('id')
                        
                        # Find media file
                        image_files = list(images_dir.glob(f'civitai_{item_id}.*'))
                        video_files = list(videos_dir.glob(f'civitai_{item_id}.*'))
                        
                        if image_files:
                            data['media_type'] = 'image'
                            data['media_file'] = image_files[0].name
                        elif video_files:
                            data['media_type'] = 'video'
                            data['media_file'] = video_files[0].name
                        else:
                            continue
                        
                        items.append(data)
                except Exception as e:
                    print(f"Error loading {json_file}: {e}")
        
        self.civitai_cache = items
        print(f"✓ Loaded {len(items)} Civitai items")
        return items

    def get_civitai_stats(self):
        items = self.get_civitai_items()
        configs = self.get_civitai_configs()
        
        if not items:
            return {"total": 0, "images": 0, "videos": 0, "avg_votes": 0, "total_votes": 0, "configs": len(configs)}
        
        total = len(items)
        images = sum(1 for item in items if item.get('media_type') == 'image')
        videos = total - images
        
        total_votes = 0
        for item in items:
            stats = item.get('stats', {})
            votes = (stats.get('likeCount', 0) + stats.get('heartCount', 0) +
                    stats.get('laughCount', 0) + stats.get('cryCount', 0))
            total_votes += votes
        
        avg_votes = total_votes / total if total > 0 else 0
        
        return {
            "total": total,
            "images": images,
            "videos": videos,
            "avg_votes": round(avg_votes, 1),
            "total_votes": total_votes,
            "configs": len(configs)
        }

    def get_civitai_configs(self):
        configs = []
        civitai_dir = SCRIPT_DIR / 'civitai'
        
        for json_file in civitai_dir.glob('*.json'):
            if json_file.parent == civitai_dir / 'metadata':
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    config['filename'] = json_file.name
                    configs.append(config)
            except:
                pass
        return configs

    def serve_civitai_media(self, media_file):
        civitai_dir = SCRIPT_DIR / 'civitai'
        
        # Try images first
        media_path = civitai_dir / 'images' / media_file
        if not media_path.exists():
            # Try videos
            media_path = civitai_dir / 'videos' / media_file
        
        if media_path.exists():
            self.serve_file(media_path)
        else:
            self.send_error(404, f"Media not found: {media_file}")

    # ==================== FRAMESET METHODS ====================
    
    def get_frameset_images(self):
        if self.frameset_cache is not None:
            return self.frameset_cache
        
        images = []
        images_dir = SCRIPT_DIR / 'frameset' / 'images'
        
        if images_dir.exists():
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.bmp']
            
            for ext in extensions:
                for img_path in images_dir.glob(ext):
                    try:
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
            
            images.sort(key=lambda x: x['filename'])
        
        self.frameset_cache = images
        print(f"✓ Loaded {len(images)} frameset images")
        return images

    def get_frameset_stats(self):
        images = self.get_frameset_images()
        
        if not images:
            return {"total": 0, "total_size": 0, "avg_width": 0, "avg_height": 0}
        
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

    def serve_frameset_image(self, image_file):
        image_path = SCRIPT_DIR / 'frameset' / 'images' / image_file
        
        if image_path.exists():
            self.serve_file(image_path)
        else:
            self.send_error(404, f"Image not found: {image_file}")

    # ==================== HELPER METHODS ====================
    
    def serve_file(self, file_path):
        """Serve a file with proper headers."""
        try:
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = 'application/octet-stream'
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(data))
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            print(f"Error serving {file_path}: {e}")
            self.send_error(500, str(e))

    def send_json(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def log_message(self, format, *args):
        """Minimal logging."""
        if args and 'api' in str(args[0]):
            print(f"{self.address_string()} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description="Unified Viewer Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port (default: {PORT})")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host (default: {HOST})")
    args = parser.parse_args()

    # Check directories
    print("=" * 60)
    print("🔍 Checking directories...")
    print("=" * 60)
    
    civitai_dir = SCRIPT_DIR / 'civitai'
    frameset_dir = SCRIPT_DIR / 'frameset'
    
    print(f"✓ Civitai:  {civitai_dir} {'[EXISTS]' if civitai_dir.exists() else '[NOT FOUND]'}")
    print(f"✓ Frameset: {frameset_dir} {'[EXISTS]' if frameset_dir.exists() else '[NOT FOUND]'}")
    
    # Create server
    httpd = ReusableTCPServer((args.host, args.port), UnifiedHandler)
    
    # Signal handler
    shutdown_flag = {'triggered': False}
    
    def signal_handler(sig, frame):
        if shutdown_flag['triggered']:
            return
        shutdown_flag['triggered'] = True
        print("\n\n👋 Shutting down...")
        httpd.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n" + "=" * 60)
    print("🎨 Unified Viewer Server")
    print("=" * 60)
    print(f"🌐 Server: http://{args.host}:{args.port}")
    if args.host == "0.0.0.0":
        import socket
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            print(f"🔗 Local:  http://{local_ip}:{args.port}")
        except:
            pass
        print(f"🔗 Localhost: http://localhost:{args.port}")
    print("=" * 60)
    print("\n📍 Available at:")
    print(f"   Hub:       http://localhost:{args.port}/")
    print(f"   Civitai:   http://localhost:{args.port}/civitai/")
    print(f"   Frameset:  http://localhost:{args.port}/frameset/")
    print("=" * 60)
    print("\n✨ Running. Press Ctrl+C to stop.\n")
    
    httpd.serve_forever()


if __name__ == "__main__":
    main()