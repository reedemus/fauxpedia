"""Environment variable loading utilities."""

import os
from typing import Optional
from dotenv import load_dotenv, find_dotenv


def load_environment() -> None:
    """Load environment variables from .env file."""
    load_dotenv(find_dotenv())


def get_env_var(name: str) -> Optional[str]:
    """Get an environment variable, returns None if not set."""
    return os.environ.get(name)


def get_api_keys() -> dict:
    """Load all required API keys."""
    return {
        "anthropic": get_env_var("ANTHROPIC_API_KEY"),
        "openrouter": get_env_var("OPENROUTER_API_KEY"),
        "huggingface": get_env_var("HFACE_API_KEY"),
        "imgbb": get_env_var("IMGBB_API_KEY"),
    }
