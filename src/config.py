"""Configuration loader and validator."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SubredditTarget:
    name: str
    limit: int = 50
    sort: str = "hot"
    time_filter: str = "all"


@dataclass
class UserTarget:
    name: str
    limit: int = 30


@dataclass
class TargetsConfig:
    subreddits: list[SubredditTarget] = field(default_factory=list)
    users: list[UserTarget] = field(default_factory=list)


@dataclass
class DownloadConfig:
    output_dir: str = "./downloads"
    media_types: list[str] = field(default_factory=lambda: ["image", "video", "gif"])
    min_score: int = 10
    skip_nsfw: bool = True
    max_file_size_mb: int = 100
    flat_structure: bool = True  # All files in single folder
    generate_sidecar: bool = True  # Generate .json sidecar for Immich
    videos_only_from_favorites: bool = False  # Only download videos from favorited users


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 10
    download_delay_seconds: float = 2.0


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = "collector.log"


@dataclass
class BlacklistConfig:
    authors: list[str] = field(default_factory=list)
    subreddits: list[str] = field(default_factory=list)
    title_keywords: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)


@dataclass
class Config:
    targets: TargetsConfig
    download: DownloadConfig
    rate_limit: RateLimitConfig
    logging: LoggingConfig
    blacklist: BlacklistConfig = field(default_factory=BlacklistConfig)


def load_config(config_path: str = "config.yaml") -> Config:
    """Load and validate configuration from YAML file."""
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please copy config.yaml.example to config.yaml and customize."
        )

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    targets_data = data.get("targets", {})
    subreddits = [
        SubredditTarget(
            name=s["name"],
            limit=s.get("limit", 50),
            sort=s.get("sort", "hot"),
            time_filter=s.get("time_filter", "all"),
        )
        for s in targets_data.get("subreddits", [])
    ]
    users = [
        UserTarget(name=u["name"], limit=u.get("limit", 30))
        for u in targets_data.get("users", [])
    ]
    targets = TargetsConfig(subreddits=subreddits, users=users)

    if not targets.subreddits and not targets.users:
        raise ValueError("No targets configured. Add subreddits or users to config.")

    download_data = data.get("download", {})
    download = DownloadConfig(
        output_dir=download_data.get("output_dir", "./downloads"),
        media_types=download_data.get("media_types", ["image", "video", "gif"]),
        min_score=download_data.get("min_score", 10),
        skip_nsfw=download_data.get("skip_nsfw", True),
        max_file_size_mb=download_data.get("max_file_size_mb", 100),
        flat_structure=download_data.get("flat_structure", True),
        generate_sidecar=download_data.get("generate_sidecar", True),
        videos_only_from_favorites=download_data.get("videos_only_from_favorites", False),
    )

    rate_data = data.get("rate_limit", {})
    rate_limit = RateLimitConfig(
        requests_per_minute=rate_data.get("requests_per_minute", 10),
        download_delay_seconds=rate_data.get("download_delay_seconds", 2.0),
    )

    log_data = data.get("logging", {})
    logging_config = LoggingConfig(
        level=log_data.get("level", "INFO"),
        file=log_data.get("file", "collector.log"),
    )

    blacklist_data = data.get("blacklist", {})
    blacklist = BlacklistConfig(
        authors=[a.lower() for a in blacklist_data.get("authors", [])],
        subreddits=[s.lower() for s in blacklist_data.get("subreddits", [])],
        title_keywords=[k.lower() for k in blacklist_data.get("title_keywords", [])],
        domains=[d.lower() for d in blacklist_data.get("domains", [])],
    )

    return Config(
        targets=targets,
        download=download,
        rate_limit=rate_limit,
        logging=logging_config,
        blacklist=blacklist,
    )


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Configure logging based on config."""
    logger = logging.getLogger("reddit_collector")
    logger.setLevel(getattr(logging, config.level.upper()))

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if config.file:
        file_handler = logging.FileHandler(config.file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
