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
