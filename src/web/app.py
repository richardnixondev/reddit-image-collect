"""FastAPI web application for managing Reddit Image Collector."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import config_manager

# Import database
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.database import Database


app = FastAPI(title="Reddit Image Collector", version="1.0.0")

# Downloads directory for serving media files
DOWNLOADS_DIR = Path(__file__).parent.parent.parent / "downloads"

# Thumbnails directory
THUMBS_DIR = DOWNLOADS_DIR / ".thumbs"
THUMBS_DIR.mkdir(exist_ok=True)

# Collector state
collector_status = {
    "running": False,
    "last_run": None,
    "last_result": None
}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class SubredditCreate(BaseModel):
    name: str
    limit: int = 100
    sort: str = "new"


class UserCreate(BaseModel):
    name: str
    limit: int = 100


class BlacklistItem(BaseModel):
    value: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main page."""
    subreddits = config_manager.get_subreddits()
    users = config_manager.get_users()
    blacklist = config_manager.get_blacklist()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "subreddits": subreddits,
        "users": users,
        "blacklist": blacklist
    })


@app.get("/api/config")
async def get_config():
    """Get full configuration."""
    return config_manager.load_config()


@app.get("/api/subreddits")
async def list_subreddits():
    """List all subreddits."""
    return config_manager.get_subreddits()


@app.post("/api/subreddits")
async def add_subreddit(data: SubredditCreate):
    """Add a new subreddit."""
    if not data.name:
        raise HTTPException(status_code=400, detail="Name is required")

    success = config_manager.add_subreddit(data.name, data.limit, data.sort)
    if not success:
        raise HTTPException(status_code=409, detail="Subreddit already exists")

    return {"message": f"Subreddit '{data.name}' added successfully"}


@app.delete("/api/subreddits/{name}")
async def delete_subreddit(name: str):
    """Remove a subreddit."""
    success = config_manager.remove_subreddit(name)
    if not success:
        raise HTTPException(status_code=404, detail="Subreddit not found")

    return {"message": f"Subreddit '{name}' removed successfully"}


@app.get("/api/users")
async def list_users():
    """List all users."""
    return config_manager.get_users()


@app.post("/api/users")
async def add_user(data: UserCreate):
    """Add a new user."""
    if not data.name:
        raise HTTPException(status_code=400, detail="Name is required")

    success = config_manager.add_user(data.name, data.limit)
    if not success:
        raise HTTPException(status_code=409, detail="User already exists")

    return {"message": f"User '{data.name}' added successfully"}


@app.delete("/api/users/{name}")
async def delete_user(name: str):
    """Remove a user."""
    success = config_manager.remove_user(name)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": f"User '{name}' removed successfully"}


# Blacklist endpoints

@app.get("/api/blacklist")
async def get_blacklist():
    """Get full blacklist configuration."""
    return config_manager.get_blacklist()


@app.post("/api/blacklist/authors")
async def add_blacklist_author(data: BlacklistItem):
    """Add an author to the blacklist."""
    if not data.value:
        raise HTTPException(status_code=400, detail="Value is required")

    success = config_manager.add_blacklist_author(data.value)
    if not success:
        raise HTTPException(status_code=409, detail="Author already blacklisted")

    return {"message": f"Author '{data.value}' added to blacklist"}


@app.delete("/api/blacklist/authors/{author}")
async def remove_blacklist_author(author: str):
    """Remove an author from the blacklist."""
    success = config_manager.remove_blacklist_author(author)
    if not success:
        raise HTTPException(status_code=404, detail="Author not found in blacklist")

    return {"message": f"Author '{author}' removed from blacklist"}


@app.post("/api/blacklist/keywords")
async def add_blacklist_keyword(data: BlacklistItem):
    """Add a title keyword to the blacklist."""
    if not data.value:
        raise HTTPException(status_code=400, detail="Value is required")

    success = config_manager.add_blacklist_keyword(data.value)
    if not success:
        raise HTTPException(status_code=409, detail="Keyword already blacklisted")

    return {"message": f"Keyword '{data.value}' added to blacklist"}


@app.delete("/api/blacklist/keywords/{keyword:path}")
async def remove_blacklist_keyword(keyword: str):
    """Remove a title keyword from the blacklist."""
    success = config_manager.remove_blacklist_keyword(keyword)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found in blacklist")

    return {"message": f"Keyword '{keyword}' removed from blacklist"}


@app.post("/api/blacklist/domains")
async def add_blacklist_domain(data: BlacklistItem):
    """Add a domain to the blacklist."""
    if not data.value:
        raise HTTPException(status_code=400, detail="Value is required")

    success = config_manager.add_blacklist_domain(data.value)
    if not success:
        raise HTTPException(status_code=409, detail="Domain already blacklisted")

    return {"message": f"Domain '{data.value}' added to blacklist"}


@app.delete("/api/blacklist/domains/{domain:path}")
async def remove_blacklist_domain(domain: str):
    """Remove a domain from the blacklist."""
    success = config_manager.remove_blacklist_domain(domain)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found in blacklist")

    return {"message": f"Domain '{domain}' removed from blacklist"}


# Statistics endpoints

@app.get("/api/stats")
async def get_stats():
    """Get collection statistics."""
    db = Database()
    stats = db.get_stats()

    # Calculate disk usage
    total_size = 0
    file_count = 0
    if DOWNLOADS_DIR.exists():
        for f in DOWNLOADS_DIR.iterdir():
            if f.is_file() and not f.name.endswith('.json'):
                total_size += f.stat().st_size
                file_count += 1

    stats["disk_size_bytes"] = total_size
    stats["disk_size_mb"] = round(total_size / (1024 * 1024), 2)
    stats["disk_size_gb"] = round(total_size / (1024 * 1024 * 1024), 2)
    stats["file_count"] = file_count

    return stats


@app.get("/api/stats/recent")
async def get_recent_downloads(limit: int = Query(default=10, le=50)):
    """Get recent downloads."""
    db = Database()
    return db.get_recent_downloads(limit)


# Media browser endpoints

@app.get("/api/media")
async def get_media_files(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    subreddit: Optional[str] = None,
    media_type: Optional[str] = None
):
    """Get media files with pagination and filtering."""
    db = Database()
    files = db.get_media_files(limit, offset, subreddit, media_type)
    total = db.get_total_media_count(subreddit, media_type)

    return {
        "files": files,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/media/subreddits")
async def get_media_subreddits():
    """Get list of subreddits with downloaded content."""
    db = Database()
    return db.get_all_subreddits()


@app.get("/api/media/file/{filename:path}")
async def get_media_file(filename: str):
    """Serve a media file."""
    file_path = DOWNLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


def generate_thumbnail(video_path: Path) -> Optional[Path]:
    """Generate a thumbnail for a video file using ffmpeg."""
    thumb_path = THUMBS_DIR / f"{video_path.name}.jpg"

    # If thumbnail already exists, return it
    if thumb_path.exists():
        return thumb_path

    try:
        # Use ffmpeg to extract a frame at 1 second
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
                "-q:v", "2",
                str(thumb_path)
            ],
            capture_output=True,
            timeout=30
        )

        if result.returncode == 0 and thumb_path.exists():
            return thumb_path

        # If failed at 1s, try at 0s (for very short videos)
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", "00:00:00",
                "-vframes", "1",
                "-vf", "scale=320:320:force_original_aspect_ratio=decrease",
                "-q:v", "2",
                str(thumb_path)
            ],
            capture_output=True,
            timeout=30
        )

        if result.returncode == 0 and thumb_path.exists():
            return thumb_path

        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


@app.get("/api/media/thumb/{filename:path}")
async def get_video_thumbnail(filename: str):
    """Get or generate a thumbnail for a video file."""
    video_path = DOWNLOADS_DIR / filename

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if it's a video file
    video_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}
    if video_path.suffix.lower() not in video_extensions:
        raise HTTPException(status_code=400, detail="Not a video file")

    # Generate or get cached thumbnail
    thumb_path = generate_thumbnail(video_path)

    if thumb_path and thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    raise HTTPException(status_code=500, detail="Failed to generate thumbnail")


@app.delete("/api/media/{post_id}")
async def delete_media(post_id: str):
    """Delete a media file and its database record."""
    db = Database()
    post = db.get_post(post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Delete the file if it exists
    if post.local_path:
        file_path = Path(post.local_path)
        if file_path.exists():
            file_path.unlink()

        # Also delete sidecar JSON if exists
        sidecar_path = file_path.with_suffix(file_path.suffix + '.json')
        if sidecar_path.exists():
            sidecar_path.unlink()

        # Delete thumbnail if exists
        thumb_path = THUMBS_DIR / f"{file_path.name}.jpg"
        if thumb_path.exists():
            thumb_path.unlink()

    # Remove from database
    with db._get_connection() as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()

    return {"message": f"Media '{post_id}' deleted successfully"}


# Blacklist cleanup endpoints

@app.get("/api/media/blacklist-preview")
async def preview_blacklist_cleanup():
    """Preview how many files would be deleted by cleanup."""
    blacklist = config_manager.get_blacklist()
    authors = blacklist.get("authors", [])

    if not authors:
        return {"count": 0, "authors": []}

    db = Database()
    count = db.count_posts_by_authors(authors)

    return {"count": count, "authors": authors}


@app.post("/api/media/cleanup-blacklist")
async def cleanup_blacklisted_media():
    """Delete all media from blacklisted authors."""
    blacklist = config_manager.get_blacklist()
    authors = blacklist.get("authors", [])

    if not authors:
        return {"deleted": 0, "message": "No authors in blacklist"}

    db = Database()
    posts = db.get_posts_by_authors(authors)

    deleted_count = 0
    errors = []

    for post in posts:
        try:
            # Delete media file
            if post.local_path:
                file_path = Path(post.local_path)
                if file_path.exists():
                    file_path.unlink()

                # Delete sidecar
                sidecar_path = file_path.with_suffix(file_path.suffix + '.json')
                if sidecar_path.exists():
                    sidecar_path.unlink()

                # Delete thumbnail
                thumb_path = THUMBS_DIR / f"{file_path.name}.jpg"
                if thumb_path.exists():
                    thumb_path.unlink()

            # Remove from database
            with db._get_connection() as conn:
                conn.execute("DELETE FROM posts WHERE id = ?", (post.id,))
                conn.commit()

            deleted_count += 1
        except Exception as e:
            errors.append(f"{post.id}: {str(e)}")

    return {
        "deleted": deleted_count,
        "errors": errors if errors else None,
        "message": f"Deleted {deleted_count} files from blacklisted authors"
    }


def run_collector():
    """Run the collector in background."""
    from datetime import datetime

    collector_status["running"] = True
    collector_status["last_run"] = datetime.now().isoformat()

    try:
        project_dir = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["python3", "-m", "src.main"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=14400  # 4 hours max
        )
        collector_status["last_result"] = "success" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        collector_status["last_result"] = "timeout"
    except Exception as e:
        collector_status["last_result"] = f"error: {str(e)}"
    finally:
        collector_status["running"] = False


@app.get("/api/collector/status")
async def get_collector_status():
    """Get collector status."""
    return collector_status


@app.post("/api/collector/run")
async def trigger_collector(background_tasks: BackgroundTasks):
    """Trigger the collector to run."""
    if collector_status["running"]:
        raise HTTPException(status_code=409, detail="Collector is already running")

    background_tasks.add_task(run_collector)
    return {"message": "Collector started"}
