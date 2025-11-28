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
	SESSION_SECRET_KEY=your-secret-key-from-sesskey-file
	```

## Quickstart
1. Start the application:
	```sh
	python main.py
	```
   The app will launch on `http://localhost:10000` by default.
2. Open your browser and navigate to the provided URL.
3. Click "Start" and fill in your details (name, job, place) and upload a photo to generate a fictional Wikipedia biography with AI-generated portrait and video.

## Deploy
To deploy Fauxpedia:
1. Set all required environment variables on your server. `SESSION_SECRET_KEY` is any random uuid number or your secret phrase.
2. Use a production-ready ASGI server (e.g., Uvicorn or Hypercorn):
	```sh
	uvicorn main:app --host 0.0.0.0 --port 10000
	```
   (Note: The app runs on port 10000 by default in production)
3. Configure HTTPS and reverse proxy as needed for your environment.
4. Ensure a health check endpoint is available at `/health` for monitoring.

Recommended hosting platforms:
- **Render** (https://render.com) - Simple Python app deployment with auto-scaling
- **Railway** (https://railway.app) - Quick deployment with environment variable management
- **Replit** (https://replit.com) - Easy hosting for Python apps with built-in secrets
- **PythonAnywhere** (https://www.pythonanywhere.com) - Python-focused hosting

## Features
- Sessions are now persistent across restarts using a fixed secret key from `SESSION_SECRET_KEY` environment variable.
- Multi-user support implemented with session-aware routing and user-specific asset management.
- Relies on external AI APIs (Anthropic, WaveSpeed, HuggingFace) and requires valid API keys and internet access.
- Image and video generation is asynchronous via background tasks for non-blocking user experience.

## Limitations
- Not compatible with React, Vue, or Svelte; designed for HTML-first, server-rendered apps.
