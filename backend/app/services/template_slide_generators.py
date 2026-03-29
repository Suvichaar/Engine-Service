"""Template-specific slide generators keyed by registry metadata."""

from __future__ import annotations

from typing import Optional, Protocol

from app.services.template_registry import get_template_definition

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


class TestNews3SlideGenerator:
    """Generator for test-news-3 template (breaking news style with ticker)."""

    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        """Generate AMP slide for test-news-3 template (breaking news style)."""
        # Default background image if none provided
        if not background_image_url:
            background_image_url = "https://media.suvichaar.org/upload/polaris/polarisslide.png"

        # Escape HTML in paragraph
        paragraph_escaped = paragraph.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return f"""
      <amp-story-page id="{slide_id}" auto-advance-after="{slide_id}-audio">
        <!-- BACKGROUND IMAGE -->
        <amp-story-grid-layer template="fill" class="bg-img">
          <amp-img
            src="{background_image_url}"
            width="720"
            height="1280"
            layout="responsive">
          </amp-img>
        </amp-story-grid-layer>
        
        <!-- BACKGROUND AUDIO -->
        <amp-story-grid-layer template="fill">
          <amp-video autoplay loop layout="fixed" width="1" height="1" poster="" id="{slide_id}-audio">
            <source type="audio/mpeg" src="{audio_url}">
          </amp-video>
        </amp-story-grid-layer>

        <!-- NEWS UI -->
        <amp-story-grid-layer template="vertical">
          <div class="news-layout-wrapper">
            <div class="breaking-news-bar">
              SUVICHAAR LIVE
            </div>
            <div class="content-area">
              <div class="description">
                {paragraph_escaped}
              </div>
            </div>
            <div class="ticker-wrap">
              <div class="ticker-move">
                READ | SHARE | INSPIRE
              </div>
            </div>
          </div>
        </amp-story-grid-layer>
      </amp-story-page>
        """


# Template Registry
TEMPLATE_GENERATORS: dict[str, TemplateSlideGenerator] = {
    "test-news-1": TestNews1SlideGenerator(),
    "test-news-2": TestNews2SlideGenerator(),
    "test-news-3": TestNews3SlideGenerator(),
}


def get_slide_generator(template_key: str) -> TemplateSlideGenerator:
    """Resolve a slide generator using the central template registry."""
    definition = get_template_definition(template_key)
    return TEMPLATE_GENERATORS.get(definition.slide_generator, TestNews1SlideGenerator())
