"""Reddit client using public JSON endpoints (no authentication required)."""

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Optional

import requests

from .config import RateLimitConfig, SubredditTarget, UserTarget

logger = logging.getLogger("reddit_collector")

BASE_URL = "https://www.reddit.com"


@dataclass
class Post:
    """Represents a Reddit post."""
    id: str
    subreddit: str
    author: str
    title: str
    url: str
    score: int
    created_utc: float
    over_18: bool
    is_gallery: bool
    preview: Optional[dict]
    media_metadata: Optional[dict]
    permalink: Optional[str] = None  # Reddit permalink
    flair: Optional[str] = None  # Post flair text


class RateLimiter:
    """Simple rate limiter to avoid hitting Reddit's limits."""

    def __init__(self, requests_per_minute: int = 10):
        self.min_interval = 60.0 / requests_per_minute
        self.last_request = 0.0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request = time.time()


class RedditClient:
    """Reddit client using public JSON API (no auth required)."""

    def __init__(self, rate_config: RateLimitConfig):
        self.rate_limiter = RateLimiter(rate_config.requests_per_minute)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })
        logger.info("Reddit client initialized (public JSON API)")

    def _fetch_json(self, url: str, params: dict = None) -> dict:
        """Fetch JSON from Reddit with rate limiting and error handling."""
        self.rate_limiter.wait()

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                return self._fetch_json(url, params)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def _parse_post(self, data: dict) -> Post:
        """Parse raw post data into Post object."""
        post_data = data.get("data", data)

        # Extract flair text (can be in different fields)
        flair = post_data.get("link_flair_text") or post_data.get("flair_text")

        return Post(
            id=post_data.get("id", ""),
            subreddit=post_data.get("subreddit", ""),
            author=post_data.get("author", "[deleted]"),
            title=post_data.get("title", ""),
            url=post_data.get("url", ""),
            score=post_data.get("score", 0),
            created_utc=post_data.get("created_utc", 0),
            over_18=post_data.get("over_18", False),
            is_gallery=post_data.get("is_gallery", False),
            preview=post_data.get("preview"),
            media_metadata=post_data.get("media_metadata"),
            permalink=post_data.get("permalink"),
            flair=flair,
        )

    def get_subreddit_posts(
        self, target: SubredditTarget
    ) -> Iterator[Post]:
        """Fetch posts from a subreddit."""
        logger.info(
            f"Fetching {target.limit} posts from r/{target.name} "
            f"(sort: {target.sort})"
        )

        url = f"{BASE_URL}/r/{target.name}/{target.sort}.json"
        params = {"limit": min(target.limit, 100)}

        if target.sort == "top":
            params["t"] = target.time_filter

        fetched = 0
        after = None

        while fetched < target.limit:
            if after:
                params["after"] = after

            data = self._fetch_json(url, params)
            posts = data.get("data", {}).get("children", [])

            if not posts:
                break

            for post_data in posts:
                if fetched >= target.limit:
                    break
                yield self._parse_post(post_data)
                fetched += 1

            after = data.get("data", {}).get("after")
            if not after:
                break

    def get_user_posts(self, target: UserTarget) -> Iterator[Post]:
        """Fetch posts submitted by a user."""
        logger.info(f"Fetching {target.limit} posts from u/{target.name}")

        url = f"{BASE_URL}/user/{target.name}/submitted.json"
        params = {"limit": min(target.limit, 100)}

        fetched = 0
        after = None

        while fetched < target.limit:
            if after:
                params["after"] = after

            data = self._fetch_json(url, params)
            posts = data.get("data", {}).get("children", [])

            if not posts:
                break

            for post_data in posts:
                if fetched >= target.limit:
                    break
                yield self._parse_post(post_data)
                fetched += 1

            after = data.get("data", {}).get("after")
            if not after:
                break

    def get_post_media_urls(self, post: Post) -> list[tuple[str, str]]:
        """
        Extract all media URLs and types from a post.
        Returns list of (media_url, media_type) tuples.
        For galleries, returns all images. For single media, returns a single-item list.
        """
        url = post.url.lower()

        # Handle galleries - return all images
        if post.is_gallery:
            return self._extract_gallery_urls(post)

        # Single media posts
        if any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return [(post.url, "image")]

        if url.endswith(".gif"):
            return [(post.url, "gif")]

        if "i.redd.it" in url:
            return [(post.url, "image")]

        if "v.redd.it" in url:
            return [(post.url, "video")]

        if "i.imgur.com" in url:
            if ".gifv" in url:
                return [(url.replace(".gifv", ".mp4"), "video")]
            return [(post.url, "image")]

        if "imgur.com" in url and "/a/" not in url and "/gallery/" not in url:
            if not any(url.endswith(ext) for ext in [".jpg", ".png", ".gif", ".mp4"]):
                return [(f"{post.url}.jpg", "image")]
            return [(post.url, "image")]

        if "gfycat.com" in url or "redgifs.com" in url:
            return [(post.url, "video")]

        if post.preview:
            images = post.preview.get("images", [])
            if images:
                return [(images[0]["source"]["url"].replace("&amp;", "&"), "image")]

        return []

    def _extract_gallery_urls(self, post: Post) -> list[tuple[str, str]]:
        """Extract ALL image URLs from a Reddit gallery post."""
        urls = []
        if not post.media_metadata:
            return urls

        for item_id, item in post.media_metadata.items():
            if item.get("status") == "valid" and item.get("e") == "Image":
                source = item.get("s", {})
                if "u" in source:
                    urls.append((source["u"].replace("&amp;", "&"), "image"))

        return urls
