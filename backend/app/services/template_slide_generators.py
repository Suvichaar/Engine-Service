"""Template-specific slide generators for different HTML templates."""

from __future__ import annotations

from typing import Optional, Protocol

from app.services.template_registry import get_template_definition


DEFAULT_BACKGROUND_IMAGE = "https://media.suvichaar.org/upload/polaris/polarisslide.png"


def configure_template_generators(*, default_background_image: str) -> None:
    global DEFAULT_BACKGROUND_IMAGE
    DEFAULT_BACKGROUND_IMAGE = default_background_image


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


class CuriousTemplate2SlideGenerator:
    """Generator for curious-template-2 template (dynamic slide generation)."""

    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        """Generate AMP slide for curious-template-2 template."""
        # Default background image if none provided
        if not background_image_url:
            background_image_url = DEFAULT_BACKGROUND_IMAGE

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
            <div class="header">📘 Notes Chapter</div>
            <div class="text1">
              {paragraph_escaped}
            </div>
           <div class="footer"><p>&copy;ABC Classes</p></div>
          </div>
        </amp-story-grid-layer>
      </amp-story-page>
        """


class CuriousTemplate1SlideGenerator(CuriousTemplate2SlideGenerator):
    """Generator for curious-template-1 template."""


class TemplateV19SlideGenerator(CuriousTemplate2SlideGenerator):
    """Generator for template-v19."""


# Template Registry
TEMPLATE_GENERATORS: dict[str, TemplateSlideGenerator] = {
    "curious-template-1": CuriousTemplate1SlideGenerator(),
    "curious-template-2": CuriousTemplate2SlideGenerator(),
    "template-v19": TemplateV19SlideGenerator(),
}


def get_slide_generator(template_key: str) -> TemplateSlideGenerator:
    """Resolve a slide generator using the central template registry."""
    definition = get_template_definition(template_key)
    return TEMPLATE_GENERATORS.get(definition.slide_generator, CuriousTemplate2SlideGenerator())
