#!/bin/bash
# Reddit Image Collector - Daily Cron Script

cd /home/richard/reddit-image-collect

# Add local bin to PATH for yt-dlp
export PATH="$HOME/.local/bin:$PATH"

# Run collector with timeout (4 hours max)
timeout 4h python3 -m src.main >> /home/richard/reddit-image-collect/cron.log 2>&1

# Log completion
echo "$(date): Collector finished with exit code $?" >> /home/richard/reddit-image-collect/cron.log
