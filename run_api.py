"""Convenience entry point to launch the FastAPI server."""

import sys
from pathlib import Path
import uvicorn

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from screener.api import app

if __name__ == "__main__":
    print("Starting AI Resume Screener API at http://127.0.0.1:8000 (Docs at http://127.0.0.1:8000/docs)")
    uvicorn.run("screener.api:app", app_dir="src", host="127.0.0.1", port=8000, reload=True)
