"""Configuration file manager for CRUD operations."""

from pathlib import Path
from typing import Any

import yaml


CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file."""
    if not CONFIG_PATH.exists():
        return {"targets": {"subreddits": [], "users": []}}

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to YAML file."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_subreddits() -> list[dict[str, Any]]:
    """Get list of configured subreddits."""
    config = load_config()
    return config.get("targets", {}).get("subreddits", [])


def add_subreddit(name: str, limit: int = 100, sort: str = "new") -> bool:
    """Add a new subreddit target."""
    config = load_config()

    if "targets" not in config:
        config["targets"] = {"subreddits": [], "users": []}
    if "subreddits" not in config["targets"]:
        config["targets"]["subreddits"] = []

    # Check if already exists
    for sub in config["targets"]["subreddits"]:
        if sub["name"].lower() == name.lower():
            return False

    config["targets"]["subreddits"].append({
        "name": name,
        "limit": limit,
        "sort": sort
    })

    save_config(config)
    return True


def remove_subreddit(name: str) -> bool:
    """Remove a subreddit target."""
    config = load_config()
    subreddits = config.get("targets", {}).get("subreddits", [])

    original_len = len(subreddits)
    config["targets"]["subreddits"] = [
        s for s in subreddits if s["name"].lower() != name.lower()
    ]

    if len(config["targets"]["subreddits"]) < original_len:
        save_config(config)
        return True
    return False


def get_users() -> list[dict[str, Any]]:
    """Get list of configured users."""
    config = load_config()
    return config.get("targets", {}).get("users", [])


def add_user(name: str, limit: int = 100) -> bool:
    """Add a new user target."""
    config = load_config()

    if "targets" not in config:
        config["targets"] = {"subreddits": [], "users": []}
    if "users" not in config["targets"]:
        config["targets"]["users"] = []

    # Check if already exists
    for user in config["targets"]["users"]:
        if user["name"].lower() == name.lower():
            return False

    config["targets"]["users"].append({
        "name": name,
        "limit": limit
    })

    save_config(config)
    return True


def remove_user(name: str) -> bool:
    """Remove a user target."""
    config = load_config()
    users = config.get("targets", {}).get("users", [])

    original_len = len(users)
    config["targets"]["users"] = [
        u for u in users if u["name"].lower() != name.lower()
    ]

    if len(config["targets"]["users"]) < original_len:
        save_config(config)
        return True
    return False


# Blacklist functions

def _ensure_blacklist(config: dict) -> dict:
    """Ensure blacklist structure exists in config."""
    if "blacklist" not in config:
        config["blacklist"] = {"authors": [], "subreddits": [], "title_keywords": [], "domains": []}
    for key in ["authors", "subreddits", "title_keywords", "domains"]:
        if key not in config["blacklist"]:
            config["blacklist"][key] = []
    return config


def get_blacklist() -> dict[str, list[str]]:
    """Get the full blacklist configuration."""
    config = load_config()
    config = _ensure_blacklist(config)
    return config["blacklist"]


def add_blacklist_author(author: str) -> bool:
    """Add an author to the blacklist and remove from users collection."""
    config = load_config()
    config = _ensure_blacklist(config)

    # Check if already exists (case-insensitive)
    if any(a.lower() == author.lower() for a in config["blacklist"]["authors"]):
        return False

    config["blacklist"]["authors"].append(author)

    # Also remove from users collection if present
    if "targets" in config and "users" in config["targets"]:
        config["targets"]["users"] = [
            u for u in config["targets"]["users"]
            if u.get("name", "").lower() != author.lower()
        ]

    save_config(config)
    return True


def remove_blacklist_author(author: str) -> bool:
    """Remove an author from the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    original_len = len(config["blacklist"]["authors"])
    config["blacklist"]["authors"] = [
        a for a in config["blacklist"]["authors"] if a.lower() != author.lower()
    ]

    if len(config["blacklist"]["authors"]) < original_len:
        save_config(config)
        return True
    return False


def add_blacklist_subreddit(subreddit: str) -> bool:
    """Add a subreddit to the blacklist and remove from subreddits collection."""
    config = load_config()
    config = _ensure_blacklist(config)

    # Check if already exists (case-insensitive)
    if any(s.lower() == subreddit.lower() for s in config["blacklist"]["subreddits"]):
        return False

    config["blacklist"]["subreddits"].append(subreddit)

    # Also remove from subreddits collection if present
    if "targets" in config and "subreddits" in config["targets"]:
        config["targets"]["subreddits"] = [
            s for s in config["targets"]["subreddits"]
            if s.get("name", "").lower() != subreddit.lower()
        ]

    save_config(config)
    return True


def remove_blacklist_subreddit(subreddit: str) -> bool:
    """Remove a subreddit from the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    original_len = len(config["blacklist"]["subreddits"])
    config["blacklist"]["subreddits"] = [
        s for s in config["blacklist"]["subreddits"] if s.lower() != subreddit.lower()
    ]

    if len(config["blacklist"]["subreddits"]) < original_len:
        save_config(config)
        return True
    return False


def add_blacklist_keyword(keyword: str) -> bool:
    """Add a title keyword to the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    # Check if already exists (case-insensitive)
    if any(k.lower() == keyword.lower() for k in config["blacklist"]["title_keywords"]):
        return False

    config["blacklist"]["title_keywords"].append(keyword)
    save_config(config)
    return True


def remove_blacklist_keyword(keyword: str) -> bool:
    """Remove a title keyword from the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    original_len = len(config["blacklist"]["title_keywords"])
    config["blacklist"]["title_keywords"] = [
        k for k in config["blacklist"]["title_keywords"] if k.lower() != keyword.lower()
    ]

    if len(config["blacklist"]["title_keywords"]) < original_len:
        save_config(config)
        return True
    return False


def add_blacklist_domain(domain: str) -> bool:
    """Add a domain to the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    # Normalize domain (remove protocol if present)
    domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")

    # Check if already exists
    if domain in config["blacklist"]["domains"]:
        return False

    config["blacklist"]["domains"].append(domain)
    save_config(config)
    return True


def remove_blacklist_domain(domain: str) -> bool:
    """Remove a domain from the blacklist."""
    config = load_config()
    config = _ensure_blacklist(config)

    # Normalize domain
    domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")

    original_len = len(config["blacklist"]["domains"])
    config["blacklist"]["domains"] = [
        d for d in config["blacklist"]["domains"] if d != domain
    ]

    if len(config["blacklist"]["domains"]) < original_len:
        save_config(config)
        return True
    return False
