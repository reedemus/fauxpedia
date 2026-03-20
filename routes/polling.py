"""Polling endpoints for portrait and video generation status."""

from pathlib import Path
from fasthtml.common import *
import time

from html_presenter.output_manager import OutputManager
from tasks.portrait_generator import PortraitGenerator
from tasks.video_generator import VideoGenerator


class PollingRoutes:
    """Handles HTMX polling endpoints."""

    def __init__(
        self,
        output_manager: OutputManager,
        portrait_gen: PortraitGenerator,
        video_gen: VideoGenerator
    ):
        self.output_manager = output_manager
        self.portrait_gen = portrait_gen
        self.video_gen = video_gen

    def portrait_status(self, id: str):
        """Poll for portrait image generation status."""
        image_path = Path(f"{self.portrait_gen.gen_folder}/{id}.jpeg")

        if not image_path.exists():
            return self._create_poller("portrait", id)

        if self.output_manager.update_image_src("portrait-image", image_path):
            return self._create_complete_portrait_resp(id)

        return Div("Portrait image element not found", id="polling-placeholder", hx_swap_oob="true")

    def video_status(self, id: str):
        """Poll for video generation status."""
        video_path = Path(f"{self.video_gen.gen_folder}/{id}.mp4")

        if not video_path.exists():
            return self._create_poller("video", id)

        self.output_manager.update_video_src("portrait-video", video_path)
        return self._create_complete_video_resp()

    def _create_poller(self, type: str, id: str) -> Div:
        msg = "🔄 Portrait generation in progress..." if type == "portrait" else "🔄 Video generation in progress..."
        trigger = "every 1s" if type == "portrait" else "every 2s"

        return Div(
            msg,
            id=f"{type}-placeholder",
            hx_post=f"/{type}_img/{id}" if type == "portrait" else f"/video_status/{id}",
            hx_trigger=trigger,
            hx_swap="outerHTML",
            style="background-color: #f0f8ff; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px;"
        )

    def _create_complete_portrait_resp(self, id: str) -> tuple:
        timestamp = int(time.time())
        vid_task = BackgroundTask(self.video_gen.start_video_workflow, id)
        return (
            Iframe(src=f"/output_file?refresh={timestamp}", hx_swap_oob="true"),
            Div("", id="polling-placeholder", hx_swap_oob="true"),
            Div("", id="title-spinner", hx_swap_oob="true"),
            vid_task
        )

    def _create_complete_video_resp(self) -> tuple:
        timestamp = int(time.time())
        return (
            Iframe(src=f"/output_file?refresh={timestamp}", hx_swap_oob="true"),
            Div("", id="video-placeholder", hx_swap_oob="true"),
            Div("", id="title-spinner", hx_swap_oob="true")
        )
