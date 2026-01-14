"""FastAPI web application for managing Reddit Image Collector."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import config_manager


app = FastAPI(title="Reddit Image Collector", version="1.0.0")

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
