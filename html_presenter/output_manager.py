"""Manager for generated HTML output files."""

from pathlib import Path
from bs4 import BeautifulSoup, Tag
import logging

logger = logging.getLogger(__name__)


class OutputManager:
    """Manages the output.html file and its content."""

    def __init__(self, output_path: Path = Path("output.html")):
        self.output_path = output_path

    def write_full_html(self, content: str) -> None:
        """Write complete HTML content to output file."""
        cleaned = self._cleanup_html(content)
        self.output_path.write_text(cleaned)
        logger.info(f"Wrote HTML to {self.output_path}")

    def update_image_src(self, element_id: str, image_path: Path) -> bool:
        """Update image source in existing HTML."""
        soup = self._parse_output()
        element = soup.find(id=element_id)

        if not element:
            logger.warning(f"Element {element_id} not found in {self.output_path}")
            return False

        element['src'] = str(image_path)
        self._write_back(soup)
        return True

    def update_video_src(self, element_id: str, video_path: Path) -> None:
        """Update video source in existing HTML."""
        soup = self._parse_output()
        element = soup.find(id=element_id)

        if element:
            element['src'] = str(video_path)
            element['loop'] = ""
            self._write_back(soup)

    def get_element(self, element_id: str) -> Tag | None:
        """Find an element by ID in output.html."""
        soup = self._parse_output()
        return soup.find(id=element_id)

    def _cleanup_html(self, content: str) -> str:
        """Extract HTML block and fix missing tags."""
        doctype_pos = content.find("<!DOCTYPE html>")
        if doctype_pos != -1:
            content = content[doctype_pos:]

        parsed = BeautifulSoup(content, 'html.parser')
        return parsed.prettify()

    def _parse_output(self) -> BeautifulSoup:
        """Parse output.html into BeautifulSoup object."""
        content = self.output_path.read_text()
        return BeautifulSoup(content, 'html.parser')

    def _write_back(self, soup: BeautifulSoup) -> None:
        """Write BeautifulSoup back to file."""
        self.output_path.write_text(str(soup))
        logger.info(f"Updated {self.output_path}")
