"""Asset management endpoints with authentication."""

from pathlib import Path
from fasthtml.common import *
import datetime as dt
import os
import logging

from config.settings import AppSettings


class AssetRoutes:
    """Handles asset management endpoints."""

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def clear_assets(self, request) -> dict | Response:
        """Authenticated endpoint to clear all generated assets."""
        if not self._check_auth(request):
            return Response("Unauthorized", 401)

        try:
            assets_path = Path.cwd() / self.settings.gen_folder

            if not assets_path.exists():
                assets_path.mkdir(parents=True, exist_ok=True)
                return {"status": "success", "message": f"Created empty {self.settings.gen_folder} directory"}

            for file_path in assets_path.iterdir():
                if file_path.is_file():
                    file_path.unlink()

            # Clear generated HTML files
            for html_file in Path.cwd().glob("*.html"):
                html_file.unlink()

            return {"status": "success", "message": f"Successfully cleared {self.settings.gen_folder} directory"}

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error clearing assets: {e}")
            return {"status": "error", "message": str(e)}, 500

    def list_assets(self, request) -> dict:
        """List all files in the generated assets directory."""
        if not self._check_auth(request):
            return Response("Unauthorized", 401)

        try:
            assets_path = Path.cwd() / self.settings.gen_folder
            if not assets_path.exists():
                return {"status": "error", "message": f"Directory {self.settings.gen_folder} does not exist"}, 404

            files = []
            for file_path in assets_path.iterdir():
                if file_path.is_file():
                    files.append({
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "last_modified": dt.datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })

            return {"status": "success", "files": files}

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error listing assets: {e}")
            return {"status": "error", "message": str(e)}, 500

    def _check_auth(self, request) -> bool:
        """Check Authorization header matches expected format."""
        api_key = request.headers.get("Authorization")
        expected = f"Bearer {os.environ.get('ANTHROPIC_API_KEY')}"
        return api_key == expected
