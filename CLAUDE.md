# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

Fauxpedia is a server-rendered hypermedia application that generates fictional Wikipedia-style biographies with AI-generated images and video. The architecture follows a synchronous, file-based approach with background task processing using FastHTML and HTMX.

### Project Structure (Refactored)

```
fauxpedia/
├── main.py                           # Application entry point, app setup, route registrations
├── config/
│   ├── __init__.py                   # Module exports
│   ├── settings.py                   # AppSettings dataclass, logging initialization
│   └── credentials.py                # Environment variable loading
├── api/
│   ├── __init__.py                   # Module exports
│   ├── anthropic_client.py           # Async Anthropic Claude API client
│   ├── imagga_client.py              # imgBB image upload client
│   ├── wavespeed_client.py           # WaveSpeed image generation API client
│   └── huggingface_client.py         # HuggingFace video generation via gradio-client
├── html_presenter/                   # Note: renamed from 'html' to avoid conflict with stdlib
│   ├── __init__.py
│   ├── prompts.py                    # LLM prompt templates (static methods)
│   └── output_manager.py             # HTML file generation and updates
├── tasks/
│   ├── __init__.py
│   ├── portrait_generator.py         # Background image generation workflow
│   ├── video_generator.py            # Background video generation workflow
│   └── biography_generator.py        # Text generation orchestrator
├── routes/
│   ├── __init__.py
│   ├── main.py                       # Main UI routes (index, modal, form processing)
│   ├── polling.py                    # Portrait/video polling endpoints
│   ├── assets.py                     # Asset management (clear, list)
│   └── static_files.py               # Static file serving
├── utils/
│   ├── __init__.py
│   └── fileops.py                    # Shared file operations (save image, video, webcam)
├── static/
│   ├── css/webcam.css
│   └── js/webcam.js
├── generated/                        # AI-generated images and videos
└── output.html                       # Generated biography (overwritten per session)
```

### Key Components

**Web Framework**: FastHTML (on top of Starlette) with HTMX for interactive UI updates. Routes are registered using the `@rt(...)` decorator on a `fast_app()` instance.

**AI Integration Chain**:
1. **Text Generation**: Anthropic API (Claude Sonnet 4.5) generates the Wikipedia biography HTML
2. **Image Generation**: WaveSpeed API for image inpainting/editing based on user photo
3. **Video Generation**: HuggingFace space via `gradio-client` for video generation
4. **Image Captioning**: Anthropic API generates captions to improve video prompts

### Workflow

```
User Input → LLM Biography → Upload Photo → Gen Image → Gen Video
                              (background)    (background)
```

1. User submits name, job, place, and photo
2. LLM generates HTML biography with placeholder image/video tags
3. Photo uploads to external service (imgBB)
4. Background task polls for generated image from WaveSpeed
5. Background task generates video caption + prompt via LLM
6. Background task submits to HF video generation space
7. Background task polls for video completion
8. output.html is mutated directly to update assets

### State Management

- **No database**: Generated content written to `output.html`
- **Asset storage**: `./generated/` folder with request IDs as filenames
- **Sessions**: Not persistent across restarts (uses default FastHTML session handling)

### HTMX Pattern

The app uses out-of-band (OOB) swaps for progressive enhancement:
- Loading spinners shown via `hx_swap_oob="true"`
- Polling endpoints check for asset completion
- IFRAME refreshes triggered upon asset readiness

### Key Patterns

1. **Dependency Injection**: API clients and generators are instantiated in `main.py` and passed to routes
2. **BackgroundTask**: Starlette's `BackgroundTask` class used for async operations (not asyncio.create_task)
3. **File-based polling**: Frontend polls endpoints to check if generated assets exist
4. **Static prompt templates**: `PromptTemplates` class provides immutable prompt strings

## Commands

```sh
# Development server (hot reload)
uv run python main.py

# Production (with uvicorn)
uvicorn main:app --host 0.0.0.0 --port 80

# Install dependencies (if rebuild needed)
uv sync
```

## Environment Variables

Required via `.env` file:
- `ANTHROPIC_API_KEY` - Claude for text generation
- `OPENROUTER_API_KEY` - WaveSpeed image API
- `HFACE_API_KEY` - HuggingFace token
- `HF_SPACE_URL` - Video generation space URL
- `IMGBB_API_KEY` - Image hosting service

## Gotchas

1. **File-based state**: `output.html` is mutated directly; not concurrent-user safe
2. **Background tasks**: Use `BackgroundTask` class from Starlette, not `asyncio.create_task`
3. **Polling pattern**: Frontend polls `/portrait_img/{id}` and `/video_status/{id}`
4. **Session expiring**: API keys are read at startup; no runtime reload
5. **Image size**: WaveSpeed generates 1024x1536 (portrait 2:3 ratio)
6. **Module naming conflict**: The `html/` directory was renamed to `html_presenter/` to avoid conflict with Python's stdlib `html` module
