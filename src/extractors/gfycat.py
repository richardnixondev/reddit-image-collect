"""Gfycat/Redgifs URL extractor using yt-dlp."""

import logging
from typing import Optional

logger = logging.getLogger("reddit_collector")


def extract_gfycat_url(url: str) -> Optional[str]:
    """
    Extract video URL from Gfycat/Redgifs links.
    Uses yt-dlp for extraction.
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info and "url" in info:
                return info["url"]

            if info and "formats" in info:
                mp4_formats = [
                    f for f in info["formats"]
                    if f.get("ext") == "mp4" and f.get("url")
                ]
                if mp4_formats:
                    best = max(mp4_formats, key=lambda x: x.get("height", 0))
                    return best["url"]

        return None

    except ImportError:
        logger.warning("yt-dlp not installed, cannot extract Gfycat URLs")
        return None
    except Exception as e:
        logger.debug(f"Failed to extract Gfycat URL: {e}")
        return None
