#!/usr/bin/env python3
"""
Civitai Media Scraper
Downloads images and videos from Civitai.com using their official API
Filters for content with 200+ user reactions (likes/hearts)
"""

import requests
import json
import time
import os
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import mimetypes

class CivitaiScraper:
    """Scraper for downloading images and videos from Civitai API"""
    
    def __init__(self, api_key: Optional[str] = None, config_name: Optional[str] = None, 
                 target_images: int = 10000, target_videos: int = 10000, min_votes: int = 200,
                 max_pages: int = 100):
        """
        Initialize the scraper
        
        Args:
            api_key: Your Civitai API key (get from https://civitai.com/user/account)
            config_name: Name for this scraping configuration
            target_images: Target number of images
            target_videos: Target number of videos
            min_votes: Minimum vote/reaction count
            max_pages: Maximum API pages to fetch
        """
        self.base_url = "https://civitai.com/api/v1"
        self.api_key = api_key
        self.session = requests.Session()
        
        # Set up headers
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "CivitaiScraper/1.0"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Store configuration
        self.config = {
            "config_name": config_name,
            "target_images": target_images,
            "target_videos": target_videos,
            "min_votes": min_votes,
            "max_pages": max_pages,
            "start_time": datetime.now().isoformat(),
            "api_key_used": bool(api_key)
        }
        
        # Generate config filename if not provided
        if not config_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            config_name = f"civitai_imgs{target_images}_vids{target_videos}_votes{min_votes}_{timestamp}"
        
        self.config_name = config_name
        
        # Create download directories in current folder
        self.image_dir = Path("images")
        self.video_dir = Path("videos")
        self.metadata_dir = Path("metadata")
        
        for directory in [self.image_dir, self.video_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Config file path
        self.config_file = Path(f"{config_name}.json")
        
        # Track downloads
        self.downloaded_ids = self._load_downloaded_ids()
        self.stats = {
            "images_downloaded": 0,
            "videos_downloaded": 0,
            "images_skipped": 0,
            "videos_skipped": 0,
            "errors": 0
        }
    
    def _load_downloaded_ids(self) -> set:
        """Load previously downloaded IDs to avoid duplicates"""
        ids_file = self.metadata_dir / f"{self.config_name}_downloaded_ids.json"
        if ids_file.exists():
            with open(ids_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def _save_downloaded_ids(self):
        """Save downloaded IDs to file"""
        ids_file = self.metadata_dir / f"{self.config_name}_downloaded_ids.json"
        with open(ids_file, 'w') as f:
            json.dump(list(self.downloaded_ids), f)
    
    def _save_config(self):
        """Save configuration and stats to JSON file"""
        config_data = {
            **self.config,
            "stats": self.stats,
            "end_time": datetime.now().isoformat(),
            "output_directories": {
                "images": str(self.image_dir),
                "videos": str(self.video_dir),
                "metadata": str(self.metadata_dir)
            },
            "downloaded_ids_file": str(self.metadata_dir / f"{self.config_name}_downloaded_ids.json")
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"\n✓ Configuration saved to: {self.config_file}")
    
    def fetch_images(self, limit_per_request: int = 200, max_requests: int = 100) -> List[Dict]:
        """
        Fetch images from Civitai API with minimum reaction count
        
        Args:
            limit_per_request: Number of items per API request (max 200)
            max_requests: Maximum number of API requests to make (prevents infinite loops)
        
        Returns:
            List of image/video metadata dictionaries
        """
        min_reactions = self.config["min_votes"]
        all_items = []
        next_cursor = None
        request_count = 0
        consecutive_low_votes = 0
        
        print(f"Fetching items with {min_reactions}+ reactions...")
        print(f"Note: Will fetch up to {max_requests} pages to find enough content\n")
        
        while request_count < max_requests:
            # Build URL with parameters
            params = {
                "limit": limit_per_request,
                "sort": "Most Reactions",  # Sort by reactions to get highly-voted content first
                "period": "AllTime"
            }
            
            if next_cursor:
                params["cursor"] = next_cursor
            
            try:
                # Make API request
                url = f"{self.base_url}/images"
                response = self.session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                metadata = data.get("metadata", {})
                
                request_count += 1
                items_meeting_criteria = 0
                
                # Filter items by reaction count
                for item in items:
                    stats = item.get("stats", {})
                    total_reactions = (
                        stats.get("likeCount", 0) + 
                        stats.get("heartCount", 0) +
                        stats.get("laughCount", 0) +
                        stats.get("cryCount", 0)
                    )
                    
                    if total_reactions >= min_reactions:
                        all_items.append(item)
                        items_meeting_criteria += 1
                
                # Track if we're getting low-quality content
                if items_meeting_criteria < len(items) * 0.1:  # Less than 10% meet criteria
                    consecutive_low_votes += 1
                else:
                    consecutive_low_votes = 0
                
                print(f"Request {request_count}/{max_requests}: Fetched {len(items)} items, "
                      f"{items_meeting_criteria} meet criteria (≥{min_reactions} votes), "
                      f"Total collected: {len(all_items)}")
                
                # CRITICAL: Stop early if we have enough items for our targets
                target_total = self.config["target_images"] + self.config["target_videos"]
                if len(all_items) >= target_total:
                    print(f"\n✓ Collected enough items ({len(all_items)} >= {target_total} target)")
                    print(f"  Stopping API requests early to save bandwidth and time")
                    break
                
                # Stop if we've had 5 consecutive pages with very few qualifying items
                # This prevents wasting time on low-quality content
                if consecutive_low_votes >= 5:
                    print(f"\n⚠ Stopping: Found very few items meeting criteria in last {consecutive_low_votes} pages")
                    print(f"Consider lowering --min-votes to find more content")
                    break
                
                # Check for next page
                next_cursor = metadata.get("nextCursor")
                next_page = metadata.get("nextPage")
                
                if not next_cursor and not next_page:
                    print("\nℹ No more pages available from API")
                    break
                
                # Rate limiting - be nice to the API
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data: {e}")
                self.stats["errors"] += 1
                # Wait longer on error
                time.sleep(5)
                break
        
        print(f"\nTotal items fetched: {len(all_items)}")
        print(f"API requests made: {request_count}/{max_requests}")
        return all_items
    
    def _is_video(self, url: str, item: Dict) -> bool:
        """
        Determine if the item is a video based on URL and metadata
        
        Args:
            url: The media URL
            item: The item metadata
        
        Returns:
            True if video, False if image
        """
        # Check URL extension
        url_lower = url.lower()
        video_extensions = ['.mp4', '.webm', '.mov', '.avi', '.mkv']
        if any(url_lower.endswith(ext) for ext in video_extensions):
            return True
        
        # Check metadata for video indicators
        meta = item.get("meta")
        if meta and isinstance(meta, dict):
            if "duration" in meta or "fps" in meta:
                return True
        
        # Check MIME type if available
        mime_type, _ = mimetypes.guess_type(url)
        if mime_type and mime_type.startswith('video/'):
            return True
        
        return False
    
    def download_media(self, item: Dict) -> Optional[str]:
        """
        Download a single media file (image or video)
        
        Args:
            item: Item metadata from API
        
        Returns:
            Path to downloaded file, or None if failed
        """
        item_id = item.get("id")
        url = item.get("url")
        
        if not url or not item_id:
            print(f"⚠ Skipping item {item_id or 'unknown'}: missing URL or ID")
            return None
        
        # Skip if already downloaded
        if str(item_id) in self.downloaded_ids:
            return None
        
        try:
            # Determine if video or image
            is_video = self._is_video(url, item)
            
            # Set directory and update stats
            if is_video:
                media_dir = self.video_dir
                media_type = "video"
            else:
                media_dir = self.image_dir
                media_type = "image"
            
            # Extract file extension from URL
            ext = Path(url).suffix
            if not ext or ext == '':
                ext = ".jpeg" if not is_video else ".mp4"
            
            # Create filename with Civitai ID
            filename = f"civitai_{item_id}{ext}"
            filepath = media_dir / filename
            
            # Download file
            print(f"Downloading {media_type} {item_id}...")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Save file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Save metadata (handle None values gracefully)
            metadata_file = self.metadata_dir / f"civitai_{item_id}.json"
            try:
                with open(metadata_file, 'w') as f:
                    json.dump(item, f, indent=2)
            except (TypeError, ValueError) as e:
                print(f"⚠ Warning: Could not save metadata for {item_id}: {e}")
            
            # Update tracking
            self.downloaded_ids.add(str(item_id))
            
            if is_video:
                self.stats["videos_downloaded"] += 1
            else:
                self.stats["images_downloaded"] += 1
            
            print(f"✓ Downloaded {media_type}: {filename}")
            
            # Rate limiting
            time.sleep(0.5)
            
            return str(filepath)
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error downloading {item_id}: {e}")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            print(f"✗ Unexpected error with {item_id}: {e}")
            self.stats["errors"] += 1
            return None
    
    def run(self):
        """
        Main scraping function
        """
        target_images = self.config["target_images"]
        target_videos = self.config["target_videos"]
        min_votes = self.config["min_votes"]
        
        print("="*60)
        print("Civitai Media Scraper")
        print("="*60)
        print(f"Configuration: {self.config_name}")
        print(f"Target: {target_images} images, {target_videos} videos")
        print(f"Minimum votes: {min_votes}")
        print(f"Max pages: {self.config['max_pages']} (~{self.config['max_pages'] * 200} items)")
        print(f"API Key configured: {bool(self.api_key)}")
        print(f"Output directories:")
        print(f"  - Images: ./{self.image_dir}")
        print(f"  - Videos: ./{self.video_dir}")
        print(f"  - Metadata: ./{self.metadata_dir}")
        print("="*60)
        
        start_time = datetime.now()
        
        # Fetch items from API
        max_pages = self.config["max_pages"]
        items = self.fetch_images(max_requests=max_pages)
        
        if not items:
            print("\n⚠ No items found matching criteria")
            self._save_config()
            return
        
        print(f"\n{'='*60}")
        print(f"Starting downloads...")
        print(f"{'='*60}\n")
        
        # Download media files
        for idx, item in enumerate(items, 1):
            # Check if we've reached targets
            if (self.stats["images_downloaded"] >= target_images and 
                self.stats["videos_downloaded"] >= target_videos):
                print(f"\n✓ Reached target for both images and videos!")
                break
            
            # Skip if we already have enough of this type
            is_video = self._is_video(item.get("url", ""), item)
            if is_video and self.stats["videos_downloaded"] >= target_videos:
                self.stats["videos_skipped"] += 1
                continue
            if not is_video and self.stats["images_downloaded"] >= target_images:
                self.stats["images_skipped"] += 1
                continue
            
            # Download the item
            result = self.download_media(item)
            
            # Periodic progress update
            if idx % 100 == 0:
                print(f"\n--- Progress Update ---")
                print(f"Processed: {idx}/{len(items)}")
                print(f"Images: {self.stats['images_downloaded']}/{target_images}")
                print(f"Videos: {self.stats['videos_downloaded']}/{target_videos}")
                print(f"Errors: {self.stats['errors']}")
                print("-" * 40 + "\n")
            
            # Save progress periodically
            if idx % 50 == 0:
                self._save_downloaded_ids()
                self._save_config()
        
        # Final save
        self._save_downloaded_ids()
        
        # Update config with end time
        self.config["end_time"] = datetime.now().isoformat()
        
        # Print final statistics
        end_time = datetime.now()
        duration = end_time - start_time
        
        print("\n" + "="*60)
        print("SCRAPING COMPLETE")
        print("="*60)
        print(f"Configuration: {self.config_name}")
        print(f"Duration: {duration}")
        print(f"\nDownloaded:")
        print(f"  - Images: {self.stats['images_downloaded']}/{target_images}")
        print(f"  - Videos: {self.stats['videos_downloaded']}/{target_videos}")
        print(f"  - Total: {self.stats['images_downloaded'] + self.stats['videos_downloaded']}")
        print(f"\nSkipped:")
        print(f"  - Images: {self.stats['images_skipped']}")
        print(f"  - Videos: {self.stats['videos_skipped']}")
        print(f"\nErrors: {self.stats['errors']}")
        print(f"\nFiles saved to:")
        print(f"  - Images: {self.image_dir}")
        print(f"  - Videos: {self.video_dir}")
        print(f"  - Metadata: {self.metadata_dir}")
        print(f"\nConfiguration saved to: {self.config_file}")
        print("="*60)
        
        # Save final configuration
        self._save_config()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download images and videos from Civitai with specified vote count",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download 5000 images and 2000 videos with 150+ votes
  python civitai_scraper.py --images 5000 --videos 2000 --min-votes 150
  
  # Use a custom configuration name
  python civitai_scraper.py --name my_dataset --images 1000 --videos 500 --min-votes 100
  
  # Provide API key via command line
  python civitai_scraper.py --api-key YOUR_KEY --images 10000 --videos 10000
  
  # Use environment variable for API key
  export CIVITAI_API_KEY=your_key_here
  python civitai_scraper.py --images 5000 --videos 5000 --min-votes 200
        """
    )
    
    parser.add_argument(
        '--images', '-i',
        type=int,
        default=10000,
        help='Number of images to download (default: 10000)'
    )
    
    parser.add_argument(
        '--videos', '-v',
        type=int,
        default=10000,
        help='Number of videos to download (default: 10000)'
    )
    
    parser.add_argument(
        '--min-votes', '-m',
        type=int,
        default=200,
        help='Minimum vote/reaction count (default: 200)'
    )
    
    parser.add_argument(
        '--name', '-n',
        type=str,
        default=None,
        help='Custom name for this configuration (default: auto-generated with timestamp)'
    )
    
    parser.add_argument(
        '--api-key', '-k',
        type=str,
        default="97d1e0355b45d52b9eaf5b5b1af6d72a",
        help='Civitai API key (or use CIVITAI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=50000,
        help='Maximum API pages to fetch (default: 50000, ~200 items per page)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Get API key from args or environment variable
    api_key = args.api_key or os.environ.get('CIVITAI_API_KEY')
    
    # If no API key provided, prompt for it or continue without
    if not api_key:
        print("\n" + "="*60)
        print("⚠ WARNING: No API key configured!")
        print("="*60)
        print("You can still run the scraper, but you'll have lower rate limits.")
        print("\nTo get an API key:")
        print("1. Create an account at https://civitai.com")
        print("2. Go to https://civitai.com/user/account")
        print("3. Generate an API key")
        print("\nYou can provide it via:")
        print("  - Command line: --api-key YOUR_KEY")
        print("  - Environment: export CIVITAI_API_KEY=YOUR_KEY")
        print("  - Interactive prompt (below)")
        print("="*60)
        
        user_key = input("\nEnter your API key (or press Enter to continue without one): ").strip()
        if user_key:
            api_key = user_key
    
    # Display configuration
    print("\n" + "="*60)
    print("CONFIGURATION")
    print("="*60)
    print(f"Images to download: {args.images}")
    print(f"Videos to download: {args.videos}")
    print(f"Minimum votes: {args.min_votes}")
    print(f"Max pages to fetch: {args.max_pages} (~{args.max_pages * 200} items max)")
    if args.name:
        print(f"Configuration name: {args.name}")
    else:
        print(f"Configuration name: (auto-generated)")
    print(f"API key: {'✓ Provided' if api_key else '✗ Not provided'}")
    print("="*60)
    
    # Confirm to proceed
    response = input("\nProceed with download? [Y/n]: ").strip().lower()
    if response and response not in ['y', 'yes']:
        print("Download cancelled.")
        return
    
    # Initialize scraper with all parameters
    scraper = CivitaiScraper(
        api_key=api_key,
        config_name=args.name,
        target_images=args.images,
        target_videos=args.videos,
        min_votes=args.min_votes,
        max_pages=args.max_pages
    )
    
    # Run scraper
    scraper.run()


if __name__ == "__main__":
    main()