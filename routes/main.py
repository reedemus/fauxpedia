"""Main UI routes for the Fauxpedia application."""

from pathlib import Path
from fasthtml.common import *
from starlette.background import BackgroundTask
import json
import time

from html_presenter.prompts import PromptTemplates
from html_presenter.output_manager import OutputManager
from tasks.biography_generator import BiographyGenerator

# Import static routes separately
from routes.static_files import static_files


class MainRoutes:
    """Handler for main UI routing."""

    def __init__(
        self,
        output_manager: OutputManager,
        bio_generator: BiographyGenerator,
        portrait_gen,
        video_gen
    ):
        self.output_manager = output_manager
        self.bio_generator = bio_generator
        self.portrait_gen = portrait_gen
        self.video_gen = video_gen

    def index(self):
        """Main landing page."""
        start_btn = Button(
            "Start",
            id="start-btn",
            hx_get="/open_modal",
            hx_target="#modal-placeholder",
            hx_swap="innerHTML"
        )

        return Container(
            self._make_header(),
            Div(id="polling-placeholder"),
            Div(id="video-placeholder"),
            Div(P("Click 'Start' to enter your details."), id="info"),
            self._make_iframe(),
            start_btn,
            Div(id="modal-placeholder")
        )

    def open_modal(self):
        """Serve the user input modal."""
        return DialogX(
            Article(
                H3("Enter Your Details"),
                Link(rel="stylesheet", href="/static/css/webcam.css"),
                Script(src="/static/js/webcam.js"),

                Form(
                    Input(name="name", placeholder="Name", required=True, autofocus=True),
                    Input(name="job", placeholder="Job", required=True),
                    Input(name="place", placeholder="The place/environment of where you work", required=True),

                    # Photo input with tab interface
                    Div(
                        self._make_photo_input_tabs(),
                        self._make_upload_section(),
                        self._make_webcam_section(),
                        id="photo-input-section"
                    ),

                    Button("Enter", type="submit"),
                    hx_post="/submit",
                    hx_target="#info",
                    hx_swap="innerHTML",
                    enctype="multipart/form-data"
                )
            ),
            hx_post="/dismiss_modal",
            hx_trigger="keydown[key=='Escape'] from:body",
            id="modal-info",
            open=True
        )

    async def submit_form(self, name: str, job: str, place: str, photo=None, webcam_data=None):
        """Handle form submission and initiate processing."""
        temp_path = self._save_photo(photo, webcam_data)

        loading_display = Div(
            H3("Generating your biography..."),
            Div(cls="spinner", id="title-spinner", style="display:inline", hx_swap_oob="true"),
            cls="loading-container",
            hx_post="/process",
            hx_trigger="load",
            hx_vals=json.dumps({
                "name": name,
                "job": job,
                "place": place,
                "photo_path": str(temp_path)
            }),
            hx_target="#info",
            hx_swap="innerHTML"
        )

        return (
            loading_display,
            Div(style="display:block;", id="info"),
            Div(id="modal-info", hx_swap_oob="true"),
            Div(id="modal-placeholder", hx_swap_oob="true")
        )

    async def process_form(self, name: str, job: str, place: str, photo_path: str):
        """Execute biography generation workflow."""
        try:
            llm_prompt, image_prompt = PromptTemplates.prepare_biography_and_image_prompt(
                name, job, place
            )

            html_out = await self.bio_generator.generate_biography(llm_prompt)
            self.output_manager.write_full_html(html_out)

            request_id, bg_task = self.portrait_gen.start_generation(
                Path(photo_path), image_prompt
            )
            logger = logging.getLogger(__name__)
            logger.info(f"Started portrait generation with request_id: {request_id}")

            return (
                self._show_iframe(),
                self._portrait_poller(request_id),
                self._video_poller(request_id),
                bg_task
            )

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing form: {e}")
            return self._error_response(f"Error processing form: {str(e)}")

    # Private route helpers
    def _make_header(self) -> Div:
        return Div(
            H1("Create Your Fictional Wikipedia"),
            Div(cls="spinner", id="title-spinner", style="display:none"),
            cls="header-flex"
        )

    def _make_iframe(self) -> Iframe:
        return Iframe(
            src="/output_file",
            style="width:100%; height:80vh; border:0; display:none;",
            title="Generated biography",
            id="content-iframe"
        )

    def _make_photo_input_tabs(self) -> Div:
        return Div(
            Div(
                Input(type="radio", id="upload-radio", name="input-method", value="upload", onchange="switchInputMethod()", checked=True),
                Label("Upload File", for_="upload-radio"),
                cls="radio-option"
            ),
            Div(
                Input(type="radio", id="webcam-radio", name="input-method", value="webcam", onchange="switchInputMethod()"),
                Label("Use Webcam", for_="webcam-radio"),
                cls="radio-option"
            ),
            cls="radio-container"
        )

    def _make_upload_section(self) -> Div:
        return Div(
            Input(name="photo", type="file", accept="image/*", id="file-input"),
            id="upload-section"
        )

    def _make_webcam_section(self) -> Div:
        return Div(
            Video(id="webcam-video", width="320", height="240", autoplay=True, style="display:none"),
            Canvas(id="webcam-canvas", width="320", height="240", style="display:none"),
            Br(),
            Button("Capture Photo", type="button", onclick="capturePhoto()", id="capture-photo", style="display:none"),
            Button("Retake", type="button", onclick="retakePhoto()", id="retake-photo", style="display:none"),
            Input(name="webcam_data", type="hidden", id="webcam-data"),
            id="webcam-section",
            style="display:none"
        )

    def _show_iframe(self) -> Iframe:
        return Iframe(
            src="/output_file",
            style="width:100%; height:80vh; border:0; display:block;",
            title="Generated biography",
            id="content-iframe",
            hx_swap_oob="true"
        )

    def _portrait_poller(self, request_id: str) -> Div:
        return Div(
            "🔄 Portrait generation in progress...",
            id="polling-placeholder",
            hx_post=f"/portrait_img/{request_id}",
            hx_trigger="every 1s",
            hx_swap="outerHTML",
            style="background-color: #f0f8ff; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px;"
        )

    def _video_poller(self, request_id: str) -> Div:
        return Div(
            "🔄 Video generation in progress...",
            id="video-placeholder",
            hx_post=f"/video_status/{request_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            style="background-color: #f0f8ff; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px;"
        )

    def _error_response(self, message: str) -> Div:
        return Div(
            H3("Error"),
            P(str(message)),
            P("Try again by pressing the Start button."),
            cls="loading-container",
            id="info",
            hx_swap_oob="true"
        )

    def _save_photo(self, photo, webcam_data) -> Path:
        """Save photo from upload or webcam capture."""
        import tempfile
        from pathlib import Path as PathObj

        temp_dir = PathObj("./tmp")
        temp_dir.mkdir(exist_ok=True)

        if photo and photo.size > 0:
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False, suffix=".jpg") as temp_photo:
                temp_photo.write(photo.read())
                return Path(temp_photo.name)
        elif webcam_data:
            from utils.fileops import capture_webcam_frame
            return capture_webcam_frame(webcam_data, temp_dir)

        raise ValueError("No photo provided")

    def dismiss_modal(self):
        """Handle modal dismissal via escape key."""
        clear_modal = Div(id="modal-placeholder", hx_swap_oob="true")
        hide_info = Div(style="display:none;", id="info", hx_swap_oob="true")
        show_iframe = Iframe(
            src="/output_file",
            style="width:100%; height:80vh; border:0; display:block;",
            title="Generated biography",
            id="content-iframe",
            hx_swap_oob="true"
        )
        return clear_modal, hide_info, show_iframe

    def output_file(self):
        """Serve the generated Wikipedia biography HTML file."""
        try:
            return File("output.html")
        except FileNotFoundError:
            show_message = Div(
                H3("No Content Yet"),
                P("No biography has been generated yet. Please use the Start button below to create one."),
                cls="loading-container",
                style="display:block;",
                id="info",
                hx_swap_oob="true"
            )
            hide_iframe = Iframe(
                src="/output_file",
                style="width:100%; height:80vh; border:0; display:none;",
                title="Generated biography",
                id="content-iframe",
                hx_swap_oob="true"
            )
            return show_message, hide_iframe
