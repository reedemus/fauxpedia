"""Prompt templates for LLM interactions."""

from typing import Tuple


class PromptTemplates:
    """Static prompt templates for LLM interactions."""

    @staticmethod
    def get_image_caption() -> str:
        """Prompt for generating image captions."""
        return """Provide a detailed caption for the image provided.
The caption should describe the subject, setting, and any notable features in the image."""

    @staticmethod
    def prepare_video_prompt(description: str) -> str:
        """Prompt for converting image description to video prompt."""
        return f"""Given the description below, write a prompt for a video generation model.
**Description**
{description}
Use the section headers below, keep it concise and emphasize the motion aspects:
- Subject
- Scene
- Motion"""

    @staticmethod
    def prepare_biography(name: str, job: str, place: str) -> str:
        """Prompt for generating Wikipedia-style biography."""
        return f"""
Create a fictional and funny wikipedia biography of {name} as a {job} from {place}.
The output format must be html and css in typical wikipedia format. Strictly no emojis in the output.
Use the placeholder image at src="/static/portrait.jpg" with element id "portrait-image".
Use the placeholder video at src="/static/portrait.mp4" with element id "portrait-video".
Use the section headers below:
- Early life
- Career
- Personal life
- My typical work day
  (place the video element here)
- Awards and Achievements
- Wealth
- Scandals
- References
- Further reading
    """

    @staticmethod
    def prepare_image_prompt(job: str, place: str) -> str:
        """Prompt for AI image generation."""
        return f"Create a photo of the attached image as a {job} performing his job in {place}."

    @staticmethod
    def prepare_biography_and_image_prompt(name: str, job: str, place: str) -> Tuple[str, str]:
        """Generate both biography and image prompts."""
        biography_prompt = PromptTemplates.prepare_biography(name, job, place)
        image_prompt = PromptTemplates.prepare_image_prompt(job, place)
        return biography_prompt, image_prompt
