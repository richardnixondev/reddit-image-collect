"""Sidecar file generator for Immich integration."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("reddit_collector")


def write_immich_sidecar(
    filepath: str,
    subreddit: str,
    author: str,
    title: str,
    score: int,
    created_utc: float,
    media_type: str,
    permalink: Optional[str] = None,
    flair: Optional[str] = None,
    source_type: Optional[str] = None,
) -> str:
    """
    Write a JSON sidecar file for Immich.

    Immich reads .json sidecar files with the same base name as the media file.
    This enables proper date sorting, album creation, and metadata display.

    Args:
        filepath: Path to the media file
        subreddit: Source subreddit name
        author: Post author username
        title: Post title
        score: Reddit score/upvotes
        created_utc: Unix timestamp of post creation
        media_type: Type of media (image, video, gif)
        permalink: Reddit permalink (optional)
        flair: Post flair (optional)
        source_type: 'subreddit' or 'user' (optional)

    Returns:
        Path to the created sidecar file
    """
    sidecar_path = f"{filepath}.json"

    # Convert timestamp to ISO format
    dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    date_iso = dt.isoformat()

    # Build tags list
    tags = ["reddit", subreddit, media_type]
    if flair:
        tags.append(flair)
    if source_type:
        tags.append(f"from_{source_type}")

    # Calculate rating (1-5 scale based on score)
    # 0-10: 1, 10-50: 2, 50-200: 3, 200-1000: 4, 1000+: 5
    if score >= 1000:
        rating = 5
    elif score >= 200:
        rating = 4
    elif score >= 50:
        rating = 3
    elif score >= 10:
        rating = 2
    else:
        rating = 1

    # Build sidecar structure
    sidecar = {
        "dateTimeOriginal": date_iso,
        "description": title[:500] if title else "",  # Limit description length
        "albums": [f"r/{subreddit}"],
        "tags": tags,
        "rating": rating,
    }

    # Add people (author) if not deleted
    if author and author not in ("[deleted]", "AutoModerator"):
        sidecar["people"] = [author]

    # Add external URL if permalink available
    if permalink:
        sidecar["externalUrl"] = f"https://reddit.com{permalink}"

    # Write sidecar file
    with open(sidecar_path, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)

    logger.debug(f"Created sidecar: {sidecar_path}")
    return sidecar_path


def generate_filename(
    subreddit: str,
    author: str,
    created_utc: float,
    post_id: str,
    ext: str,
    gallery_index: Optional[int] = None,
) -> str:
    """
    Generate a descriptive filename with metadata embedded.

    Format: {subreddit}_{author}_{YYYYMMDD}_{HHmmss}_{post_id}[_{index}].{ext}

    Examples:
        CuteGirlsinPanties_username123_20260113_235346_1qb8nil_1.jpg
        FitNakedGirls_deleted_20260113_001814_1qbbrev.mp4

    Args:
        subreddit: Source subreddit name
        author: Post author username
        created_utc: Unix timestamp of post creation
        post_id: Reddit post ID
        ext: File extension (including dot)
        gallery_index: Index for gallery items (optional)

    Returns:
        Generated filename
    """
    # Convert timestamp to datetime
    dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    date_str = dt.strftime("%Y%m%d_%H%M%S")

    # Sanitize components
    safe_sub = _sanitize_name(subreddit)[:30]
    safe_author = _sanitize_name(author)[:20]

    # Handle deleted/unknown authors
    if not safe_author or safe_author in ("deleted", "AutoModerator"):
        safe_author = "unknown"

    # Build filename
    if gallery_index is not None:
        filename = f"{safe_sub}_{safe_author}_{date_str}_{post_id}_{gallery_index}{ext}"
    else:
        filename = f"{safe_sub}_{safe_author}_{date_str}_{post_id}{ext}"

    return filename


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use in filename."""
    if not name:
        return ""
    # Replace brackets and special chars, keep alphanumeric and basic punctuation
    return "".join(c if c.isalnum() or c in "-_" else "" for c in name)
