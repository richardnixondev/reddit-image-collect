"""Media downloader with retry logic and hash-based deduplication."""

import hashlib
import logging
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from .config import DownloadConfig, RateLimitConfig
from .sidecar import generate_filename, write_immich_sidecar

logger = logging.getLogger("reddit_collector")


@dataclass
class DownloadMetadata:
    """Metadata needed for downloading and sidecar generation."""
    subreddit: str
    author: str
    title: str
    score: int
    created_utc: float
    post_id: str
    media_type: str
    gallery_index: Optional[int] = None
    permalink: Optional[str] = None
    flair: Optional[str] = None
    source_type: Optional[str] = None

MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
}


class Downloader:
    """Download manager with retry, rate limiting, and deduplication."""

    def __init__(
        self,
        download_config: DownloadConfig,
        rate_config: RateLimitConfig,
    ):
        self.output_dir = Path(download_config.output_dir)
        self.max_size = download_config.max_file_size_mb * 1024 * 1024
        self.delay = rate_config.download_delay_seconds
        self.flat_structure = download_config.flat_structure
        self.generate_sidecar = download_config.generate_sidecar
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with appropriate headers."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; RedditImageCollector/1.0)",
            "Accept": "image/*,video/*,*/*",
        })
        return session

    def download(
        self,
        url: str,
        metadata: DownloadMetadata,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Download media from URL.
        Returns (local_path, file_hash) or (None, None) on failure.
        """
        time.sleep(self.delay)

        try:
            local_path, file_hash = self._download_with_retry(url, metadata)

            # Generate sidecar file for Immich
            if local_path and self.generate_sidecar:
                write_immich_sidecar(
                    filepath=local_path,
                    subreddit=metadata.subreddit,
                    author=metadata.author,
                    title=metadata.title,
                    score=metadata.score,
                    created_utc=metadata.created_utc,
                    media_type=metadata.media_type,
                    permalink=metadata.permalink,
                    flair=metadata.flair,
                    source_type=metadata.source_type,
                )

            return local_path, file_hash

        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None, None

    def _download_with_retry(
        self,
        url: str,
        metadata: DownloadMetadata,
        max_retries: int = 3,
    ) -> tuple[str, str]:
        """Download with exponential backoff retry."""
        last_error = None

        for attempt in range(max_retries):
            try:
                return self._do_download(url, metadata)

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Download failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)

        raise last_error

    def _do_download(
        self,
        url: str,
        metadata: DownloadMetadata,
    ) -> tuple[str, str]:
        """Perform the actual download."""
        response = self.session.get(url, stream=True, timeout=30)
        response.raise_for_status()

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_size:
            raise ValueError(
                f"File too large: {int(content_length) / 1024 / 1024:.1f}MB"
            )

        ext = self._get_extension(url, response.headers.get("Content-Type"))

        # Determine output directory and filename based on structure mode
        if self.flat_structure:
            # All files in single folder with descriptive names
            self.output_dir.mkdir(parents=True, exist_ok=True)
            filename = generate_filename(
                subreddit=metadata.subreddit,
                author=metadata.author,
                created_utc=metadata.created_utc,
                post_id=metadata.post_id,
                ext=ext,
                gallery_index=metadata.gallery_index,
            )
            local_path = self.output_dir / filename
        else:
            # Original behavior: folder per subreddit
            subreddit_dir = self.output_dir / self._sanitize_name(metadata.subreddit)
            subreddit_dir.mkdir(parents=True, exist_ok=True)
            if metadata.gallery_index is not None:
                filename = f"{metadata.post_id}_{metadata.gallery_index}{ext}"
            else:
                filename = f"{metadata.post_id}{ext}"
            local_path = subreddit_dir / filename

        hasher = hashlib.md5()
        total_size = 0

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > self.max_size:
                        local_path.unlink()
                        raise ValueError("File exceeded max size during download")
                    f.write(chunk)
                    hasher.update(chunk)

        file_hash = hasher.hexdigest()
        logger.debug(f"Downloaded {url} -> {local_path} ({file_hash[:8]})")

        return str(local_path), file_hash

    def _get_extension(
        self, url: str, content_type: Optional[str]
    ) -> str:
        """Determine file extension from URL or Content-Type."""
        if content_type:
            content_type = content_type.split(";")[0].strip()
            if content_type in MIME_TO_EXT:
                return MIME_TO_EXT[content_type]

        parsed = urlparse(url)
        path = parsed.path.lower()

        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm"]:
            if path.endswith(ext):
                return ext if ext != ".jpeg" else ".jpg"

        guess = mimetypes.guess_extension(content_type or "")
        if guess:
            return guess

        return ".jpg"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as directory/filename."""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    def compute_hash(self, filepath: str) -> str:
        """Compute MD5 hash of an existing file."""
        hasher = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
