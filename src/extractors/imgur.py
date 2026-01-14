"""Imgur URL extractor."""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("reddit_collector")


def extract_imgur_url(url: str) -> tuple[Optional[str], str]:
    """
    Extract direct image/video URL from Imgur links.
    Returns (url, media_type) or (None, "image") on failure.
    """
    parsed = urlparse(url)
    path = parsed.path

    if "i.imgur.com" in parsed.netloc:
        if path.endswith(".gifv"):
            return url.replace(".gifv", ".mp4"), "video"
        return url, "image"

    if "/a/" in path or "/gallery/" in path:
        logger.debug(f"Imgur albums not supported: {url}")
        return None, "image"

    match = re.search(r"/(\w+)(?:\.\w+)?$", path)
    if match:
        image_id = match.group(1)
        return f"https://i.imgur.com/{image_id}.jpg", "image"

    return None, "image"
