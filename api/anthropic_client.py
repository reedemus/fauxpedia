"""Async Anthropic client for LLM interactions."""

from anthropic import AsyncAnthropic
from typing import Union
import base64
import logging

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Async client for Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def call_with_image(
        self,
        prompt: str,
        image_path: str,
        is_url: bool = False
    ) -> str:
        """Call LLM with an image attachment."""
        if is_url:
            content = self._create_url_image_payload(prompt, image_path)
        else:
            content = self._create_base64_image_payload(prompt, image_path)

        result = await self._execute_request(content)
        return result

    async def call_text_only(self, prompt: str) -> str:
        """Call LLM with text-only input."""
        result = await self._execute_request(prompt)
        return result

    def _create_url_image_payload(self, prompt: str, image_url: str) -> list:
        return [
            {"type": "image", "source": {"type": "url", "url": image_url}},
            {"type": "text", "text": prompt}
        ]

    def _create_base64_image_payload(self, prompt: str, image_path: str) -> list:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_data,
                },
            },
            {"type": "text", "text": prompt}
        ]

    async def _execute_request(self, content: Union[str, list]) -> str:
        async with self.client.messages.stream(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=8192,
        ) as stream:
            async for _ in stream.text_stream:
                pass

        final_message = await stream.get_final_message()
        output_tokens = final_message.usage.output_tokens
        logger.info(f"Used {output_tokens} output tokens.")

        return await stream.get_final_text()
