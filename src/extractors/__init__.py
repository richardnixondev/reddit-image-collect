"""Media URL extractors for various hosts."""

import logging
from typing import Optional
from urllib.parse import urlparse

from .imgur import extract_imgur_url
from .reddit import extract_reddit_video_url
from .gfycat import extract_gfycat_url

logger = logging.getLogger("reddit_collector")


def extract_media_url(url: str, media_type: str) -> tuple[str, str]:
    """
    Extract the actual downloadable media URL from a post URL.
    Returns (final_url, final_media_type).
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if "v.redd.it" in domain:
        video_url = extract_reddit_video_url(url)
        if video_url:
            return video_url, "video"

    if "imgur.com" in domain:
        imgur_url, imgur_type = extract_imgur_url(url)
        if imgur_url:
            return imgur_url, imgur_type

    if "gfycat.com" in domain or "redgifs.com" in domain:
        gfycat_url = extract_gfycat_url(url)
        if gfycat_url:
            return gfycat_url, "video"

    return url, media_type
