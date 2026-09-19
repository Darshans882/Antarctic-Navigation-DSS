from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))
# Vercel reserves the root ``api`` package for this function. Remove it before
# importing the backend so its own route package is resolved from backend/api.
sys.modules.pop("api", None)

from main import app

__all__ = ["app"]
