from fastcore.parallel import threaded
from fasthtml.common import *
import os
from gradio_client import Client

app = FastHTML(hdrs=(picolink,))

# Initialize the Gradio client
client = Client("multimodalart/Qwen-Image-Fast") 

# Store our generations
generations = []
folder = f"generated_assets"
os.makedirs(folder, exist_ok=True)

# Main page
@app.get("/")
def home():
    inp = Input(id="new-prompt", name="prompt", placeholder="Enter a prompt")
    add = Form(Group(inp, Button("Generate")), hx_post="/", target_id='gen-list', hx_swap="afterbegin")
    gen_list = Div(id='gen-list')
    return Title('Image Generation Demo'), Main(H1('Magic Image Generation'), add, gen_list, cls='container')

# A pending preview keeps polling this route until we return the image preview
def generation_preview(id):
    if os.path.exists(f"{folder}/{id}.png"):
        return Div(Img(src=f"{folder}/{id}.png"), id=f'gen-{id}')
    else:
        # make post request to self every second
        return Div("Generating...", id=f'gen-{id}', 
                   hx_post=f"/generations/{id}",
                   hx_trigger='every 1s', hx_swap='outerHTML')
    
@app.post("/generations/{id}")
def get(id:int): return generation_preview(id)
    

# For images, CSS, etc.
@app.get("/{fname:path}.{ext:static}")
def static(fname:str, ext:str): return FileResponse(f'{fname}.{ext}')

# Generation route
@app.post("/")
def post(prompt:str):
    id = len(generations)
    generate_and_save(prompt, id)
    generations.append(prompt)
    clear_input =  Input(id="new-prompt", name="prompt", placeholder="Enter a prompt", hx_swap_oob='true')
    return generation_preview(id), clear_input

# Generate an image and save it to the folder (in a separate thread)
@threaded
def generate_and_save(prompt, id):
    result = client.predict(
			prompt=prompt,
			seed=0,
			randomize_seed=True,
			aspect_ratio="16:9",
			guidance_scale=1,
			num_inference_steps=8,
			prompt_enhance=True,
			api_name="/infer"
	)
    with open(f"assets/{id}.png", "wb") as f:
        with open(result[0], "rb") as image_bytes:
            f.write(image_bytes.read())

serve()