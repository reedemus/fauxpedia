"""Static file serving routes."""

from pathlib import Path
from fasthtml.common import *
import os


def static_files(fname: str, ext: str) -> FileResponse:
    """Serve static files from the static directory."""
    static_dir = Path(__file__).parent.parent / "static"
    return FileResponse(f"{static_dir}/{fname}.{ext}")
