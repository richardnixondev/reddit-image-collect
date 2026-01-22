"""FastAPI web application for managing Reddit Image Collector."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query, Header
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
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


@app.post("/api/blacklist/subreddits")
async def add_blacklist_subreddit(data: BlacklistItem):
    """Add a subreddit to the blacklist."""
    if not data.value:
        raise HTTPException(status_code=400, detail="Value is required")

    success = config_manager.add_blacklist_subreddit(data.value)
    if not success:
        raise HTTPException(status_code=409, detail="Subreddit already blacklisted")

    return {"message": f"Subreddit '{data.value}' added to blacklist"}


@app.delete("/api/blacklist/subreddits/{subreddit}")
async def remove_blacklist_subreddit(subreddit: str):
    """Remove a subreddit from the blacklist."""
    success = config_manager.remove_blacklist_subreddit(subreddit)
    if not success:
        raise HTTPException(status_code=404, detail="Subreddit not found in blacklist")

    return {"message": f"Subreddit '{subreddit}' removed from blacklist"}


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
    import shutil

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

    # Get disk free space
    try:
        disk_usage = shutil.disk_usage(DOWNLOADS_DIR)
        stats["disk_free_gb"] = round(disk_usage.free / (1024 * 1024 * 1024), 2)
        stats["disk_total_gb"] = round(disk_usage.total / (1024 * 1024 * 1024), 2)
        stats["disk_used_percent"] = round((disk_usage.used / disk_usage.total) * 100, 1)
    except:
        stats["disk_free_gb"] = 0
        stats["disk_total_gb"] = 0
        stats["disk_used_percent"] = 0

    return stats


@app.get("/api/stats/enhanced")
async def get_enhanced_stats():
    """Get enhanced statistics for dashboard."""
    db = Database()
    return db.get_enhanced_stats()


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
    media_type: Optional[str] = None,
    sort: str = Query(default="newest"),
    favorites_only: bool = Query(default=False),
    favorite_authors: bool = Query(default=False)
):
    """Get media files with pagination, filtering and sorting.

    Args:
        sort: 'newest' (default), 'oldest', 'score_high', 'score_low'
    """
    db = Database()

    # Get list of favorite authors (authors with at least one favorited post)
    fav_authors_list = db.get_favorite_authors()
    fav_authors_set = set(a.lower() for a in fav_authors_list) if fav_authors_list else set()

    if favorites_only:
        files = db.get_favorites(limit, offset)
        total = db.count_favorites()
    elif favorite_authors:
        # Get posts from authors who have been favorited
        if fav_authors_list:
            files = db.get_media_by_authors(fav_authors_list, limit, offset, subreddit, media_type)
            total = db.count_media_by_authors(fav_authors_list, subreddit, media_type)
        else:
            files = []
            total = 0
        # Add is_favorite flag
        for f in files:
            f["is_favorite"] = db.is_favorite(f["id"])
    else:
        files = db.get_media_files(limit, offset, subreddit, media_type, sort)
        total = db.get_total_media_count(subreddit, media_type)

        # Add is_favorite flag to each file
        for f in files:
            f["is_favorite"] = db.is_favorite(f["id"])

    # Add is_author_favorite flag to all files
    for f in files:
        author = f.get("author", "")
        f["is_author_favorite"] = author.lower() in fav_authors_set if author else False

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
async def get_media_file(filename: str, range: Optional[str] = Header(None)):
    """Serve a media file with Range request support for video streaming."""
    file_path = DOWNLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_size = file_path.stat().st_size

    # Determine media type
    suffix = file_path.suffix.lower()
    media_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(suffix, 'application/octet-stream')

    # For non-video files or no Range header, return full file
    # Include Accept-Ranges header so browsers know Range requests are supported
    if not range or not suffix in ('.mp4', '.webm', '.mov', '.avi', '.mkv'):
        return FileResponse(
            file_path,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes"}
        )

    # Parse Range header (e.g., "bytes=0-1023")
    try:
        range_str = range.replace("bytes=", "")
        range_parts = range_str.split("-")
        start = int(range_parts[0]) if range_parts[0] else 0
        end = int(range_parts[1]) if range_parts[1] else file_size - 1
    except (ValueError, IndexError):
        start = 0
        end = file_size - 1

    # Ensure valid range
    start = max(0, min(start, file_size - 1))
    end = max(start, min(end, file_size - 1))
    content_length = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            chunk_size = 64 * 1024  # 64KB chunks
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }

    return StreamingResponse(
        iterfile(),
        status_code=206,
        media_type=media_type,
        headers=headers
    )


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

    # Check file extension
    video_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

    # If it's actually an image file (misclassified as video), return it directly
    if video_path.suffix.lower() in image_extensions:
        return FileResponse(video_path, media_type="image/jpeg")

    if video_path.suffix.lower() not in video_extensions:
        raise HTTPException(status_code=400, detail="Not a video file")

    # Generate or get cached thumbnail
    thumb_path = generate_thumbnail(video_path)

    if thumb_path and thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    # If ffmpeg failed, check if file is actually an image (wrong extension)
    # by checking the file magic bytes
    try:
        with open(video_path, 'rb') as f:
            header = f.read(12)
            # JPEG magic bytes
            if header[:2] == b'\xff\xd8':
                return FileResponse(video_path, media_type="image/jpeg")
            # PNG magic bytes
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                return FileResponse(video_path, media_type="image/png")
    except:
        pass

    raise HTTPException(status_code=500, detail="Failed to generate thumbnail")


class DeleteMediaRequest(BaseModel):
    blacklist_author: bool = False
    blacklist_subreddit: bool = False


@app.delete("/api/media/{post_id}")
async def delete_media(post_id: str, blacklist_author: bool = False, blacklist_subreddit: bool = False):
    """Delete a media file and its database record. Optionally add author/subreddit to blacklist."""
    db = Database()
    post = db.get_post(post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Add to blacklist if requested
    blacklisted = []
    if blacklist_author and post.author and post.author not in ("[deleted]", "AutoModerator"):
        config_manager.add_blacklist_author(post.author)
        blacklisted.append(f"author:{post.author}")

    if blacklist_subreddit and post.subreddit:
        config_manager.add_blacklist_subreddit(post.subreddit)
        blacklisted.append(f"subreddit:{post.subreddit}")

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

    result = {"message": f"Media '{post_id}' deleted successfully"}
    if blacklisted:
        result["blacklisted"] = blacklisted
    return result


@app.get("/api/media/{post_id}/info")
async def get_media_info(post_id: str):
    """Get media info for delete confirmation dialog."""
    db = Database()
    post = db.get_post(post_id)

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return {
        "id": post.id,
        "author": post.author,
        "subreddit": post.subreddit,
        "title": post.title,
        "media_type": post.media_type
    }


# Blacklist cleanup endpoints

@app.get("/api/media/blacklist-preview")
async def preview_blacklist_cleanup():
    """Preview how many files would be deleted by cleanup."""
    blacklist = config_manager.get_blacklist()
    authors = blacklist.get("authors", [])
    subreddits = blacklist.get("subreddits", [])

    db = Database()
    author_count = db.count_posts_by_authors(authors) if authors else 0
    subreddit_count = db.count_posts_by_subreddits(subreddits) if subreddits else 0

    return {
        "author_count": author_count,
        "subreddit_count": subreddit_count,
        "total_count": author_count + subreddit_count,
        "authors": authors,
        "subreddits": subreddits
    }


@app.post("/api/media/cleanup-blacklist")
async def cleanup_blacklisted_media():
    """Delete all media from blacklisted authors and subreddits."""
    blacklist = config_manager.get_blacklist()
    authors = blacklist.get("authors", [])
    subreddits = blacklist.get("subreddits", [])

    if not authors and not subreddits:
        return {"deleted": 0, "message": "No authors or subreddits in blacklist"}

    db = Database()
    posts = []

    if authors:
        posts.extend(db.get_posts_by_authors(authors))
    if subreddits:
        posts.extend(db.get_posts_by_subreddits(subreddits))

    # Remove duplicates (in case a post matches both author and subreddit)
    seen_ids = set()
    unique_posts = []
    for post in posts:
        if post.id not in seen_ids:
            seen_ids.add(post.id)
            unique_posts.append(post)

    deleted_count = 0
    errors = []

    for post in unique_posts:
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
        "message": f"Deleted {deleted_count} files from blacklisted authors/subreddits"
    }


# Media type cleanup endpoints

@app.get("/api/media/cleanup-preview")
async def preview_media_cleanup(media_type: str = Query(..., description="video or gif")):
    """Preview how many files of a specific type would be deleted."""
    if media_type not in ("video", "gif"):
        raise HTTPException(status_code=400, detail="media_type must be 'video' or 'gif'")

    db = Database()
    count = db.get_total_media_count(media_type=media_type)

    return {"media_type": media_type, "count": count}


@app.post("/api/media/cleanup-by-type")
async def cleanup_media_by_type(media_type: str = Query(..., description="video or gif")):
    """Delete all media of a specific type (video or gif)."""
    if media_type not in ("video", "gif"):
        raise HTTPException(status_code=400, detail="media_type must be 'video' or 'gif'")

    db = Database()

    # Get all posts of this type
    with db._get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, local_path FROM posts
            WHERE media_type = ? AND local_path IS NOT NULL
            """,
            (media_type,)
        )
        posts = cursor.fetchall()

    deleted_count = 0
    errors = []

    for post_id, local_path in posts:
        try:
            if local_path:
                file_path = Path(local_path)
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
                conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
                conn.commit()

            deleted_count += 1
        except Exception as e:
            errors.append(f"{post_id}: {str(e)}")

    return {
        "deleted": deleted_count,
        "media_type": media_type,
        "errors": errors if errors else None,
        "message": f"Deleted {deleted_count} {media_type} files"
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


# Favorites endpoints

@app.get("/api/favorites")
async def get_favorites(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """Get favorited posts."""
    db = Database()
    favorites = db.get_favorites(limit, offset)
    total = db.count_favorites()

    # Add is_favorite flag to each item
    for fav in favorites:
        fav["is_favorite"] = True

    return {
        "favorites": favorites,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.post("/api/favorites/{post_id}")
async def add_favorite(post_id: str, add_user_to_collection: bool = True):
    """Add a post to favorites. Optionally adds the author to user collection."""
    db = Database()

    # Check if post exists
    post = db.get_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Add to favorites
    added = db.add_favorite(post_id)

    result = {
        "message": f"Post '{post_id}' added to favorites" if added else "Post already in favorites",
        "added": added
    }

    # Add author to user collection if requested and author is valid
    if add_user_to_collection and post.author and post.author not in ("[deleted]", "AutoModerator"):
        user_added = config_manager.add_user(post.author, limit=100)
        if user_added:
            result["user_added"] = post.author
            result["message"] += f". User '{post.author}' added to collection targets."

    return result


@app.delete("/api/favorites/{post_id}")
async def remove_favorite(post_id: str):
    """Remove a post from favorites."""
    db = Database()
    removed = db.remove_favorite(post_id)

    if not removed:
        raise HTTPException(status_code=404, detail="Post not in favorites")

    return {"message": f"Post '{post_id}' removed from favorites"}


@app.get("/api/favorites/authors")
async def get_favorite_authors():
    """Get list of unique authors from favorited posts."""
    db = Database()
    return db.get_favorite_authors()


@app.post("/api/favorites/sync-users")
async def sync_favorite_authors_to_users():
    """Add all authors from favorites to user collection targets."""
    db = Database()
    authors = db.get_favorite_authors()

    added = []
    for author in authors:
        if config_manager.add_user(author, limit=100):
            added.append(author)

    return {
        "synced": len(added),
        "added_users": added,
        "message": f"Added {len(added)} users to collection targets"
    }


# Authors endpoints

@app.get("/api/authors")
async def get_authors(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    favorites_only: bool = Query(default=False),
    sort: str = Query(default="count")
):
    """Get list of authors with stats and thumbnails."""
    db = Database()
    authors = db.get_authors_with_stats(limit, offset, favorites_only, sort)
    total = db.count_authors(favorites_only)

    return {
        "authors": authors,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/authors/{author}/media")
async def get_author_media(
    author: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="newest")
):
    """Get all media from a specific author."""
    db = Database()
    files = db.get_media_by_authors([author], limit, offset, sort=sort)
    total = db.count_media_by_authors([author])

    # Add is_favorite flag
    for f in files:
        f["is_favorite"] = db.is_favorite(f["id"])

    return {
        "files": files,
        "total": total,
        "author": author,
        "limit": limit,
        "offset": offset
    }


# Settings/Configuration endpoints

class DownloadSettings(BaseModel):
    media_types: list[str] = ["image"]
    min_score: int = 1
    skip_nsfw: bool = False
    max_file_size_mb: int = 200
    videos_only_from_favorites: bool = False


@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    config = config_manager.load_config()

    return {
        "download": config.get("download", {}),
        "rate_limit": config.get("rate_limit", {}),
        "blacklist": config.get("blacklist", {})
    }


@app.put("/api/settings/download")
async def update_download_settings(settings: DownloadSettings):
    """Update download settings."""
    config = config_manager.load_config()

    if "download" not in config:
        config["download"] = {}

    config["download"]["media_types"] = settings.media_types
    config["download"]["min_score"] = settings.min_score
    config["download"]["skip_nsfw"] = settings.skip_nsfw
    config["download"]["max_file_size_mb"] = settings.max_file_size_mb
    config["download"]["videos_only_from_favorites"] = settings.videos_only_from_favorites

    config_manager.save_config(config)

    return {"message": "Download settings updated", "settings": settings.dict()}


class RateLimitSettings(BaseModel):
    requests_per_minute: int = 20
    download_delay_seconds: float = 2.0


@app.put("/api/settings/rate-limit")
async def update_rate_limit_settings(settings: RateLimitSettings):
    """Update rate limit settings."""
    config = config_manager.load_config()

    if "rate_limit" not in config:
        config["rate_limit"] = {}

    config["rate_limit"]["requests_per_minute"] = settings.requests_per_minute
    config["rate_limit"]["download_delay_seconds"] = settings.download_delay_seconds

    config_manager.save_config(config)

    return {"message": "Rate limit settings updated", "settings": settings.dict()}
