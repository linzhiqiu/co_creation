# Civitai Media Scraper

A Python script to download images and videos from Civitai.com using their official API, filtering for highly-voted content (200+ reactions).

## Features

- ✅ Uses official Civitai REST API (no web scraping needed)
- ✅ Downloads both images and videos
- ✅ Filters by minimum reaction count (likes + hearts)
- ✅ Saves complete metadata including generation parameters
- ✅ Tracks unique Civitai IDs for each file
- ✅ Resume capability (tracks downloaded IDs)
- ✅ Rate limiting to respect API limits
- ✅ Progress tracking and statistics

## Prerequisites

1. **Python 3.7+**
2. **Civitai Account** (free registration)
3. **API Key** (optional but recommended for higher rate limits)

## Getting Your API Key

1. Create an account at [https://civitai.com](https://civitai.com)
2. Log in and go to your account settings: [https://civitai.com/user/account](https://civitai.com/user/account)
3. Find the "API Keys" section
4. Click "Add API Key" or "Generate API Key"
5. Copy the generated key
6. Keep it secure (don't share it publicly)

## Installation

```bash
# Clone or download the script
# Navigate to the directory

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
# Default: 10,000 images, 10,000 videos, 200+ votes
python civitai_scraper.py
```

### Command Line Arguments

```bash
# Custom targets
python civitai_scraper.py --images 5000 --videos 2000 --min-votes 150

# Short form arguments
python civitai_scraper.py -i 1000 -v 500 -m 100

# Specify a custom configuration name
python civitai_scraper.py --name my_dataset --images 5000 --videos 2000

# Provide API key via command line
python civitai_scraper.py --api-key YOUR_API_KEY_HERE --images 10000

# Show help
python civitai_scraper.py --help
```

### Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--images` | `-i` | Number of images to download | 10000 |
| `--videos` | `-v` | Number of videos to download | 10000 |
| `--min-votes` | `-m` | Minimum vote/reaction count | 200 |
| `--name` | `-n` | Custom configuration name | Auto-generated |
| `--api-key` | `-k` | Civitai API key | None |

### Configure API Key

**Option 1: Command line argument**
```bash
python civitai_scraper.py --api-key YOUR_API_KEY_HERE -i 5000 -v 2000
```

**Option 2: Environment variable**
```bash
export CIVITAI_API_KEY="your_api_key_here"
python civitai_scraper.py --images 5000 --videos 2000
```

**Option 3: Interactive prompt**
```bash
python civitai_scraper.py
# Script will prompt for API key if not provided
```

## Output Structure

```
current_directory/
├── images/
│   ├── civitai_123456.jpeg
│   ├── civitai_123457.png
│   └── ...
├── videos/
│   ├── civitai_789012.mp4
│   ├── civitai_789013.webm
│   └── ...
├── metadata/
│   ├── civitai_123456.json
│   ├── civitai_123457.json
│   ├── civitai_imgs5000_vids2000_votes150_20250123_143022_downloaded_ids.json
│   └── ...
└── civitai_imgs5000_vids2000_votes150_20250123_143022.json  # Configuration file
```

### Configuration File

Each run creates a unique JSON configuration file in the current directory. The filename includes:
- Number of images target
- Number of videos target  
- Minimum vote count
- Timestamp

Example filename: `civitai_imgs10000_vids5000_votes200_20250123_143022.json`

Or with custom name: `my_dataset.json`

**Configuration file contents:**
```json
{
  "config_name": "civitai_imgs5000_vids2000_votes150_20250123_143022",
  "target_images": 5000,
  "target_videos": 2000,
  "min_votes": 150,
  "start_time": "2025-01-23T14:30:22.123456",
  "end_time": "2025-01-23T16:45:10.654321",
  "api_key_used": true,
  "stats": {
    "images_downloaded": 5000,
    "videos_downloaded": 1847,
    "images_skipped": 234,
    "videos_skipped": 0,
    "errors": 12
  },
  "output_directories": {
    "images": "images",
    "videos": "videos",
    "metadata": "metadata"
  },
  "downloaded_ids_file": "metadata/civitai_imgs5000_vids2000_votes150_20250123_143022_downloaded_ids.json"
}
```

## Metadata Format

Each media file has a corresponding JSON file with complete metadata:

```json
{
  "id": 469632,
  "url": "https://imagecache.civitai.com/...",
  "hash": "UKHU@6H?_ND*_3M{t84o^+%MD%xuXSxasAt7",
  "width": 1024,
  "height": 1536,
  "nsfw": false,
  "nsfwLevel": "None",
  "createdAt": "2023-04-11T15:33:12.500Z",
  "postId": 138779,
  "stats": {
    "cryCount": 0,
    "laughCount": 0,
    "likeCount": 245,
    "heartCount": 180,
    "commentCount": 12
  },
  "meta": {
    "Size": "512x768",
    "seed": 234871805,
    "Model": "Meina",
    "steps": 35,
    "prompt": "...",
    "sampler": "DPM++ SDE Karras",
    "cfgScale": 7,
    "negativePrompt": "..."
  },
  "username": "CreatorName"
}
```

## Important Notes

### API Limits

- **With API Key**: Higher rate limits (exact limits not publicly documented)
- **Without API Key**: Lower rate limits
- The script includes rate limiting (1-2 seconds between requests) to be respectful

### Rate Limit Strategy

If you hit rate limits:
1. The script will automatically wait and retry
2. Progress is saved regularly (every 50 downloads)
3. You can stop and resume later - already downloaded files are tracked

### Distinguishing Images vs Videos

The script uses multiple methods to identify videos:
- File extension (.mp4, .webm, .mov, etc.)
- Metadata fields (duration, fps)
- MIME type checking

### Content Filtering

- `min_reactions=200` filters for content with 200+ total reactions (likes + hearts + laughs + cries)
- Results are sorted by "Most Reactions" to get highly-voted content first
- NSFW content is included by default (you can modify the script to filter it)

## Troubleshooting

### "Rate limit exceeded" errors
- Add/use an API key via `--api-key` or environment variable
- Increase sleep time between requests in the code
- Run script during off-peak hours

### "Connection timeout" errors
- Check your internet connection
- Increase timeout values in the code
- Try again later (Civitai servers may be busy)

### Not enough videos found
- Videos are less common than images on Civitai
- Try lowering `--min-votes` threshold
- The images API endpoint includes both images and videos, but videos are rarer

### Script stops unexpectedly
- Check the error messages in terminal
- Progress is saved in `metadata/<config_name>_downloaded_ids.json`
- Simply run the script again with the same `--name` to resume

### Resume a previous run
```bash
# Use the exact same configuration name to resume
python civitai_scraper.py --name my_dataset --images 5000 --videos 2000 --min-votes 150
```
The script will skip already downloaded files automatically.

## Advanced Customization

### Run multiple configurations

```bash
# Dataset 1: High quality images with many votes
python civitai_scraper.py --name high_quality --images 2000 --videos 500 --min-votes 500

# Dataset 2: More variety with lower threshold
python civitai_scraper.py --name variety --images 5000 --videos 2000 --min-votes 100

# Dataset 3: Video-focused collection
python civitai_scraper.py --name videos_only --images 100 --videos 5000 --min-votes 200
```

Each run creates its own configuration file and tracks downloads separately.

### Filter by specific parameters

Modify the `fetch_images()` method to add more filters:

```python
params = {
    "limit": limit_per_request,
    "sort": "Most Reactions",
    "period": "Month",        # AllTime, Year, Month, Week, Day
    "nsfw": False,            # Filter out NSFW content
    "username": "someuser",   # Filter by specific creator
}
```

### Change sort order

In the `fetch_images()` method, change the sort parameter:
- `"Most Reactions"` (default) - Highest voted first
- `"Most Comments"` - Most discussed
- `"Newest"` - Most recent

## API Endpoints Used

- **Images**: `GET https://civitai.com/api/v1/images`
  - Returns both images and videos
  - Supports filtering by reactions, time period, creator, etc.
  - Uses cursor-based pagination

## Legal & Ethical Considerations

- ✅ This script uses Civitai's official public API
- ✅ Respects rate limits with built-in delays
- ⚠️ Check individual content licenses before commercial use
- ⚠️ Respect creator rights and Civitai's Terms of Service
- ⚠️ Be aware that some content may be NSFW

## Credits

- Civitai API: [https://developer.civitai.com](https://developer.civitai.com)
- API Documentation: [https://github.com/civitai/civitai/wiki/REST-API-Reference](https://github.com/civitai/civitai/wiki/REST-API-Reference)

## License

This script is provided as-is for educational purposes. Users are responsible for complying with Civitai's Terms of Service and respecting content creators' rights.