"""Application configuration and settings validation."""

from dataclasses import dataclass
from pathlib import Path
import os
import logging


@dataclass
class AppSettings:
    """Application configuration container."""
    gen_folder: Path
    log_file: Path
    api_timeout: int
    portrait_poll_interval: int
    video_poll_interval: int
    anthropic_model: str
    image_size: str

    @classmethod
    def from_env(cls) -> 'AppSettings':
        """Load settings from environment variables."""
        gen_folder = Path(os.environ.get("GEN_FOLDER", "./generated"))
        gen_folder.mkdir(parents=True, exist_ok=True)

        return cls(
            gen_folder=gen_folder,
            log_file=Path(os.environ.get("LOG_FILE", "main.log")),
            api_timeout=int(os.environ.get("API_TIMEOUT", "60")),
            portrait_poll_interval=int(os.environ.get("PORTRAIT_POLL_INTERVAL", "1")),
            video_poll_interval=int(os.environ.get("VIDEO_POLL_INTERVAL", "2")),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            image_size=os.environ.get("IMAGE_SIZE", "1024*1536"),
        )


def initialize_logging(log_file: Path) -> None:
    """Configure application logging."""
    if log_file.exists():
        log_file.unlink()
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logging.getLogger(__name__).info("Logging initialized")
