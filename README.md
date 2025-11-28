# Fauxpedia

## Background
Fauxpedia is a server-rendered hypermedia application built with FastHTML, Starlette, HTMX, and FastTags. It generates fictional Wikipedia-style biographies and images using AI models and provides a modern, interactive web interface.

## How to Install
1. Clone the repository:
	```sh
	git clone <repo-url>
	cd fauxpedia
	```
2. Create and activate a Python virtual environment:
	```sh
	python3 -m venv .venv
	source .venv/bin/activate
	```
3. Install dependencies using uv:
	```sh
	uv sync
	```
4. Set up environment variables in a `.env` file (see example below):
	```env
	ANTHROPIC_API_KEY=your-anthropic-key
	WAVESPEED_API_KEY=your-wavespeed-key
	HFACE_API_KEY=your-hface-key
	HF_SPACE_URL=your-hf-space-url
	IMGBB_API_KEY=your-imgbb-key
	```

## Quickstart
1. Start the application:
	```sh
	python main.py
	```
2. Open your browser and go to `http://localhost:5001`.
3. Click "Start" and fill in your details to generate a fictional Wikipedia biography and AI-generated images.

## Deploy
To deploy Fauxpedia:
1. Set all required environment variables on your server.
2. Use a production-ready ASGI server (e.g., Uvicorn or Hypercorn):
	```sh
	uvicorn main:app --host 0.0.0.0 --port 80
	```
3. Configure HTTPS and reverse proxy as needed for your environment.

Recommended hosting platforms:
- **Render** (https://render.com) - Simple Python app deployment with auto-scaling
- **Railway** (https://railway.app) - Quick deployment with environment variable management
- **Replit** (https://replit.com) - Easy hosting for Python apps with built-in secrets
- **PythonAnywhere** (https://www.pythonanywhere.com) - Python-focused hosting

## Limitations
- Sessions are not persistent across server restarts unless a fixed secret key is provided.
- Only supports single-user output by default; multi-user support requires session-aware routing and asset management.
- Relies on external AI APIs (Anthropic, WaveSpeed, HuggingFace) and may require valid API keys and internet access.
- Not compatible with React, Vue, or Svelte; designed for HTML-first, server-rendered apps.
