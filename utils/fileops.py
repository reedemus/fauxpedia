"""Shared file operations and utilities."""

from pathlib import Path
import base64
import httpx
import logging
import os

logger = logging.getLogger(__name__)


def save_base64_image(base64_data: str, output_path: Path) -> Path:
    """Save base64-encoded image data to file."""
    if ',' in base64_data:
        base64_data = base64_data.split(',', 1)[1]

    image_bytes = base64.b64decode(base64_data)
    output_path.write_bytes(image_bytes)
    logger.info(f"Saved generated image to {output_path}")
    return output_path


def save_image_from_url(url: str, output_path: Path) -> Path:
    """Download and save image from URL."""
    response = httpx.get(url, follow_redirects=True, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    logger.info(f"Saved generated image to {output_path}")
    return output_path


def save_video_from_url(url: str, output_path: Path) -> Path:
    """Download and save video from URL."""
    response = httpx.get(url, follow_redirects=True, timeout=300)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    logger.info(f"Saved generated video to {output_path}")
    return output_path


def capture_webcam_frame(webcam_data: str, temp_dir: Path) -> Path:
    """Save webcam capture data to temporary file."""
    if webcam_data.startswith('data:image'):
        webcam_data = webcam_data.split(',', 1)[1]

    image_bytes = base64.b64decode(webcam_data)

    temp_file = temp_dir / f"webcam_{os.urandom(8).hex()}.jpg"
    temp_file.write_bytes(image_bytes)

    logger.info(f"Saved webcam capture to {temp_file}")
    return temp_file


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, creating if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_file_to(source_path: str, dest_folder: Path, new_name: str) -> Path:
    """Copy a file to a destination folder with a new name."""
    import shutil

    dest_path = dest_folder / new_name
    shutil.copy2(source_path, dest_path)
    logger.info(f"Copied {source_path} to {dest_path}")
    return dest_path
