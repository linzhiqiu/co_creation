# Civitai Scraper - Quick Reference

## Quick Start

```bash
# Install dependencies
pip install requests

# Run with defaults (10k images, 10k videos, 200+ votes)
python civitai_scraper.py

# Run with custom parameters
python civitai_scraper.py --images 5000 --videos 2000 --min-votes 150
```

## Command Line Arguments

```bash
python civitai_scraper.py [OPTIONS]

Options:
  -i, --images NUM      Number of images to download (default: 10000)
  -v, --videos NUM      Number of videos to download (default: 10000)
  -m, --min-votes NUM   Minimum vote/reaction count (default: 200)
  -n, --name NAME       Custom configuration name (default: auto-generated)
  -k, --api-key KEY     Civitai API key (or use CIVITAI_API_KEY env var)
  -h, --help            Show help message
```

## Examples

### Example 1: Small test run
```bash
python civitai_scraper.py -i 100 -v 50 -m 100 --name test_run
```
Output: `test_run.json` config file

### Example 2: High-quality dataset
```bash
python civitai_scraper.py -i 5000 -v 2000 -m 500 --name high_quality
```
Output: `high_quality.json` config file

### Example 3: With API key
```bash
python civitai_scraper.py -k YOUR_API_KEY -i 10000 -v 5000 -m 200
```

### Example 4: Using environment variable
```bash
export CIVITAI_API_KEY="your_api_key_here"
python civitai_scraper.py -i 8000 -v 3000 -m 250 --name my_dataset
```
Output: `my_dataset.json` config file

### Example 5: Auto-generated name
```bash
python civitai_scraper.py -i 5000 -v 2000 -m 150
```
Output: `civitai_imgs5000_vids2000_votes150_20250123_143022.json`

## Output Files

### Directory Structure
```
./
├── images/                    # Downloaded images
│   └── civitai_<ID>.jpg
├── videos/                    # Downloaded videos  
│   └── civitai_<ID>.mp4
├── metadata/                  # Individual file metadata
│   ├── civitai_<ID>.json
│   └── <config_name>_downloaded_ids.json
└── <config_name>.json        # Run configuration & stats
```

### Configuration File Fields
- `config_name`: Name of this scraping run
- `target_images`: Target number of images
- `target_videos`: Target number of videos
- `min_votes`: Minimum vote threshold used
- `start_time`: When scraping started
- `end_time`: When scraping completed
- `api_key_used`: Whether API key was provided
- `stats`: Download statistics
  - `images_downloaded`: Actual images downloaded
  - `videos_downloaded`: Actual videos downloaded
  - `images_skipped`: Images skipped (already downloaded or target reached)
  - `videos_skipped`: Videos skipped
  - `errors`: Number of errors encountered

## Resume Downloads

To resume a previous run, use the same configuration name:

```bash
# First run (interrupted)
python civitai_scraper.py --name my_dataset -i 10000 -v 5000 -m 200

# Resume later (uses same name)
python civitai_scraper.py --name my_dataset -i 10000 -v 5000 -m 200
```

The script automatically skips already downloaded files.

## API Key Setup

1. Go to https://civitai.com/user/account
2. Generate an API key
3. Use one of these methods:

**Method 1: Command line**
```bash
python civitai_scraper.py --api-key YOUR_KEY
```

**Method 2: Environment variable**
```bash
export CIVITAI_API_KEY="YOUR_KEY"
python civitai_scraper.py
```

**Method 3: Interactive prompt**
Just run the script and enter the key when prompted.

## Tips

- Start with small numbers for testing (e.g., `-i 100 -v 50`)
- Use `--name` for organized datasets
- Lower `--min-votes` if you need more content variety
- API key recommended for better rate limits
- Each run saves progress every 50 downloads
- Videos are rarer than images on Civitai
- Config files help track what you've downloaded

## Common Issues

**Not finding enough videos?**
- Lower the `--min-votes` threshold
- Videos are less common than images on Civitai

**Rate limited?**
- Use an API key (`--api-key`)
- The script includes automatic rate limiting

**Want to run multiple datasets?**
- Use different `--name` for each run
- Each config is tracked separately