import os, json, time, base64, re, tempfile, logging, asyncio, time, httpx
from dotenv import load_dotenv, find_dotenv
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from fasthtml.common import *

# Environment variables
load_dotenv(find_dotenv())
llm_api_key = os.environ.get("ANTHROPIC_API_KEY")
gen_image_api_key = os.environ.get("WAVESPEED_API_KEY")

# Configure basic logging for this module
logging.basicConfig(filename=os.path.join(os.curdir, "main.log"), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# gen_video_api_key = os.environ.get("SORA_API_KEY")

## MODEL CALLS ##
def prepare_prompt(name: str, job: str, place: str) -> tuple[str, str]:
    llm_prompt = f"""
Create a fictional and funny wikipedia biography of {name} as a {job} from {place}. 
The output format must be html and css in typical wikipedia format. Strictly no emojis in the output.
Use the placeholder image named portrait.jpg in the assets folder from the current directory.
The placeholder image is given by element id "portrait-image".
Use the section headers below:
- Early life
- Career
- Personal life
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
    # Define the regex pattern
    # re.DOTALL makes '.' match newline characters
    # re.IGNORECASE makes the match case-insensitive
    pattern = re.compile(r"(<!DOCTYPE html>.*?</html>)", re.DOTALL | re.IGNORECASE)
    
    # Search for the pattern
    match = pattern.search(content)
    if match:
        clean_html = match.group(1)
        return clean_html
    else:
        print("Error: Could not find a valid <!DOCTYPE html>...</html> block.")
        return content


async def call_anthropic(prompt: str) -> str:
    """Call an Anthropic/Claude-style LLM endpoint."""
    client = AsyncAnthropic(
        api_key=llm_api_key,
        timeout=120.0  # Increase timeout to 120 seconds
    )
    msg = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens= 5120,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    content = msg.content[0].text
    return content


def upload_photo(file_path: str) -> str:
    """Upload user photo to the WavespeedAI media upload endpoint for processing.
    Returns the url of the uploaded image.
    """
    image_url = ""
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist")
        return image_url

    api_url="https://api.wavespeed.ai/api/v3/media/upload/binary"
    headers = {
        "Authorization": f"Bearer {gen_image_api_key}",
    }

    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = httpx.post(api_url, files=files, headers=headers)
        response.raise_for_status()
        json_data = json.loads(response.content.decode('utf-8'))
        image_url = json_data['data']['download_url']
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
        "enable_base64_output": True,
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


async def poll_generated_result(request_id: str) -> str:
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
        await asyncio.sleep(2)
    return return_val


async def download_generated_result(request_id: str, url: str) -> str:
    """Download generated image/video from url.
    Returns local path of saved image/video"""
    saved_image_path = f"assets/{request_id}.jpeg"
    saved_video_path = f"assets/{request_id}.mp4"
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
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            with open(saved_image_path, 'wb') as f:
                f.write(response.content)
                return_val = saved_image_path
                logger.info(f"Saved generated image to {saved_image_path}")

    elif ".mp4" in url:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            with open(saved_video_path, 'wb') as f:
                f.write(response.content)
                return_val = saved_video_path
                logger.info(f"Saved generated video to {saved_video_path}")

    else:
        logger.error(f"Error: download failed!")
    return return_val


def call_sora_video(image_path: str, scene_prompt: str) -> str:
    """Call SORA video generation model.

    Returns path to generated video file. Expect a multipart upload with the image and a prompt.
    Configure SORA_API_URL and SORA_API_KEY.
    """
    url = os.environ.get("SORA_API_URL")
    key = os.environ.get("SORA_API_KEY")
    if not url or not key:
        raise RuntimeError("SORA_API_URL or SORA_API_KEY not set")

    with open(image_path, "rb") as f:
        files = {"image": f}
        data = {"prompt": scene_prompt}
        headers = {"Authorization": f"Bearer {key}"}
        resp = httpx.post(url, files=files, data=data, headers=headers, timeout=180)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    out_path = tempfile.mktemp(suffix=".mp4")
    if "application/json" in content_type:
        js = resp.json()
        b64 = js.get("video_base64") or js.get("b64") or js.get("video")
        if not b64:
            raise RuntimeError("Unexpected JSON response from SORA API: %s" % js)
        with open(out_path, "wb") as out:
            out.write(base64.b64decode(b64))
    else:
        with open(out_path, "wb") as out:
            out.write(resp.content)

    return out_path


def portrait_reload(id):
    if os.path.exists(f"assets/{id}.jpeg"):
        # Open output.html and replace the image src using sync file operations (fine in FastHTML)
        with open("output.html", "r+") as file:
            html_content = file.read()
            soup = BeautifulSoup(html_content, 'html.parser')
        
            # Find the portrait image element by ID and update it
            portrait_img = soup.find('img', id='portrait-image')
            if portrait_img:
                portrait_img['src'] = f"assets/{id}.jpeg"
                
                file.seek(0)
                file.write(str(soup))
                file.truncate()

                # Show the iframe by adding timestamp to force reload
                timestamp = int(time.time())
                show_iframe = Iframe(
                    src=f"/output_file?v={timestamp}",  # Cache busting 
                    style="width:100%; height:80vh; border:0; display:block;",
                    title="Generated biography",
                    id="content-iframe",
                    hx_swap_oob="true"
                )
                return show_iframe
            else:
                logger.warning("Portrait image element not found in HTML")
    else:
        # make post request to self every second
        return Img(id="portrait-image", src=f"assets/portrait.jpg",
                hx_post=f"/portrait_img/{id}",
                hx_trigger='every 1s', hx_swap='innerHTML')

async def start_portrait_generation(photo_path: str, image_prompt: str) -> str:
    """
    Start portrait generation and return request_id immediately.
    The actual image generation happens in background.
    """
    # Upload photo and start generation (these are quick)
    photo_url = upload_photo(photo_path)
    request_id = call_generate_image(photo_url, image_prompt)
    
    # Start the polling and download in background
    asyncio.create_task(complete_portrait_generation(request_id))
    
    return request_id

async def complete_portrait_generation(request_id: str):
    """
    Complete the portrait generation in background.
    Polls for result and downloads when ready.
    The portrait_reload function handles the HTML update and iframe refresh.
    """
    try:
        download_url = await poll_generated_result(request_id)
        await download_generated_result(request_id, download_url)
        logger.info(f"Portrait generation completed for request_id: {request_id}")
        # Note: portrait_reload() will handle updating the HTML and iframe when polled
    except Exception as e:
        logger.error(f"Background portrait generation failed for {request_id}: {str(e)}")

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

# Initialize the app, passing in our custom styles
app, rt = fast_app(hdrs=(style,))

@rt("/portrait_img/{id}")
def get_portrait_img(id:int): return portrait_reload(id)

@rt("/")
def index():
    """
    Main landing page route that displays the application interface.
    
    Returns:
        A titled page containing:
        - Info display area for messages and loading states
        - Hidden iframe for displaying generated Wikipedia content
        - Fixed "Start" button at bottom center for opening the form modal
        - Empty modal placeholder for dynamic modal loading
    """
    start_btn = Button(
        "Start",
        id="start-btn",
        hx_get="/open_modal",       # On click, it calls the /open_modal route
        hx_target="#modal-placeholder", # It will place the response here
        hx_swap="innerHTML"         # It replaces the content of the target
    )

    # This is the placeholder where submitted info will appear
    info_placeholder = Div(
        P("Click 'Start' to enter your details."),
        id="info"
    )
    
    # Hidden iframe that will be shown when content is ready
    content_iframe = Iframe(
        src="/output_file", 
        style="width:100%; height:80vh; border:0; display:none;", 
        title="Generated biography",
        id="content-iframe"
    )
    
    # This is an empty placeholder where the modal will be loaded
    modal_placeholder = Div(id="modal-placeholder")

    # Titled() creates a <title> and <H1>
    # Container() provides Pico CSS's standard page wrapper
    return Titled("Create Your Fictional Wikipedia",
        Container(
            info_placeholder,
            content_iframe,
            start_btn,
            modal_placeholder
        )
    )


@rt("/open_modal")
def open_modal():
    """
    Route that serves the user input modal dialog.
    
    Called via HTMX when the "Start" button is clicked. Creates and returns
    a DialogX modal containing a form for user input.
    
    Returns:
        DialogX modal with:
        - Form fields for name, job, place, and photo upload
        - Submit button that triggers form processing
        - Escape key handler for modal dismissal
        - Auto-focus on the name input field
    """
    return DialogX(
        Article(
            H3("Enter Your Details"),
            Form(
                Input(name="name", placeholder="Name", required=True, autofocus=True),
                Input(name="job", placeholder="Job", required=True),
                Input(name="place", placeholder="The place/environment of where you work", required=True),
                Input(name="photo", placeholder="photo of you with clear face", type="file", accept="image/*", required=True),
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
async def submit_form(name: str, job: str, place: str, photo: UploadFile):
    """
    Route that handles form submission and initiates biography generation.
    
    Receives user input from the modal form, saves the uploaded photo to a
    temporary file, and immediately returns a loading spinner while triggering
    background processing.
    
    Args:
        name (str): Person's name for the biography
        job (str): Person's profession/job title
        place (str): Work environment or location
        photo (UploadFile): User's photo file for AI image generation
    
    Returns:
        Multiple elements with out-of-band swaps:
        - Loading spinner with auto-trigger to start processing
        - Closed modal elements to dismiss the form
        - Clears modal placeholder
    """
    # Save the uploaded photo to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_photo:
        temp_photo.write(await photo.read())
        temp_photo_path = temp_photo.name

    # Return loading spinner immediately 
    loading_display = Div(
        Div(cls="spinner"),
        H3("Generating your biography..."),
        P("This may take a moment. Please wait."),
        cls="loading-container",
        hx_post="/process",
        hx_trigger="load",        
        hx_vals=f'{{"name": "{name}", "job": "{job}", "place": "{place}", "photo_path": "{temp_photo_path}"}}',
        hx_target="#info",
        hx_swap="innerHTML"
    )
    
    # Close the modal using out-of-band swap - replace with empty div
    closed_modal = Div(id="modal-info", hx_swap_oob="true")
    
    # Also clear the modal placeholder
    clear_modal_placeholder = Div(id="modal-placeholder", hx_swap_oob="true")
    
    return loading_display, closed_modal, clear_modal_placeholder


@rt("/process") 
async def process_form(name: str, job: str, place: str, photo_path: str):
    """
    Route that performs the actual biography generation and AI image processing.
    
    Called automatically by HTMX after the loading spinner is displayed.
    Orchestrates the complete workflow: LLM text generation, image upload,
    AI image generation, and file updates.
    
    Args:
        name (str): Person's name for the biography
        job (str): Person's profession/job title  
        place (str): Work environment or location
        photo_path (str): Path to the temporary photo file
    
    Returns:
        On success: Updates to show iframe with generated content
        On error: Error message with retry button
        
    Workflow:
        1. Generate Wikipedia biography text using Anthropic LLM
        2. Upload user photo to WaveSpeed AI service
        3. Generate AI image based on user photo and job context
        4. Update output.html with generated content and new image
        5. Display results in iframe
    """
    try:
        # Call the LLM to generate the biography and image prompt
        llm_prompt, image_prompt = prepare_prompt(name, job, place)
        html_out = await call_anthropic(llm_prompt)
        out = cleanup_html_output(html_out)
        with open("output.html", "w") as f:
            f.write(out)

        # Start portrait image generation in background and get request_id 
        request_id = await start_portrait_generation(photo_path, image_prompt)
        
        # Return updates to show the iframe immediately with the placeholder image
        show_iframe = Iframe(
            src="/output_file", 
            style="width:100%; height:80vh; border:0; display:block;",
            title="Generated biography",
            id="content-iframe",
            hx_swap_oob="true"
        )
        hide_info = Div(
            style="display:none;",
            id="info",
            hx_swap_oob="true"
        )
        
        # Add polling element that uses your existing portrait_img route
        portrait_poller = Div(
            id="portrait-poller",
            hx_post=f"/portrait_img/{request_id}",
            hx_trigger="every 2s",
            hx_target="#content-iframe",
            hx_swap="outerHTML",
            style="display:none;",
            hx_swap_oob="true"
        )
        
        return show_iframe, hide_info, portrait_poller

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


@rt("/show_output")
def show_output():
    """
    Route that switches the view to display generated content.
    
    Hides the info display area and shows the iframe containing
    the generated Wikipedia biography. Used for manually displaying
    content when it already exists.
    
    Returns:
        Multiple elements with out-of-band swaps:
        - Hides the info display area
        - Shows the iframe with generated content
    """
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
    
    return hide_info, show_iframe


@rt("/output_file")
def output_file():
    """
    Route that serves the generated Wikipedia biography HTML file.
    
    Attempts to serve the output.html file containing the generated biography.
    If the file doesn't exist (no content has been generated yet), returns
    a helpful message and manages UI state.
    
    Returns:
        On success: The generated HTML file (output.html)
        On FileNotFoundError: 
        - Message indicating no content exists yet
        - Hides the iframe to prevent loading errors
        - Directs user to use the Start button
    """
    try:
        return File("output.html")
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

serve()
