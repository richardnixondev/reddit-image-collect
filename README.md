# Reddit Media Collector

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-supported-brightgreen.svg)](https://www.docker.com/)

A powerful, self-hosted media collector for Reddit that automatically downloads images, videos, and GIFs from your favorite subreddits and users. Features a built-in web interface for management and seamless integration with [Immich](https://immich.app/) for photo organization.

## Features

- **Multi-source Collection** - Collect from subreddits and user profiles
- **Smart Deduplication** - MD5 hash-based detection prevents duplicate downloads
- **Gallery Support** - Automatically handles Reddit galleries with multiple images
- **Multiple Extractors** - Built-in support for Reddit, Imgur, Gfycat, and Redgifs
- **Immich Integration** - Generates JSON sidecar files with metadata for seamless import
- **Web Dashboard** - Modern web interface for configuration and monitoring
- **Blacklist System** - Filter out unwanted authors, subreddits, keywords, and domains
- **Favorites System** - Mark and filter your favorite posts
- **Video Thumbnails** - Auto-generated thumbnails for video preview in gallery
- **No API Keys Required** - Uses Reddit's public JSON endpoints
- **Docker Support** - Easy deployment with Docker Compose
- **Scheduled Collection** - Cron-ready for automated periodic collection

## Quick Start

### Prerequisites

- Python 3.11 or higher
- FFmpeg (optional, for video thumbnails)
- yt-dlp (optional, for Gfycat/Redgifs support)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/reddit-image-collect.git
   cd reddit-image-collect
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure**
   ```bash
   cp config.yaml.example config.yaml
   # Edit config.yaml with your preferences
   ```

5. **Run the collector**
   ```bash
   python -m src.main
   ```

## Configuration

Create a `config.yaml` file based on the example:

```yaml
targets:
  subreddits:
    - name: "earthporn"
      limit: 100           # Posts per request (max 100)
      sort: "top"          # hot, new, top, rising
      time_filter: "week"  # For "top" sort: hour, day, week, month, year, all

    - name: "pics"
      limit: 50
      sort: "new"

  users:
    - name: "username"
      limit: 100

download:
  output_dir: "./downloads"
  media_types:
    - "image"
    - "video"
    - "gif"
  min_score: 10              # Minimum upvotes required
  skip_nsfw: false           # Skip NSFW content
  max_file_size_mb: 200      # Maximum file size
  flat_structure: true       # All files in single folder
  generate_sidecar: true     # Generate .json for Immich
  videos_only_from_favorites: false  # Only download videos from favorited users

rate_limit:
  requests_per_minute: 20
  download_delay_seconds: 2

logging:
  level: "INFO"
  file: "collector.log"

blacklist:
  authors: []      # Usernames to ignore
  subreddits: []   # Subreddits to ignore
  title_keywords: []
  domains: []
```

## Web Interface

The collector includes a FastAPI-powered web dashboard for easy management.

### Starting the Web Server

```bash
# Using the run script
./run_web.sh

# Or directly with uvicorn
uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

Access the dashboard at `http://localhost:8000`

### Web Features

- **Dashboard** - View collection statistics and manage targets
- **Gallery** - Browse downloaded media with filtering and favorites
- **Settings** - Configure download options and blacklist
- **Collector Control** - Trigger collection runs from the web UI

### Running as a Service (systemd)

```bash
# Copy the service file
sudo cp reddit-collector-web.service /etc/systemd/system/

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable reddit-collector-web
sudo systemctl start reddit-collector-web

# Check status
sudo systemctl status reddit-collector-web

# View logs
sudo journalctl -u reddit-collector-web -f
```

## Docker

### Using Docker Compose

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Docker Configuration

The `docker-compose.yml` mounts the following volumes:
- `./config.yaml` - Configuration file (read-only)
- `./downloads` - Downloaded media
- `./media.db` - SQLite database
- `./collector.log` - Log file

## File Naming Convention

Downloaded files follow a descriptive naming pattern:

```
{subreddit}_{author}_{YYYYMMDD}_{HHmmss}_{post_id}[_{gallery_index}].{ext}
```

**Examples:**
```
earthporn_photographer123_20260118_143052_abc123.jpg
pics_user456_20260118_091523_xyz789_1.jpg  (gallery image 1)
pics_user456_20260118_091523_xyz789_2.jpg  (gallery image 2)
```

## Immich Integration

The collector generates JSON sidecar files compatible with [Immich](https://immich.app/):

```json
{
  "dateTimeOriginal": "2026-01-18T14:30:52+00:00",
  "description": "Post title from Reddit",
  "albums": ["r/earthporn"],
  "tags": ["reddit", "earthporn", "image"],
  "rating": 4,
  "people": ["photographer123"],
  "externalUrl": "https://reddit.com/r/earthporn/comments/abc123/title"
}
```

### Rating System

Ratings are automatically assigned based on post score:
| Score | Rating |
|-------|--------|
| 0-9 | 1 star |
| 10-49 | 2 stars |
| 50-199 | 3 stars |
| 200-999 | 4 stars |
| 1000+ | 5 stars |

### Importing to Immich

Point Immich to your downloads folder as an external library, or use the Immich CLI:

```bash
immich upload --album "Reddit Collection" ./downloads/
```

## Scheduled Collection

### Using Cron

```bash
# Edit crontab
crontab -e

# Add entry (runs every 6 hours)
0 */6 * * * /path/to/reddit-image-collect/run_collector.sh
```

### Example run_collector.sh

```bash
#!/bin/bash
cd /path/to/reddit-image-collect
source venv/bin/activate
export PATH="$HOME/.local/bin:$PATH"  # For yt-dlp
timeout 4h python -m src.main >> cron.log 2>&1
echo "$(date): Collector finished with exit code $?" >> cron.log
```

## API Reference

The web interface exposes a REST API:

### Targets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/subreddits` | List configured subreddits |
| POST | `/api/subreddits` | Add a subreddit |
| DELETE | `/api/subreddits/{name}` | Remove a subreddit |
| GET | `/api/users` | List configured users |
| POST | `/api/users` | Add a user |
| DELETE | `/api/users/{name}` | Remove a user |

### Media
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/media` | List downloaded media (paginated) |
| GET | `/api/media/{id}/info` | Get media details |
| DELETE | `/api/media/{id}` | Delete media file |
| GET | `/api/stats` | Get collection statistics |

### Blacklist
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/blacklist` | Get blacklist configuration |
| POST | `/api/blacklist/authors` | Add author to blacklist |
| DELETE | `/api/blacklist/authors/{name}` | Remove author from blacklist |
| POST | `/api/blacklist/subreddits` | Add subreddit to blacklist |
| DELETE | `/api/blacklist/subreddits/{name}` | Remove subreddit from blacklist |

### Favorites
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/favorites/{post_id}` | Add to favorites |
| DELETE | `/api/favorites/{post_id}` | Remove from favorites |

### Collector
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/collector/run` | Trigger collection run |
| GET | `/api/collector/status` | Get collector status |

## Database Schema

The SQLite database (`media.db`) stores all metadata:

```sql
CREATE TABLE posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT NOT NULL,
    author TEXT,
    title TEXT,
    url TEXT NOT NULL,
    media_url TEXT,
    media_type TEXT,
    score INTEGER DEFAULT 0,
    created_utc REAL,
    downloaded_at TIMESTAMP,
    local_path TEXT,
    file_hash TEXT,
    permalink TEXT,
    source_type TEXT,
    flair TEXT
);

CREATE TABLE favorites (
    post_id TEXT PRIMARY KEY,
    favorited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

## Troubleshooting

### Videos saving as .html
**Cause:** yt-dlp not installed or not in PATH

**Solution:**
```bash
pip install yt-dlp
export PATH="$HOME/.local/bin:$PATH"
```

### Rate limited (429 errors)
**Cause:** Too many requests to Reddit

**Solution:** Increase `download_delay_seconds` or decrease `requests_per_minute` in config

### Incomplete galleries
**Cause:** Gallery metadata not available from Reddit API

**Solution:** Verify the post still exists on Reddit

### Web interface not starting
**Cause:** Port already in use or missing dependencies

**Solution:**
```bash
# Check if port is in use
lsof -i :8000

# Reinstall dependencies
pip install -r requirements.txt
```

## Project Structure

```
reddit-image-collect/
├── src/
│   ├── __init__.py
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration dataclasses
│   ├── database.py       # SQLite wrapper
│   ├── downloader.py     # Download with retry
│   ├── reddit_client.py  # Reddit API client
│   ├── sidecar.py        # Immich sidecar generation
│   ├── extractors/       # URL extractors
│   │   ├── __init__.py
│   │   ├── reddit.py
│   │   ├── imgur.py
│   │   └── gfycat.py
│   └── web/              # Web interface
│       ├── app.py
│       ├── config_manager.py
│       └── templates/
├── downloads/            # Downloaded media
├── config.yaml           # Configuration
├── media.db              # SQLite database
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for personal use only. Please respect Reddit's [Terms of Service](https://www.redditinc.com/policies/user-agreement) and the content creators' rights. Do not use this tool to redistribute copyrighted content.

## Acknowledgments

- [Reddit](https://reddit.com) for their public JSON API
- [Immich](https://immich.app/) for the excellent self-hosted photo management
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video extraction support
