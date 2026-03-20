"""Fauxpedia - Main application entry point."""

import os
import logging
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv, find_dotenv
from fasthtml.common import *

from config.settings import AppSettings, initialize_logging
from config.credentials import load_environment, get_api_keys

# Import API clients
from api.anthropic_client import AnthropicClient
from api.imagga_client import ImgBBClient
from api.wavespeed_client import WaveSpeedClient
from api.huggingface_client import HuggingFaceClient

# Import HTML utilities
from html_presenter.output_manager import OutputManager

# Import task generators
from tasks.portrait_generator import PortraitGenerator
from tasks.video_generator import VideoGenerator

# Import routes
from routes.main import MainRoutes
from routes.polling import PollingRoutes
from routes.assets import AssetRoutes
from routes.static_files import static_files

# Load environment
load_environment()

# Initialize settings and logging
settings = AppSettings.from_env()
initialize_logging(settings.log_file)

logger = logging.getLogger(__name__)

# Get API keys
keys = get_api_keys()

# Initialize API clients
anthropic = AnthropicClient(
    api_key=keys.get("anthropic"),
    model=settings.anthropic_model
)
imgbb = ImgBBClient(api_key=keys.get("imgbb"))
wavespeed = WaveSpeedClient(api_key=keys.get("openrouter"))
huggingface = HuggingFaceClient(
    space_url=os.environ.get("HF_SPACE_URL"),
    api_key=keys.get("huggingface")
)

# Initialize generators
output_manager = OutputManager()
portrait_gen = PortraitGenerator(imgbb, wavespeed, settings.gen_folder)
video_gen = VideoGenerator(huggingface, settings.gen_folder)

# Initialize routes
main_routes = MainRoutes(output_manager, None, portrait_gen, video_gen)
polling_routes = PollingRoutes(output_manager, portrait_gen, video_gen)
asset_routes = AssetRoutes(settings)

# Custom styling
style = Style("""
    /* This styles the 'Start' button */
    #start-btn {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
    }
    /* Ensure Pico's dialog appears on top of other content */
    dialog {
        z-index: 2000;
    }
    /* Loading spinner styles */
    .loading-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        text-align: center;
    }
    .header-flex {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        margin-bottom: 2rem;
        gap: 1rem;
    }
    .header-flex h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
    }
    #polling-placeholder {
        min-width: 220px;
        text-align: left;
        align-self: flex-start;
    }
    #video-placeholder {
        min-width: 220px;
        text-align: left;
        align-self: flex-start;
    }
    .spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #3498db;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
""")

# Initialize the app
app, rt = fast_app(hdrs=(style,))


# Register routes
# Static files
@rt("/{fname:path}.{ext:static}")
def static_route(fname: str, ext: str):
    return static_files(fname, ext)


# Main UI routes
@rt("/")
def index():
    return main_routes.index()


@rt("/open_modal")
def open_modal():
    return main_routes.open_modal()


@rt("/dismiss_modal")
def dismiss_modal():
    return main_routes.dismiss_modal()


@rt("/submit")
async def submit_form(name: str, job: str, place: str, photo=None, webcam_data=None):
    return await main_routes.submit_form(name, job, place, photo, webcam_data)


@rt("/process")
async def process_form(name: str, job: str, place: str, photo_path: str):
    return await main_routes.process_form(name, job, place, photo_path)


@rt("/output_file")
def output_file():
    return main_routes.output_file()


# Polling endpoints
@rt("/portrait_img/{id}")
def get_portrait_img(id: str):
    return polling_routes.portrait_status(id)


@rt("/video_status/{id}")
def video_status(id: str):
    return polling_routes.video_status(id)


# Asset management
@rt("/assets/clear_all")
def clear_assets(request):
    return asset_routes.clear_assets(request)


@rt("/assets/list_all")
def list_assets(request):
    return asset_routes.list_assets(request)


# Health check
@rt("/health")
def health_check(request):
    return {"status": "OK", "message": "running"}


serve()
