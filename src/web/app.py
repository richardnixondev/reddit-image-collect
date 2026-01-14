"""FastAPI web application for managing Reddit Image Collector."""

import asyncio
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import config_manager


app = FastAPI(title="Reddit Image Collector", version="1.0.0")

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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main page."""
    subreddits = config_manager.get_subreddits()
    users = config_manager.get_users()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "subreddits": subreddits,
        "users": users
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
