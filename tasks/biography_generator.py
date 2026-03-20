"""Background task for biography (text) generation."""

import logging
from pathlib import Path
from starlette.background import BackgroundTask

from api.anthropic_client import AnthropicClient
from api.wavespeed_client import WaveSpeedClient
from tasks.portrait_generator import PortraitGenerator
from tasks.video_generator import VideoGenerator
from html_presenter.prompts import PromptTemplates

logger = logging.getLogger(__name__)


class BiographyGenerator:
    """Orchestrates biography generation with image and video."""

    def __init__(
        self,
        anthropic_client: AnthropicClient,
        portrait_generator: PortraitGenerator,
        video_generator: VideoGenerator,
        output_manager
    ):
        self.anthropic = anthropic_client
        self.portrait_gen = portrait_generator
        self.video_gen = video_generator
        self.output_manager = output_manager

    async def generate_biography(self, prompt: str) -> str:
        """Generate Wikipedia-style biography."""
        return await self.anthropic.call_text_only(prompt)

    async def generate_biography_and_image(
        self,
        name: str,
        job: str,
        place: str
    ) -> tuple[str, str, BackgroundTask]:
        """Generate entire biography, image prompt, and start image generation.

        Returns:
            Tuple of (html_content, image_prompt, background_task)
        """
        llm_prompt, image_prompt = PromptTemplates.prepare_biography_and_image_prompt(
            name, job, place
        )

        html_out = await self.generate_biography(llm_prompt)
        return html_out, image_prompt

    async def start_video_workflow(
        self,
        image_id: str,
        gen_image_path: Path
    ):
        """Start the complete video generation workflow.

        Args:
            image_id: ID of the generated image
            gen_image_path: Path to the generated image
        """
        try:
            from api.huggingface_client import HuggingFaceClient
            from html_presenter.prompts import PromptTemplates

            # Generate caption for the image
            caption = await self.anthropic.call_text_only(
                PromptTemplates.get_image_caption()
            )

            # Prepare video prompt from caption
            video_prompt = await self.anthropic.call_text_only(
                PromptTemplates.prepare_video_prompt(caption)
            )

            # Start video generation
            await self.video_gen.generate_video_for_image(gen_image_path, video_prompt)

            logger.info(f"Started video generation workflow for {image_id}")
        except Exception as e:
            logger.error(f"Video generation workflow failed: {e}")
            raise
