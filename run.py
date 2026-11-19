"""Convenience launcher for the backend.

Run from the repository root:
    python run.py            (http://127.0.0.1:8000)

Equivalent manual command:
    cd backend && uvicorn app.main:app --port 8000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import uvicorn


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
