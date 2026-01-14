#!/bin/bash
cd /home/richard/reddit-image-collect
source venv/bin/activate 2>/dev/null || true
uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
