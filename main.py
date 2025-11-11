import os, json, time, base64, re, tempfile, logging, asyncio, httpx
from dotenv import load_dotenv, find_dotenv
from anthropic import AsyncAnthropic
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
def expand_prompt(name: str, job: str, place: str) -> str:
    llm_prompt = f"""Expand the prompt for a video generation model to include the subject, scene and motion: \
        the person in the image is a highly successful and famous {job} working at {place}"""
    return llm_prompt

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


def poll_generated_result(request_id: str) -> str:
    """Poll for the result of the generated image/video from request id.
    Returns url or base64 string.
    """
    url = f"https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"
    headers = {"Authorization": f"Bearer {gen_image_api_key}"}
    return_val = ""

    # Poll for results
    begin = time.time()
    while True:
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
        time.sleep(2)
    return return_val


async def download_generated_result(request_id: str, url: str) -> str:
    """Download generated image/video from url.
    Returns local path of saved image/video"""
    saved_image_path = f"assets/{request_id}.jpg"
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


async def call_generate_video(image_path: str, scene_prompt: str) -> str:
    """Call video generation model"""
    return_val = ""

    url = "https://api.wavespeed.ai/api/v3/wavespeed-ai/wan-2.2/i2v-480p"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gen_image_api_key}",
    }
    payload = {
        "duration": 8,
        "seed": -1,
        "image": image_path,
        "prompt": scene_prompt,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()["data"]
        request_id = result["id"]
        return_val = request_id
        logger.info(f"Task submitted successfully. Request ID: {request_id}")
    return return_val


## VIEW ##

# 1. Custom styling for the fixed button and placeholders
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

# 2. Initialize the app, passing in our custom styles
app, rt = fast_app(hdrs=(style,))

# 3. The main page route ("/")
@rt("/")
def index():
    # This button is fixed to the bottom-center of the screen
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
        id="info-display"
    )
    
    # This is an empty placeholder where the modal will be loaded
    modal_placeholder = Div(id="modal-placeholder")

    # Titled() creates a <title> and <H1>
    # Container() provides Pico CSS's standard page wrapper
    return Titled("Create Your Fictional Wikipedia",
        Container(
            info_placeholder,
            start_btn,
            modal_placeholder
        )
    )

# 4. The route that serves the popup modal
@rt("/open_modal")
def open_modal():
    # We return a DialogX component, which is Pico's modal
    # The 'open=True' attribute makes it visible immediately
    return DialogX(
        Article(
            H3("Enter Your Details"),
            Form(
                Input(name="name", placeholder="Name", required=True),
                Input(name="job", placeholder="Job", required=True),
                Input(name="place", placeholder="The place/environment of where you work", required=True),
                Input(name="photo", placeholder="photo of you with clear face", type="file", accept="image/*", required=True),  # Added input for picture file
                Button("Enter", type="submit"),
                
                # --- HTMX Form Configuration ---
                # 1. POST the form data to the /submit route
                hx_post="/submit",
                # 2. Target multiple elements
                hx_target="#info-display",
                # 3. Replace the content 
                hx_swap="innerHTML"
            )
        ),
        # Add escape key handler to close modal and show output.html
        Script("""
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    // Close modal
                    document.getElementById('modal-info').remove();
                    // Load and display output.html
                    htmx.ajax('GET', '/show_output', {
                        target: '#info-display',
                        swap: 'innerHTML'
                    });
                }
            });
        """),
        id="modal-info",
        open=True  # This makes the dialog visible
    )

# 5. The route that handles the form submission
@rt("/submit")
async def submit_form(name: str, job: str, place: str, photo: UploadFile):
    # Save the uploaded photo to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_photo:
        temp_photo.write(await photo.read())
        temp_photo_path = temp_photo.name

    # Return loading spinner immediately 
    loading_display = Div(
        Div(cls="spinner"),
        H3("Generating your biography..."),
        P("This may take a moment. Please wait."),
        cls="loading-container"
    )
    
    # Close the modal using out-of-band swap - replace with empty div
    closed_modal = Div(id="modal-info", hx_swap_oob="true")
    
    # Also clear the modal placeholder
    clear_modal_placeholder = Div(id="modal-placeholder", hx_swap_oob="true")
    
    # Start the processing in the background by triggering another request
    trigger_processing = Script(f"""
        setTimeout(function() {{
            htmx.ajax('POST', '/process', {{
                values: {{
                    name: '{name}',
                    job: '{job}',
                    place: '{place}',
                    photo_path: '{temp_photo_path}'
                }},
                target: '#info-display',
                swap: 'innerHTML'
            }});
        }}, 500);
    """)
    
    return loading_display, closed_modal, clear_modal_placeholder, trigger_processing

@rt('/video_status')
def video_status(vid: str):
    """Simple status endpoint polled by the generated output page.
    Returns JSON: {ready: bool, url: str}
    """
    video_path = os.path.join('assets', f"{vid}.mp4")
    if os.path.exists(video_path):
        # return a URL relative to the app root so the iframe can load it
        return {"ready": True, "url": f"assets/{vid}.mp4"}
    else:
        return {"ready": False}

# 6. The route that handles the actual processing
@rt("/process") 
async def process_form(name: str, job: str, place: str, photo_path: str):
    try:
        # Call the LLM to generate the biography and image prompt
        llm_prompt, image_prompt, video_prompt = prepare_prompt(name, job, place)
        # html_out = await call_anthropic(llm_prompt)
        # out = cleanup_html_output(html_out)
        # with open("output.html", "w") as f:
        #     f.write(out)

        # # Upload the user photo to the generative image service
        # photo_url = upload_photo(photo_path)
        # request_id = call_generate_image(photo_url, image_prompt)
        # download_url = poll_generated_result(request_id)
        # image_path = await download_generated_result(request_id, download_url)

        # # Update the portrait image in output.html
        image_path = "assets/portrait.jpg"
        with open("output.html", "r+") as file:
            html_content = file.read()
            updated_html = html_content.replace(
                'id="portrait-image" src="assets/portrait.jpg"',
                f'id="portrait-image" src="{image_path}"'
            )
            file.seek(0) # reset to beginning to overwrite
            file.write(updated_html)
            file.truncate()

        image_id = "https://d1q70pf5vjeyhc.cloudfront.net/predictions/605d60a14dc04800b3a9da3cfffdc760/1.jpeg"
        video_request_id = await call_generate_video(image_id, video_prompt)
        download_url = poll_generated_result(video_request_id)
        await download_generated_result(video_request_id, download_url)

        # If we have a request_id (image/video task id), inject a small polling script
        # that will check the /video_status endpoint and replace the image with the video when ready.
        if video_request_id:
            # Build the polling script using a placeholder replacement instead of
            # the % operator. The original used "%s" % (video_request_id,)
            # but the script contains literal percent signs (eg '100%') which
            # confuse Python's % formatting and raise "not enough arguments"
            # or similar formatting errors. We use json.dumps() to safely
            # produce a quoted JS string and replace a unique placeholder.
            poll_template = """
<script>
(function() {
    var vidId = PLACEHOLDER_VID_ID;
    function check() {
        fetch('/video_status?vid=' + encodeURIComponent(vidId))
            .then(function(r) { return r.json(); })
            .then(function(j) {
                if(j.ready) {
                    try {
                        var img = document.getElementById('portrait-image');
                        if(!img) return;
                        var video = document.createElement('video');
                        video.setAttribute('autoplay', '');
                        video.setAttribute('loop', '');
                        video.setAttribute('muted', '');
                        video.setAttribute('playsinline', '');
                        video.style.maxWidth = '100%';
                        video.style.height = 'auto';
                        var source = document.createElement('source');
                        source.src = j.url;
                        source.type = 'video/mp4';
                        video.appendChild(source);
                        img.parentNode.replaceChild(video, img);
                    } catch(e) { console.error(e); }
                } else {
                    setTimeout(check, 2000);
                }
            }).catch(function() { setTimeout(check, 2000); });
    }
    // start after a short delay so the iframe content has a chance to render
    setTimeout(check, 1500);
})();
</script>
"""

        # Use json.dumps to produce a safe JS string (properly quoted/escaped)
        poll_script = poll_template.replace("PLACEHOLDER_VID_ID", json.dumps(video_request_id))

        with open("output.html", "r+") as file:
            html_content = file.read()
            # Insert poll_script before </body> if present, otherwise append
            if re.search(r'</body>', html_content, flags=re.IGNORECASE):
                    html_content = re.sub(r'</body>', poll_script + '</body>', html_content, flags=re.IGNORECASE)
            else:
                html_content = html_content + poll_script
            file.seek(0) # reset to beginning to overwrite
            file.write(html_content)
            file.truncate()

            # Return an iframe so the full generated page is shown immediately
            iframe_html = '<iframe src="/output_file" style="width:100%; height:80vh; border:0;" title="Generated biography"></iframe>'
            return iframe_html

    except Exception as e:
        logger.error(f"Error processing form: {str(e)}")
        return Div(
            H3("Error"),
            P(f"An error occurred while generating your biography: {str(e)}"),
            Button("Try Again", hx_get="/open_modal", hx_target="#modal-placeholder", hx_swap="innerHTML"),
            cls="loading-container"
        )


# Route to show output.html when escape key is pressed — return an iframe
@rt("/show_output")
def show_output():
    iframe_html = '<iframe src="/output_file" style="width:100%; height:80vh; border:0;" title="Generated biography"></iframe>'
    return iframe_html


# Serve the generated output.html as a full page so it can be embedded in an iframe
@rt("/output_file")
def output_file():
    try:
        return File("output.html")
    except FileNotFoundError:
        return Div(
            H3("No Content Yet"),
            P("No biography has been generated yet. Please fill out the form to create one."),
            Button("Start", hx_get="/open_modal", hx_target="#modal-placeholder", hx_swap="innerHTML"),
            cls="loading-container"
        )

serve()
