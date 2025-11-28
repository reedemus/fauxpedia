import os, json, time, base64, tempfile, logging, time, httpx, uuid
import datetime as dt
from datetime import datetime
from typing import Dict
from asyncio import CancelledError
from dotenv import load_dotenv, find_dotenv
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from fasthtml.common import *
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import Response, FileResponse
from gradio_client import Client, handle_file

# Environment variables
load_dotenv(find_dotenv())
llm_api_key = os.environ.get("ANTHROPIC_API_KEY")
gen_image_api_key = os.environ.get("WAVESPEED_API_KEY")
hf_api_key = os.environ.get("HFACE_API_KEY")
hf_space_url = os.environ.get("HF_SPACE_URL")
img_service_key = os.environ.get("IMGBB_API_KEY")

# folder for generated assets
GEN_FOLDER = "./generated"
os.makedirs(GEN_FOLDER, exist_ok=True)

# Configure basic logging for this module
# Delete log file on each run
if os.path.exists("main.log"):
    os.remove("main.log")
logging.basicConfig(filename=os.path.join(os.curdir, "main.log"), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Session tracking and user isolation
active_sessions: Dict[str, dict] = {}
SESSION_EXPIRY_MINUTES = 30  # Browser sessions don't timeout, but track for debugging

def generate_session_id() -> str:
    """Generate unique session identifier using UUID4"""
    return str(uuid.uuid4())

def get_user_id_from_session(sess) -> str:
    """Get existing user ID or create new one for session"""
    if 'user_id' not in sess:
        sess['user_id'] = generate_session_id()
        active_sessions[sess['user_id']] = {
            'created': datetime.now().isoformat(),
            'last_access': datetime.now().isoformat(),
            'request_count': 0
        }
        logger.info(f"Created new session: {sess['user_id']}")
    else:
        # Update last access time
        if sess['user_id'] in active_sessions:
            active_sessions[sess['user_id']]['last_access'] = datetime.now().isoformat()
            active_sessions[sess['user_id']]['request_count'] += 1
    
    return sess['user_id']

def is_session_expired(session_id: str) -> bool:
    """Check if session has expired (browser sessions don't expire, but validate existence)"""
    return session_id not in active_sessions

def cleanup_expired_sessions():
    """Clean up expired sessions from tracking dictionary (periodic maintenance)"""
    logger.info(f"Session cleanup completed. Active sessions: {len(active_sessions)}")

def get_user_html_path(user_id: str) -> str:
    """Get user-specific HTML file path"""
    return f"output_{user_id}.html"

def get_user_assets_dir(user_id: str) -> str:
    """Get user-specific assets directory path"""
    user_dir = os.path.join(GEN_FOLDER, user_id)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def ensure_user_directories(user_id: str):
    """Ensure user-specific directories exist"""
    get_user_assets_dir(user_id)  # This will create the directory if it doesn't exist

def cleanup_user_assets(user_id: str) -> bool:
    """Clean up user-specific files and directories"""
    try:
        # Remove user-specific HTML file
        html_path = get_user_html_path(user_id)
        if os.path.exists(html_path):
            os.unlink(html_path)
            logger.info(f"Removed user HTML: {html_path}")
        
        # Remove user-specific assets directory
        user_assets_dir = get_user_assets_dir(user_id)
        if os.path.exists(user_assets_dir):
            import shutil
            shutil.rmtree(user_assets_dir)
            logger.info(f"Removed user assets: {user_assets_dir}")
        
        return True
    except Exception as e:
        logger.error(f"Error cleaning up user assets for {user_id}: {str(e)}")
        return False

def session_middleware(req, sess):
    """Beforeware to handle session management and user isolation"""
    user_id = get_user_id_from_session(sess)
    # Store user_id in request scope for easy access
    req.scope['user_id'] = user_id
    
    # If session expired, create a new one instead of showing 'session expired'
    if is_session_expired(user_id):
        logger.info(f"Session expired for user {user_id}, creating new session.")
        sess['user_id'] = generate_session_id()
        active_sessions[sess['user_id']] = {
            'created': datetime.now().isoformat(),
            'last_access': datetime.now().isoformat(),
            'request_count': 0
        }
        req.scope['user_id'] = sess['user_id']

## MODEL CALLS ##
def expand_prompt(job: str, place: str) -> str:
    llm_prompt = f"""Using the attached image, expand the prompt below for a video generation model to include the subject, scene and motion: \
        the person in the image is highly successful and famous {job} working at {place}."""
    return llm_prompt

def prepare_prompt(name: str, job: str, place: str) -> tuple[str, str]:
    llm_prompt = f"""
Create a fictional and funny wikipedia biography of {name} as a {job} from {place}. 
The output format must be html and css in typical wikipedia format. Strictly no emojis in the output.
Use the placeholder image at src="/static/portrait.jpg" with element id "portrait-image".
Use the placeholder video at src="/static/portrait.mp4" with element id "portrait-video".
Use the section headers below:
- Early life
- Career
- Personal life
- My typical work day
  (place the video element here)
- Awards and Achievements
- Wealth
- Scandals
- References
- Further reading
    """
    image_prompt = f"Create a photo of the attached image as a {job} performing his job in {place}."
    return llm_prompt, image_prompt


def cleanup_html_output(content: str) -> str:
    """Cleans up the HTML output from the LLM by extracting the <!DOCTYPE html> to </html> block."""
    # Find the position of <!DOCTYPE html> and rmeove anything before it
    doctype_pos = content.find("<!DOCTYPE html>")
    if doctype_pos != -1:
        content = content[doctype_pos:]
    # Fill missing closing html tags automatically after parsing
    parsed_html = BeautifulSoup(content, 'html.parser')
    return parsed_html.prettify()


async def call_anthropic(prompt: str, image: str="", is_url: bool=False) -> str:
    """Call an Anthropic/Claude-style LLM endpoint."""
    client = AsyncAnthropic(
        api_key=llm_api_key
    )

    if len(image):
            if is_url:
                input = [{  "type": "image",
                            "source": {
                                "type": "url",
                                "url": image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                ]
            else:
                input = [{  "type": "image",
                            "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64.b64encode(open(image, "rb").read()).decode('utf-8'),
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                ]
    else:
        input = prompt

    async with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        messages=[
            {"role": "user", "content": input}
        ],
        max_tokens=8192,
    ) as stream:
        # Consume the stream without printing
        async for text in stream.text_stream:
            pass
    
    # Get the complete text after streaming is done
    content = await stream.get_final_text()
    final_message = await stream.get_final_message()
    output_tokens = final_message.usage.output_tokens

    logger.info(f"Used {output_tokens} output tokens.")
    return content


def upload_photo(file_path: str) -> str:
    """Upload user photo to imgBB for temp storagecwith an expiration time.
    Returns the url of the uploaded image.
    """
    image_url = ""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return image_url

    api_url="https://api.imgbb.com/1/upload"
    parameters = {"expiration": 600, "key": img_service_key} # photo is deleted after 10 minutes

    with open(file_path, 'rb') as f:
        files = {'image': f}
        response = httpx.post(api_url, files=files, params=parameters)
        response.raise_for_status()
        json_data = json.loads(response.content.decode('utf-8'))
        image_url = json_data['data']['image']['url']
        logger.info(f"Upload successful! Download url: {image_url}")
    return image_url


def call_generate_image(face_image_url: str, prompt: str) -> str:
    """Call a generative image API to produce an image of the person in the job role.
    Returns request ID of image.
    """
    return_val = ""

    url = "https://api.wavespeed.ai/api/v3/bytedance/seedream-v4/edit"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gen_image_api_key}",
    }
    payload = {
        "enable_base64_output": False,
        "enable_sync_mode": False,
        "images": [face_image_url],
        "prompt": prompt,
        "size": "1024*1536" # Portrait orientation 2:3
    }
    response = httpx.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    result = response.json()["data"]
    request_id = result["id"]
    return_val = request_id
    logger.info(f"Call gen image API with request ID: {request_id}")
    return return_val


def poll_generated_result(request_id: str) -> str:
    """Poll for the result of the generated image/video from request id.
    Returns url or base64 string.
    """
    url = f"https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"
    headers = {"Authorization": f"Bearer {gen_image_api_key}"}
    return_val = ""

    # Poll for results
    begin = time.time()
    status = "in progress"

    while status != "completed":
        response = httpx.get(url, headers=headers)
        if response.status_code == 200:
            result_json = response.json()["data"]
            status = result_json["status"]
            if status == "completed":
                end = time.time()
                logger.info(f"Task completed in {end - begin} seconds.")
                return_val = result_json["outputs"][0]
                break
            elif status == "failed":
                logger.info(f"Task failed: {result_json.get('error')}")
                break
            else:
                logger.info(f"Task still processing. Status: {status}")
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            break
        time.sleep(1)
    return return_val


def download_generated_result(request_id: str, url: str, user_id: str) -> str:
    """Download generated image/video from url to user-specific directory"""
    user_assets_dir = get_user_assets_dir(user_id)
    saved_image_path = os.path.join(user_assets_dir, f"{request_id}.jpeg")
    saved_video_path = os.path.join(user_assets_dir, f"{request_id}.mp4")
    
    return_val = ""

    if "data:image/jpeg;base64" in url:
        # url is actually a base64 string
        # Decode the base64 string back into binary data (bytes)
        content = url.split(',')
        img_bytes = base64.b64decode(content[1])

        with open(saved_image_path, 'wb') as f:
            f.write(img_bytes)
            return_val = saved_image_path
            logger.info(f"Saved generated image to {saved_image_path}")

    elif ".jpeg" in url:
            response = httpx.get(url)
            response.raise_for_status()
            with open(saved_image_path, 'wb') as f:
                f.write(response.content)
                return_val = saved_image_path
                logger.info(f"Saved generated image to {saved_image_path}")

    elif ".mp4" in url:
            response = httpx.get(url)
            response.raise_for_status()
            with open(saved_video_path, 'wb') as f:
                f.write(response.content)
                return_val = saved_video_path
                logger.info(f"Saved generated video to {saved_video_path}")

    else:
        logger.error(f"Error: download failed for {request_id}!")
    return return_val


def call_generate_video(image_url: str, scene_prompt: str):
    """Call video generation model
    Returns local path to generated video file.
    """
    client = Client(hf_space_url, token=hf_api_key)
    job = client.submit(
        input_image=handle_file(image_url),
        prompt=scene_prompt,
        steps=6,
        negative_prompt="low quality, blurry, deformed, distorted, disfigured, ugly, duplicate, watermark, text, error, cropped, worst quality",
        duration_seconds=5.0,
        guidance_scale=1,
        guidance_scale_2=1,
        seed=42,
        randomize_seed=True,
        api_name="/generate_video"
    )
    return job


def portrait_reload(id: str, user_id: str):
    """Update the portrait image in user-specific HTML file and trigger UI refresh"""
    user_assets_dir = get_user_assets_dir(user_id)
    image_path = os.path.join(user_assets_dir, f"{id}.jpeg")
    html_file = get_user_html_path(user_id)
    
    if os.path.exists(image_path):
        logger.info(f"Found generated image for {id}, updating {html_file}")
        
        # Validate session before file operations
        if is_session_expired(user_id):
            logger.warning(f"Session expired during portrait reload for user {user_id}")
            return Div("Session expired", id="polling-placeholder", hx_swap_oob="true")
        
        # Open HTML file and replace the image src using sync file operations
        with open(html_file, "r+") as file:
            html_content = file.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
            # Find the portrait image element by ID and update it
            portrait_img = soup.find('img', id='portrait-image')
            if portrait_img:
                # Use relative path from user's perspective
                relative_path = os.path.join("generated", user_id, f"{id}.jpeg")
                portrait_img['src'] = relative_path
                
                logger.info(f"Updated image src to {portrait_img['src']}")
                
                file.seek(0)
                file.write(str(soup))
                file.truncate()
                logger.info(f"Successfully updated {html_file}")
                
                # Return elements for immediate UI update
                # Update the iframe src to force refresh with cache busting
                timestamp = int(time.time())
                
                # Create updated iframe element
                show_iframe = Iframe(
                    src=f"/output_file?refresh={timestamp}",
                    style="width:100%; height:80vh; border:0; display:block;",
                    title="Generated biography",
                    id="content-iframe",
                    hx_swap_oob="true"
                )

                # Remove the polling element since we're done
                stop_polling = Div("", id="polling-placeholder", hx_swap_oob="true")
                # Also hide the header spinner (out-of-band swap)
                hide_header_spinner = Div("", id="title-spinner", hx_swap_oob="true")

                return show_iframe, stop_polling
            else:
                logger.warning(f"Portrait image element not found in {html_file}")
                return Div("Portrait image element not found", id="polling-placeholder", hx_swap_oob="true")
    else:
        logger.info(f"Generated image for {id} not found yet, continuing to poll")
        # Continue polling
        portrait_poller = Div(
            "🔄 Portrait generation in progress...",
            id="polling-placeholder",
            hx_post=f"/portrait_img/{id}",
            hx_trigger="every 1s",
            hx_swap="outerHTML",
            style="background-color: #f0f8ff; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px;"
        )
        # Also trigger showing the header spinner via an out-of-band swap so
        # the small spinner in the header becomes visible while polling.
        show_header_spinner = Div(cls="spinner", id="title-spinner", style="display:inline", hx_swap_oob="true")
        return portrait_poller, show_header_spinner


def video_reload(vid: str, user_id: str):
    """Update the video in user-specific HTML file and trigger UI refresh"""
    user_assets_dir = get_user_assets_dir(user_id)
    video_path = os.path.join(user_assets_dir, f"{vid}.mp4")
    html_file = get_user_html_path(user_id)
    
    if os.path.exists(video_path):
        logger.info(f"Found generated video for {vid}, updating {html_file}")
        
        # Validate session before file operations
        if is_session_expired(user_id):
            logger.warning(f"Session expired during video reload for user {user_id}")
            return Div("Session expired", id="video-placeholder", hx_swap_oob="true")
        
        # Open HTML file and replace the video src using sync file operations
        with open(html_file, "r+") as file:
            html_content = file.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
            # Find the video element by ID and update it, autoloop
            video_tag = soup.find('video', id='portrait-video')
            if video_tag:
                video_tag['loop'] = ""
                # Use relative path from user's perspective
                relative_path = os.path.join("generated", user_id, f"{vid}.mp4")
                video_tag['src'] = relative_path
                
                file.seek(0)
                file.write(str(soup))
                file.truncate()
                logger.info(f"Successfully updated {html_file}")
                
                # Return elements for immediate UI update
                # Update the iframe src to force refresh with cache busting
                timestamp = int(time.time())
                
                # Create updated iframe element
                show_iframe = Iframe(
                    src=f"/output_file?refresh={timestamp}",
                    style="width:100%; height:80vh; border:0; display:block;",
                    title="Generated biography",
                    id="content-iframe",
                    hx_swap_oob="true"
                )

                # Remove the polling element since we're done
                stop_polling = Div("", id="video-placeholder", hx_swap_oob="true")
                # Also hide the header spinner (out-of-band swap)
                hide_header_spinner = Div("", id="title-spinner", hx_swap_oob="true")

                return show_iframe, stop_polling, hide_header_spinner
            else:
                logger.warning(f"Video element not found in {html_file}")
                return Div("Video element not found", id="video-placeholder", hx_swap_oob="true")
    else:
        logger.info(f"Generated video for {vid} not found yet, continuing to poll")
        # Continue polling
        video_poller = Div(
            "🔄 Video generation in progress...",
            id="video-placeholder",
            hx_post=f"/video_status/{vid}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            style="background-color: #f0f8ff; padding: 10px; margin: 10px 0; border: 1px solid #ccc; border-radius: 5px;"
        )

        # Also trigger showing the header spinner via an out-of-band swap so
        # the small spinner in the header becomes visible while polling.
        show_header_spinner = Div(cls="spinner", id="title-spinner", style="display:inline", hx_swap_oob="true")

        return video_poller, show_header_spinner


def start_portrait_generation(photo_path: str, image_prompt: str, user_id: str)-> tuple[str, BackgroundTask]:
    """
    Start portrait generation and return request_id immediately.
    The actual image generation happens in background with user-specific context.
    """
    # Upload photo and start generation (these are quick)
    photo_url = upload_photo(photo_path)
    request_id = call_generate_image(photo_url, image_prompt)
    
    # Start the polling and download in background with user context
    btask = BackgroundTask(complete_portrait_generation, request_id=request_id, user_id=user_id)
    return request_id, btask

def complete_portrait_generation(request_id: str, user_id: str):
    """
    Complete the portrait generation in background with session validation.
    Polls for result and downloads when ready to user-specific directory.
    Triggers immediate UI update when generation is complete.
    """
    try:
        # Validate session before starting background work
        if is_session_expired(user_id):
            logger.warning(f"Session expired during portrait generation for user {user_id}")
            return
        
        download_url = poll_generated_result(request_id)
        download_generated_result(request_id, download_url, user_id)
        logger.info(f"Portrait generation completed for request_id: {request_id}, user: {user_id}")
        
        # Final session validation before completion
        if is_session_expired(user_id):
            logger.warning(f"Session expired during portrait completion for user {user_id}")
            return
            
    except Exception as e:
        logger.error(f"Background portrait generation failed for {request_id}: {str(e)}")


def start_video_generation(image_url: str, video_prompt: str, user_id: str) -> tuple[str, BackgroundTask]:
    """
    Start video generation and return collision-free video ID immediately.
    The actual video generation happens in background with user-specific context.
    """
    job = call_generate_video(image_url, video_prompt)
    
    # Generate collision-free video ID using user_id and timestamp
    vid = f"{user_id}_{int(time.time())}"
    
    btask = BackgroundTask(complete_video_generation, job=job, video_id=vid, user_id=user_id)
    return vid, btask


def complete_video_generation(job, video_id: str, user_id: str) -> str:
    """
    Complete the video generation in background with session validation.
    Returns file name of the video generated in user-specific directory.
    """
    try:
        # Validate session before starting video processing
        if is_session_expired(user_id):
            logger.warning(f"Session expired during video generation for user {user_id}")
            return ""
        
        result_dict, _ = job.result() # blocking call
        vid_file_path = result_dict.get("video")
        vid_file_name = os.path.basename(vid_file_path)
        
        # Save to user-specific directory
        user_assets_dir = get_user_assets_dir(user_id)
        destination_path = os.path.join(user_assets_dir, f"{video_id}.mp4")
        os.system(f"cp {vid_file_path} {destination_path}")
        logger.info(f"Video generation completed for user {user_id}: {destination_path}")
            
        # Final session validation
        if is_session_expired(user_id):
            logger.warning(f"Session expired during video completion for user {user_id}")
            return ""
            
    except TimeoutError:
        logger.error("Background video generation timed out")
    except CancelledError:
        logger.error("Background video generation was cancelled")
    except Exception as e:
        logger.error(f"Background video generation failed: {str(e)}")
        
    return ""


## VIEW ##

# Custom styling for the fixed button and placeholders
# We use the Style tag, which FastHTML will place in the <head>
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

# Initialize the app with session middleware and custom styles
app, rt = fast_app(
    hdrs=(style,),
    
    # Session configuration
    session={
        'secret_key': 'your-secret-key-change-this-in-production',
        'cookie_name': 'fauxpedia_session',
        'max_age': None,  # Browser session cookie - expires when tab closes
        'same_site': 'lax',
        'https_only': False  # Set to True in production with HTTPS
    },
    
    # Add session middleware
    before=session_middleware
)

@rt("/{fname:path}.{ext:static}")
def static_files(fname: str, ext: str):
    """Serve static files from the static directory."""
    return FileResponse(f"static/{fname}.{ext}")

@rt("/generated/{user_id}/{fname:path}.{ext:static}")
def user_assets(request: Request, user_id: str, fname: str, ext: str):
    """Serve user-specific generated assets with session validation."""
    session_user_id = request.session.get('user_id')
    
    # Only allow users to access their own assets
    if not session_user_id or session_user_id != user_id:
        logger.warning(f"Unauthorized asset access attempt: session_user={session_user_id}, requested_user={user_id}")
        return Response("Unauthorized", 403)
    
    user_assets_dir = get_user_assets_dir(user_id)
    asset_path = os.path.join(user_assets_dir, f"{fname}.{ext}")
    
    if not os.path.exists(asset_path):
        logger.warning(f"Asset not found: {asset_path}")
        return Response("Not Found", 404)
    
    return FileResponse(asset_path)

@rt("/")
def index(request: Request):
    """
    Main landing page route that displays the application interface with session awareness.
    """
    user_id = request.session.get('user_id')
    logger.info(f"Index page accessed by user: {user_id}")
    
    start_btn = Button(
        "Start",
        id="start-btn",
        hx_get="/open_modal",
        hx_target="#modal-placeholder",
        hx_swap="innerHTML"
    )

    info_placeholder = Div(P("Click 'Start' to enter your details."), id="info")
    polling_placeholder = Div(id="polling-placeholder")
    video_placeholder = Div(id="video-placeholder")

    content_iframe = Iframe(
        src="/output_file",
        style="width:100%; height:80vh; border:0; display:none;",
        title="Generated biography",
        id="content-iframe"
    )

    modal_placeholder = Div(id="modal-placeholder")

    # Manual header row: flex H1 and polling
    header_row = Div(
        H1("Create Your Fictional Wikipedia"),
        Div(cls="spinner", id="title-spinner", style="display:none"),
        cls="header-flex"
    )

    return Container(
        header_row,
        polling_placeholder,
        video_placeholder,
        info_placeholder,
        content_iframe,
        start_btn,
        modal_placeholder
    )


@rt("/open_modal")
def open_modal():
    """
    Route that serves the user input modal dialog with webcam and file upload options.
    
    Called via HTMX when the "Start" button is clicked. Creates and returns
    a DialogX modal containing a form for user input with tab switching between
    file upload and webcam capture.
    
    Returns:
        DialogX modal with:
        - Form fields for name, job, place
        - Tab interface for photo upload or webcam capture
        - Submit button that triggers form processing
        - Escape key handler for modal dismissal
        - Auto-focus on the name input field
    """
    return DialogX(
        Article(
            H3("Enter Your Details"),
            # Include CSS and JS for webcam functionality
            Link(rel="stylesheet", href="/static/css/webcam.css"),
            Script(src="/static/js/webcam.js"),
            
            Form(
                Input(name="name", placeholder="Name", required=True, autofocus=True),
                Input(name="job", placeholder="Job", required=True),
                Input(name="place", placeholder="The place/environment of where you work", required=True),
                
                # Photo input section with radio button interface
                Div(
                    H4("Add Your Photo"),
                    # Radio buttons
                    Div(
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
                    ),
                    
                    # Upload section (default)
                    Div(
                        Input(name="photo", type="file", accept="image/*", id="file-input"),
                        id="upload-section"
                    ),
                    
                    # Webcam section (initially hidden)
                    Div(
                        Video(id="webcam-video", width="320", height="240", autoplay=True, style="display:none"),
                        Canvas(id="webcam-canvas", width="320", height="240", style="display:none"),
                        Br(),
                        Button("Capture Photo", type="button", onclick="capturePhoto()", id="capture-photo", style="display:none"),
                        Button("Retake", type="button", onclick="retakePhoto()", id="retake-photo", style="display:none"),
                        Input(name="webcam_data", type="hidden", id="webcam-data"),
                        id="webcam-section",
                        style="display:none"
                    ),
                    id="photo-input-section"
                ),
                
                Button("Enter", type="submit"),
                # Form attributes for HTMX
                hx_post="/submit",
                hx_target="#info", 
                hx_swap="innerHTML",
                enctype="multipart/form-data"  # Required for file uploads
            )
        ),
        # Pure FastHTML escape key handling - no JavaScript needed!
        hx_post="/dismiss_modal",
        hx_trigger="keydown[key=='Escape'] from:body",
        id="modal-info",
        open=True  # This makes the dialog visible
    )


@rt("/dismiss_modal")
def dismiss_modal():
    """
    Route that handles modal dismissal via escape key.
    
    Called when user presses the Escape key while modal is open.
    Performs multiple out-of-band swaps to clean up the UI state.
    
    Returns:
        Multiple elements with out-of-band swaps:
        - Clears the modal placeholder (closes modal)
        - Hides the info display area
        - Shows the iframe (attempts to display any existing content)
    """
    # Clear the modal placeholder to close the modal
    clear_modal = Div(id="modal-placeholder", hx_swap_oob="true")
    
    # Hide the info display
    hide_info = Div(
        style="display:none;",
        id="info", 
        hx_swap_oob="true"
    )
    
    # Show the iframe
    show_iframe = Iframe(
        src="/output_file", 
        style="width:100%; height:80vh; border:0; display:block;",
        title="Generated biography",
        id="content-iframe",
        hx_swap_oob="true"
    )
    
    return clear_modal, hide_info, show_iframe


@rt("/submit")
async def submit_form(request: Request, name: str, job: str, place: str, photo: UploadFile = None, webcam_data: str = None):
    """
    Route that handles form submission and initiates biography generation with session isolation.
    
    Receives user input from the modal form, handles both file uploads and webcam captures,
    saves the photo to a user-specific temporary file, and returns a loading spinner while 
    triggering background processing.
    
    Args:
        request (Request): FastHTML request object containing session data
        name (str): Person's name for the biography
        job (str): Person's profession/job title
        place (str): Work environment or location
        photo (UploadFile, optional): User's photo file for AI image generation
        webcam_data (str, optional): Base64 encoded webcam capture data
    
    Returns:
        Multiple elements with out-of-band swaps:
        - Loading spinner with auto-trigger to start processing
        - Closed modal elements to dismiss the form
        - Clears modal placeholder
    """
    user_id = request.session.get('user_id')
    if not user_id:
        logger.error("No session found during form submission")
        return Div(
            H3("Session Error"),
            P("Please refresh the page and try again."),
            cls="loading-container"
        )
    
    logger.info(f"Form submitted by user: {user_id}")
    temp_photo_path = None
    
    # Handle file upload
    if photo and photo.size > 0:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_photo:
            temp_photo.write(await photo.read())
            temp_photo_path = temp_photo.name
            logger.info(f"Saved uploaded photo to {temp_photo_path}")
    
    # Handle webcam capture
    elif webcam_data:
        import base64
        
        try:
            # Remove data URL prefix if present
            if webcam_data.startswith('data:image'):
                webcam_data = webcam_data.split(',')[1]
            
            # Decode base64 and save to temp file
            image_data = base64.b64decode(webcam_data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_photo:
                temp_photo.write(image_data)
                temp_photo_path = temp_photo.name
                logger.info(f"Saved webcam capture to {temp_photo_path}")
        except Exception as e:
            logger.error(f"Error processing webcam data: {str(e)}")
            return Div(
                H3("Error"),
                P("Failed to process webcam image. Please try again."),
                cls="loading-container"
            )
    
    # Return error if no photo provided
    else:
        return Div(
            H3("Error"),
            P("Please provide a photo either by file upload or webcam capture."),
            cls="loading-container"
        )
    
    # Continue with existing processing if we have a photo

    show_info = Div(
        style="display:block;",
        id="info"
    )
    # Return loading spinner immediately
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
            "photo_path": temp_photo_path
        }),
        hx_target="#info",
        hx_swap="innerHTML"
    )
    
    # Close the modal using out-of-band swap - replace with empty div
    closed_modal = Div(id="modal-info", hx_swap_oob="true")
    
    # Also clear the modal placeholder
    clear_modal_placeholder = Div(id="modal-placeholder", hx_swap_oob="true")
    
    return loading_display, show_info, closed_modal, clear_modal_placeholder


@rt("/process") 
async def process_form(request: Request, name: str, job: str, place: str, photo_path: str):
    """
    Route that performs the actual biography generation and AI image processing with session isolation.
    
    Called automatically by HTMX after the loading spinner is displayed.
    Orchestrates the complete workflow: LLM text generation, image upload,
    AI image generation, and file updates with user-specific paths.
    
    Args:
        request (Request): FastHTML request object containing session data
        name (str): Person's name for the biography
        job (str): Person's profession/job title  
        place (str): Work environment or location
        photo_path (str): Path to the temporary photo file
    
    Returns:
        On success: Updates to show iframe with generated content
        On error: Error message with retry button
        
    Workflow:
        1. Validate session and create user-specific directories
        2. Generate Wikipedia biography text using Anthropic LLM
        3. Upload user photo to WaveSpeed AI service
        4. Generate AI image based on user photo and job context
        5. Update user-specific HTML with generated content and new image
        6. Display results in iframe
    """
    user_id = request.session.get('user_id')
    if not user_id or is_session_expired(user_id):
        logger.error(f"Invalid or expired session during processing: {user_id}")
        return Div(
            H3("Session Error"),
            P("Your session has expired. Please refresh the page and try again."),
            cls="loading-container"
        )
    
    logger.info(f"Processing biography for user: {user_id}")
    
    try:
        # Create user-specific directories and get paths
        ensure_user_directories(user_id)
        user_html_path = get_user_html_path(user_id)
        
        # Call the LLM to generate the biography and image prompt
        logger.info("Calling LLM to generate wiki...")
        llm_prompt, image_prompt = prepare_prompt(name, job, place)
        html_out = await call_anthropic(llm_prompt)
        out = cleanup_html_output(html_out)
        
        # Write to user-specific HTML file
        with open(user_html_path, "w") as f:
            f.write(out)
        logger.info(f"Generated biography saved to {user_html_path}")

        # Start portrait image generation in background with user-specific ID
        request_id, bck_task = start_portrait_generation(photo_path, image_prompt, user_id)
        logger.info(f"Started portrait generation with request_id: {request_id}")

        # Start video generation in background and get request_id.
        # Requires portrait image to be ready first, so we do it in background task later.
        image_url = poll_generated_result(request_id)
        if image_url != "":
            logger.info(f"Starting video generation after portrait is ready.")
            # Prepare video prompt
            video_prompt = await call_anthropic(prompt=expand_prompt(job, place))
            str_index = video_prompt.find("subject".lower())
            video_prompt = video_prompt[str_index:]
            vid, video_task = start_video_generation(image_url, video_prompt, user_id)

        # Return updates to show the iframe immediately with the placeholder image
        show_iframe = Iframe(
            src="/output_file",
            style="width:100%; height:80vh; border:0; display:block;",
            title="Generated biography",
            id="content-iframe",
            hx_swap_oob="true"
        )
        return show_iframe, portrait_reload(request_id, user_id), bck_task, video_reload(str(vid), user_id), video_task

    except Exception as e:
        logger.error(f"Error processing form: {str(e)}")
        return Div(
            H3("Error"),
            P(f"An error occurred: {str(e)}."),
            P("Try again by pressing the Start button."),
            cls="loading-container",
            id="info",
            hx_swap_oob="true"
        )


@rt("/portrait_img/{id}")
def get_portrait_img(request: Request, id: str):
    user_id = request.session.get('user_id')
    logger.info(f"Receive polling request for image id: {id} from user: {user_id}")
    return portrait_reload(id, user_id)


@rt('/video_status/{id}')
def video_status(request: Request, id: str):
    user_id = request.session.get('user_id')
    logger.info(f"Receive polling request for video id: {id} from user: {user_id}")
    return video_reload(id, user_id)


@rt("/output_file")
def output_file(request: Request):
    """
    Route that serves the generated Wikipedia biography HTML file with session isolation.
    
    Attempts to serve the user-specific HTML file containing the generated biography.
    If the file doesn't exist (no content has been generated yet), returns
    a helpful message and manages UI state.
    
    Returns:
        On success: The user-specific generated HTML file
        On FileNotFoundError: 
        - Message indicating no content exists yet
        - Hides the iframe to prevent loading errors
        - Directs user to use the Start button
    """
    user_id = request.session.get('user_id')
    if not user_id:
        return Response("Session required", 403)
    
    try:
        user_html_path = get_user_html_path(user_id)
        logger.info(f"Serving output file for user: {user_id} from {user_html_path}")
        return FileResponse(user_html_path)
    except FileNotFoundError:
        # If no content exists yet, show message in info display and keep iframe hidden
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


@rt("/assets/clear_all")
def post(request, session):
    """Authenticated POST endpoint to clear generated assets"""
    # Add simple authentication check
    api_key = request.headers.get("Authorization")
    if api_key != f"Bearer {llm_api_key}":  # Replace with your key
        return Response("Unauthorized", 401)
    
    try:
        assets_path = os.path.join(os.getcwd(), GEN_FOLDER)
        
        if not os.path.exists(assets_path):
            os.makedirs(assets_path)  # Recreate if it doesn't exist
            return {"status": "success", "message": f"Created empty {GEN_FOLDER} directory"}
        
        # Clear all contents
        for filename in os.listdir(assets_path):
            file_path = os.path.join(assets_path, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)

        logger.info(f"Successfully cleared {GEN_FOLDER} directory")
        return {"status": "success", "message": f"Successfully cleared {GEN_FOLDER} directory"}
        
    except Exception as e:
        logger.error(f"Error clearing assets: {str(e)}")
        return {"status": "error", "message": str(e)}, 500


@rt("/assets/list_all")
def get(request, session):
    """List all files in the generated assets directory"""
    # Add simple authentication check
    api_key = request.headers.get("Authorization")
    if api_key != f"Bearer {llm_api_key}":  # Replace with your key
        return Response("Unauthorized", 401)

    try:
        assets_path = os.path.join(os.getcwd(), GEN_FOLDER)
        if not os.path.exists(assets_path):
            return {"status": "error", "message": f"Directory {GEN_FOLDER} does not exist"}, 404

        files = []
        for filename in os.listdir(assets_path):
            file_path = os.path.join(assets_path, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "last_modified": dt.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                })
        logger.info(f"Sent list of files in {GEN_FOLDER} directory")
        return {"status": "success", "files": files}
    except Exception as e:
        logger.error(f"Error listing assets: {str(e)}")
        return {"status": "error", "message": str(e)}, 500


serve()
