"""WaveSpeed AI image/video generation API client."""

import time
import httpx
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class WaveSpeedClient:
    """Client for WaveSpeed AI image generation API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.base_url = "https://api.wavespeed.ai/api/v3"
        self.poll_interval = 1  # seconds

    def generate_image(self, face_image_url: str, prompt: str, size: str = "1024*1536") -> str:
        """Call image generation API.

        Args:
            face_image_url: URL of the source face image
            prompt: Prompt describing the desired generation
            size: Output image size (default 1024x1536 portrait)

        Returns:
            Request ID for polling generation result
        """
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        url = f"{self.base_url}/bytedance/seedream-v4/edit"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "enable_base64_output": False,
            "enable_sync_mode": False,
            "images": [face_image_url],
            "prompt": prompt,
            "size": size
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()["data"]
        request_id = result["id"]
        logger.info(f"Called gen image API with request ID: {request_id}")
        return request_id

    def poll_result(self, request_id: str, timeout: int = 300) -> Optional[str]:
        """Poll for the result of a generative task.

        Args:
            request_id: The request ID returned by generate_image
            timeout: Maximum time to poll in seconds

        Returns:
            URL or base64 string of the generated image, or None if failed
        """
        url = f"{self.base_url}/predictions/{request_id}/result"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        begin = time.time()
        status = "in progress"

        while status == "in progress":
            response = httpx.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                result_json = response.json()["data"]
                status = result_json["status"]
                if status == "completed":
                    end = time.time()
                    logger.info(f"Image generation completed in {end - begin:.2f} seconds.")
                    return result_json["outputs"][0]
                elif status == "failed":
                    logger.error(f"Image generation failed: {result_json.get('error')}")
                    return None
                else:
                    logger.info(f"Image generation in progress. Status: {status}")
            else:
                logger.error(f"Error polling status: {response.status_code}, {response.text}")
                return None

            if time.time() - begin > timeout:
                logger.error(f"Polling timeout after {timeout} seconds")
                return None

            time.sleep(self.poll_interval)

        return None
