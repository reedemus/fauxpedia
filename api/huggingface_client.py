"""HuggingFace video generation client via gradio-client."""

from gradio_client import Client, handle_file
from gradio_client.client import Job
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HuggingFaceClient:
    """Client for HuggingFace video generation space."""

    def __init__(self, space_url: Optional[str] = None, api_key: Optional[str] = None):
        self.space_url = space_url or os.environ.get("HF_SPACE_URL")
        self.api_key = api_key or os.environ.get("HFACE_API_KEY")
        self.client = None

    def _get_client(self) -> Client:
        """Get or create gradio client."""
        if not self.client:
            if not self.space_url:
                raise ValueError("HF_SPACE_URL not set")
            self.client = Client(self.space_url, token=self.api_key)
        return self.client

    def generate_video(
        self,
        input_image: str,
        prompt: str,
        steps: int = 6,
        duration_seconds: float = 5.0,
        guidance_scale: float = 1.0,
        guidance_scale_2: float = 1.0,
        seed: int = 42,
        randomize_seed: bool = True,
        negative_prompt: str = "low quality, blurry, deformed, distorted, disfigured, ugly, duplicate, watermark, text, error, cropped, worst quality",
        api_name: str = "/generate_video"
    ) -> Job:
        """Generate video from image and prompt.

        Args:
            input_image: Path or URL to input image
            prompt: Video generation prompt
            steps: Number of inference steps
            duration_seconds: Duration of generated video
            guidance_scale: CFG scale for generation
            guidance_scale_2: Secondary CFG scale
            seed: Random seed for reproducibility
            randomize_seed: Whether to randomize seed
            negative_prompt: Negative prompt for things to avoid
            api_name: Gradio API endpoint name

        Returns:
            Job object for tracking generation progress
        """
        client = self._get_client()

        job = client.submit(
            input_image=handle_file(input_image),
            prompt=prompt,
            steps=steps,
            negative_prompt=negative_prompt,
            duration_seconds=duration_seconds,
            guidance_scale=guidance_scale,
            guidance_scale_2=guidance_scale_2,
            seed=seed,
            randomize_seed=randomize_seed,
            api_name=api_name
        )
        logger.info(f"Started video generation job")
        return job

    def copy_result_to_folder(self, job: Job, dest_folder: Path, video_id: str) -> Path:
        """Wait for job completion and copy result to destination folder.

        Args:
            job: The gradio client Job
            dest_folder: Directory to save the video
            video_id: Unique ID for naming the output file

        Returns:
            Path to saved video file
        """
        result_dict, _ = job.result()  # blocking call
        vid_file_path = result_dict.get("video")

        if vid_file_path:
            dest_path = dest_folder / f"{video_id}.mp4"
            shutil.copy2(vid_file_path, dest_folder)

            vid_name = os.path.basename(vid_file_path)
            (dest_folder / vid_name).rename(dest_path)

            logger.info(f"Video saved to {dest_path}")
            return dest_path

        raise ValueError("Video result not found in job output")
