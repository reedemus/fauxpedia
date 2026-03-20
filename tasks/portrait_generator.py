"""Background task for portrait (AI image) generation."""

from pathlib import Path
from starlette.background import BackgroundTask
import logging

from api.imagga_client import ImgBBClient
from api.wavespeed_client import WaveSpeedClient
from utils.fileops import save_base64_image, save_image_from_url

logger = logging.getLogger(__name__)


class PortraitGenerator:
    """Manages the AI portrait generation workflow."""

    def __init__(
        self,
        imgbb_client: ImgBBClient,
        wavespeed_client: WaveSpeedClient,
        gen_folder: Path
    ):
        self.imgbb = imgbb_client
        self.wavespeed = wavespeed_client
        self.gen_folder = gen_folder

    def start_generation(self, photo_path: Path, prompt: str) -> tuple[str, BackgroundTask]:
        """Start portrait generation and return request_id with background task."""
        image_url = self.imgbb.upload_photo(str(photo_path))
        request_id = self.wavespeed.generate_image(image_url, prompt)

        task = BackgroundTask(
            self._complete_generation,
            request_id=request_id
        )
        return request_id, task

    def _complete_generation(self, request_id: str) -> None:
        """Complete generation in background."""
        try:
            download_url = self.wavespeed.poll_result(request_id)
            if download_url:
                self._save_result(request_id, download_url)
                logger.info(f"Portrait generation completed for {request_id}")
        except Exception as e:
            logger.error(f"Background portrait generation failed for {request_id}: {e}")

    def _save_result(self, request_id: str, url: str) -> Path:
        """Save generated image to file."""
        output_path = self.gen_folder / f"{request_id}.jpeg"
        if "data:image/jpeg;base64" in url:
            return save_base64_image(url, output_path)
        elif ".jpeg" in url:
            return save_image_from_url(url, output_path)
        else:
            logger.error(f"Unknown format for result: {url}")
            return output_path
