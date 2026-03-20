"""Background task for video generation."""

from pathlib import Path
from gradio_client import handle_file
import logging
import asyncio

from api.huggingface_client import HuggingFaceClient
from utils.fileops import copy_file_to

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Manages video generation via HuggingFace space."""

    def __init__(
        self,
        hf_client: HuggingFaceClient,
        gen_folder: Path
    ):
        self.hf = hf_client
        self.gen_folder = gen_folder
        self.current_job = None
        self.current_id = None

    async def generate_video_for_image(
        self,
        image_path: Path,
        video_prompt: str
    ):
        """Start video generation from image and prompt."""
        job = self.hf.generate_video(
            input_image=str(image_path),
            prompt=video_prompt
        )
        self.current_job = job
        self.current_id = image_path.stem
        logger.info(f"Started video generation for {image_path}")
        return job

    async def wait_for_completion(self) -> Path:
        """Poll for video generation completion."""
        if not self.current_job:
            raise ValueError("No video generation in progress")

        while True:
            status = self.current_job.status()
            logger.info(f"Video gen status: {status.code.name}")

            if status.code.name == "FINISHED":
                return self._save_result()
            elif status.code.name == "CANCELLED":
                raise ValueError("Video generation was cancelled")

            await asyncio.sleep(5)

    def _save_result(self) -> Path:
        """Save generated video file."""
        result_dict, _ = self.current_job.result()
        vid_file_path = result_dict.get("video")

        if vid_file_path:
            return copy_file_to(vid_file_path, self.gen_folder, f"{self.current_id}.mp4")

        raise ValueError("Video result not found in job output")
