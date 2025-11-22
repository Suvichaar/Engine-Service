"""Template-specific slide generators for different HTML templates."""

from __future__ import annotations

from typing import Optional, Protocol


class TemplateSlideGenerator(Protocol):
    """Interface for template-specific slide generators."""

    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        """Generate AMP slide HTML for this template."""
        ...


class TestNews1SlideGenerator:
    """Generator for test-news-1 template."""

    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        """Generate AMP slide for test-news-1 template."""
        # Default background image if none provided
        if not background_image_url:
            background_image_url = "https://media.suvichaar.org/upload/polaris/polarisslide.png"

        # Escape HTML in paragraph
        paragraph_escaped = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return f"""
      <amp-story-page id="{slide_id}" auto-advance-after="{slide_id}-audio">
        <amp-story-grid-layer template="fill">
          <amp-img src="{background_image_url}"
            width="720" height="1280" layout="responsive">
          </amp-img>
        </amp-story-grid-layer>
        <amp-story-grid-layer template="fill">
          <amp-video autoplay loop layout="fixed" width="1" height="1" poster="" id="{slide_id}-audio">
            <source type="audio/mpeg" src="{audio_url}">
          </amp-video>
        </amp-story-grid-layer>
        <amp-story-grid-layer template="vertical">
          <div class="centered-container">
            
            <div class="text1">
              {paragraph_escaped}
            </div>
           <div class="footer"><p>©SuvichaarAI</p></div>
          </div>
        </amp-story-grid-layer>
      </amp-story-page>
        """


class TestNews2SlideGenerator:
    """Generator for test-news-2 template (temporary - same as test-news-1)."""

    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        """Generate AMP slide for test-news-2 template (temporary implementation)."""
        # For now, use same structure as test-news-1
        # TODO: Update with test-news-2 specific structure later
        if not background_image_url:
            background_image_url = "https://media.suvichaar.org/upload/polaris/polarisslide.png"

        # Escape HTML in paragraph
        paragraph_escaped = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return f"""
      <amp-story-page id="{slide_id}" auto-advance-after="{slide_id}-audio">
        <amp-story-grid-layer template="fill">
          <amp-img src="{background_image_url}"
            width="720" height="1280" layout="responsive">
          </amp-img>
        </amp-story-grid-layer>
        <amp-story-grid-layer template="fill">
          <amp-video autoplay loop layout="fixed" width="1" height="1" poster="" id="{slide_id}-audio">
            <source type="audio/mpeg" src="{audio_url}">
          </amp-video>
        </amp-story-grid-layer>
        <amp-story-grid-layer template="vertical">
          <div class="centered-container">
            <div class="text1">
              {paragraph_escaped}
            </div>
           <div class="footer"><p>©SuvichaarAI</p></div>
          </div>
        </amp-story-grid-layer>
      </amp-story-page>
        """


# Template Registry
TEMPLATE_GENERATORS: dict[str, TemplateSlideGenerator] = {
    "test-news-1": TestNews1SlideGenerator(),
    "test-news-2": TestNews2SlideGenerator(),
}


def get_slide_generator(template_key: str) -> TemplateSlideGenerator:
    """
    Get template-specific slide generator.

    Handles:
    - File names: "test-news-1" → TestNews1SlideGenerator
    - URLs: "https://example.com/test-news-1.html" → extracts "test-news-1"
    - S3: "s3://bucket/test-news-1.html" → extracts "test-news-1"
    """
    # Extract base template name
    base_name = template_key

    # If URL, extract filename
    if template_key.startswith(("http://", "https://")):
        # Extract filename from URL
        base_name = template_key.split("/")[-1].replace(".html", "")
    elif template_key.startswith("s3://"):
        # Extract filename from S3 path
        base_name = template_key.split("/")[-1].replace(".html", "")
    else:
        # File name - remove extension if present
        base_name = template_key.replace(".html", "")

    # Get generator or default to test-news-1
    return TEMPLATE_GENERATORS.get(base_name, TestNews1SlideGenerator())

