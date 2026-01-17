"""Reddit Image Collector - Main entry point."""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from .config import Config, load_config, setup_logging
from .database import Database, PostRecord
from .downloader import Downloader, DownloadMetadata
from .extractors import extract_media_url
from .reddit_client import Post, RedditClient


@dataclass
class CollectionStats:
    processed: int = 0
    downloaded: int = 0
    skipped_exists: int = 0
    skipped_no_media: int = 0
    skipped_score: int = 0
    skipped_nsfw: int = 0
    skipped_type: int = 0
    skipped_blacklist: int = 0
    errors: int = 0


def should_download_post(post: Post, config: Config) -> tuple[bool, str]:
    """Check post-level filters (NSFW, score, blacklist). Returns (should_download, reason)."""
    if config.download.skip_nsfw and post.over_18:
        return False, "nsfw"

    if post.score < config.download.min_score:
        return False, "score"

    # Check blacklist: author
    if post.author and post.author.lower() in config.blacklist.authors:
        return False, "blacklist_author"

    # Check blacklist: subreddit
    if post.subreddit and post.subreddit.lower() in config.blacklist.subreddits:
        return False, "blacklist_subreddit"

    # Check blacklist: title keywords
    title_lower = post.title.lower() if post.title else ""
    for keyword in config.blacklist.title_keywords:
        if keyword in title_lower:
            return False, "blacklist_keyword"

    return True, ""


def is_domain_blacklisted(url: str, blacklist_domains: list[str]) -> bool:
    """Check if URL domain is in blacklist."""
    if not url or not blacklist_domains:
        return False

    url_lower = url.lower()
    for domain in blacklist_domains:
        if domain in url_lower:
            return True
    return False


def should_download_media(media_type: str, config: Config, author: str = None, db: Database = None) -> bool:
    """Check if media type is allowed. For videos, optionally check if author is favorited."""
    if media_type not in config.download.media_types:
        return False

    # If videos_only_from_favorites is enabled, check for video/gif
    if config.download.videos_only_from_favorites and media_type in ("video", "gif"):
        if not author or not db:
            return False
        # Check if author has any favorited posts
        favorite_authors = db.get_favorite_authors()
        if author.lower() not in [a.lower() for a in favorite_authors]:
            return False

    return True


def process_post(
    post: Post,
    client: RedditClient,
    db: Database,
    downloader: Downloader,
    config: Config,
    stats: CollectionStats,
    logger,
    source_type: str = "subreddit",
) -> None:
    """Process a single post: extract media URLs, download all, and save to DB."""
    stats.processed += 1

    # Check post-level filters first
    should_dl, reason = should_download_post(post, config)
    if not should_dl:
        if reason == "nsfw":
            stats.skipped_nsfw += 1
        elif reason == "score":
            stats.skipped_score += 1
        elif reason.startswith("blacklist"):
            stats.skipped_blacklist += 1
        logger.debug(f"Skipping {post.id}: {reason}")
        return

    # Get all media URLs (supports galleries)
    media_urls = client.get_post_media_urls(post)

    if not media_urls:
        stats.skipped_no_media += 1
        logger.debug(f"Skipping {post.id}: no media found")
        return

    # Process each media item
    for idx, (media_url, media_type) in enumerate(media_urls):
        # Generate unique ID for gallery items
        if len(media_urls) > 1:
            item_id = f"{post.id}_{idx + 1}"
        else:
            item_id = post.id

        # Skip if already in database
        if db.post_exists(item_id):
            stats.skipped_exists += 1
            logger.debug(f"Skipping {item_id}: already in database")
            continue

        # Check media type filter (including videos_only_from_favorites)
        if not should_download_media(media_type, config, post.author, db):
            stats.skipped_type += 1
            logger.debug(f"Skipping {item_id}: media type {media_type} not allowed")
            continue

        final_url, final_type = extract_media_url(media_url, media_type)

        # Check blacklist: domain
        if is_domain_blacklisted(final_url, config.blacklist.domains):
            stats.skipped_blacklist += 1
            logger.debug(f"Skipping {item_id}: blacklisted domain in {final_url}")
            continue

        # Determine gallery index
        gallery_index = idx + 1 if len(media_urls) > 1 else None

        record = PostRecord(
            id=item_id,
            subreddit=post.subreddit,
            author=post.author,
            title=post.title,
            url=post.url,
            media_url=final_url,
            media_type=final_type,
            score=post.score,
            created_utc=post.created_utc,
            downloaded_at=None,
            local_path=None,
            file_hash=None,
            permalink=post.permalink,
            source_type=source_type,
            flair=post.flair,
        )
        db.add_post(record)

        # Create metadata for download
        download_meta = DownloadMetadata(
            subreddit=post.subreddit,
            author=post.author,
            title=post.title,
            score=post.score,
            created_utc=post.created_utc,
            post_id=post.id,
            media_type=final_type,
            gallery_index=gallery_index,
            permalink=post.permalink,
            flair=post.flair,
            source_type=source_type,
        )

        local_path, file_hash = downloader.download(final_url, download_meta)

        if local_path and file_hash:
            existing = db.hash_exists(file_hash)
            if existing:
                logger.info(f"Duplicate detected for {item_id}, keeping existing")
                os.remove(local_path)
                stats.skipped_exists += 1
                continue

            db.mark_downloaded(item_id, local_path, file_hash)
            stats.downloaded += 1
            if len(media_urls) > 1:
                logger.info(
                    f"Downloaded: {item_id} from r/{post.subreddit} ({final_type}) "
                    f"[{idx + 1}/{len(media_urls)}]"
                )
            else:
                logger.info(
                    f"Downloaded: {item_id} from r/{post.subreddit} ({final_type})"
                )
        else:
            stats.errors += 1


def collect(config: Config, logger) -> CollectionStats:
    """Main collection loop."""
    stats = CollectionStats()

    db = Database()
    client = RedditClient(config.rate_limit)
    downloader = Downloader(config.download, config.rate_limit)

    for target in config.targets.subreddits:
        logger.info(f"Processing subreddit: r/{target.name}")
        try:
            for post in client.get_subreddit_posts(target):
                process_post(
                    post, client, db, downloader, config, stats, logger,
                    source_type="subreddit"
                )
        except Exception as e:
            logger.error(f"Error processing r/{target.name}: {e}")
            stats.errors += 1

    for target in config.targets.users:
        logger.info(f"Processing user: u/{target.name}")
        try:
            for post in client.get_user_posts(target):
                process_post(
                    post, client, db, downloader, config, stats, logger,
                    source_type="user"
                )
        except Exception as e:
            logger.error(f"Error processing u/{target.name}: {e}")
            stats.errors += 1

    return stats


def print_report(stats: CollectionStats, db: Database, logger) -> None:
    """Print collection summary."""
    db_stats = db.get_stats()

    logger.info("=" * 50)
    logger.info("Collection Complete!")
    logger.info("=" * 50)
    logger.info(f"Posts processed: {stats.processed}")
    logger.info(f"New downloads: {stats.downloaded}")
    logger.info(f"Skipped (already exists): {stats.skipped_exists}")
    logger.info(f"Skipped (no media): {stats.skipped_no_media}")
    logger.info(f"Skipped (low score): {stats.skipped_score}")
    logger.info(f"Skipped (NSFW): {stats.skipped_nsfw}")
    logger.info(f"Skipped (media type): {stats.skipped_type}")
    logger.info(f"Skipped (blacklist): {stats.skipped_blacklist}")
    logger.info(f"Errors: {stats.errors}")
    logger.info("-" * 50)
    logger.info(f"Total in database: {db_stats['total_posts']}")
    logger.info(f"Total downloaded: {db_stats['downloaded']}")

    if db_stats.get("by_source"):
        logger.info("By source:")
        for source, count in sorted(db_stats["by_source"].items()):
            logger.info(f"  {source}: {count}")

    if db_stats.get("by_type"):
        logger.info("By type:")
        for mtype, count in sorted(db_stats["by_type"].items()):
            logger.info(f"  {mtype}: {count}")


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Collect images and videos from Reddit"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    logger = setup_logging(config.logging)
    logger.info(f"Reddit Image Collector starting at {datetime.now()}")

    if args.dry_run:
        logger.info("DRY RUN MODE - no files will be downloaded")
        config.download.media_types = []

    try:
        stats = collect(config, logger)
        print_report(stats, Database(), logger)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
