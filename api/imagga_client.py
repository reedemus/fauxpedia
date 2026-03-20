"""Image upload service (imgBB) client."""

import json
import httpx
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class ImgBBClient:
    """Client for imgBB image hosting service."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("IMGBB_API_KEY")
        self.api_url = "https://api.imgbb.com/1/upload"
        self.expiration = 600  # 10 minutes

    def upload_photo(self, file_path: str) -> str:
        """Upload user photo to imgBB for temporary storage.

        Args:
            file_path: Path to the local image file

        Returns:
            URL of the uploaded image

        Raises:
            ValueError: If file doesn't exist or upload fails
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File {file_path} does not exist")

        if not self.api_key:
            raise ValueError("IMGBB_API_KEY not set")

        parameters = {"expiration": self.expiration, "key": self.api_key}

        with open(file_path, 'rb') as f:
            files = {'image': f}
            response = httpx.post(self.api_url, files=files, params=parameters, timeout=30)
            response.raise_for_status()

        json_data = response.json()
        if json_data.get('success'):
            image_url = json_data['data']['image']['url']
            logger.info(f"Upload successful! Download url: {image_url}")
            return image_url
        else:
            raise ValueError(f"Upload failed: {json_data.get('error', 'Unknown error')}")
