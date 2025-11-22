# Implementation Plan v0 - Curious Mode with Multiple Templates

## Overview
Implement complete Curious mode support with multiple templates, template-specific slide generators, and full feature parity with News mode.

---

## Current State Analysis

### ✅ What Exists
- `app/curious_template/curious-template-1.html` - Quiz template exists (for quizzes, not stories)
- `CuriousModelClient` - Basic implementation exists
- `curious.py` prompt template - Defined
- Basic narrative generation - Working

### ❌ What's Missing
- **NEW**: Story generation template for curious mode (curious-default.html)
- Template-specific slide generators for curious story mode
- `slide_count` support in CuriousModelClient
- Default image handling for curious mode
- Template registry entries for curious story templates
- `<!--INSERT_SLIDES_HERE-->` placeholder in curious story template
- Orchestrator integration for slide_count
- HTML renderer support for curious mode images

### ⚠️ Important Note
The existing `curious-template-1.html` is a **quiz template** with interactive quiz elements. We need to create a **separate story template** for narrative story generation (similar to news templates).

---

## Implementation Tasks

### Phase 1: Template Setup

#### Task 1.1: Create Curious Story Template
**File**: `app/curious_template/curious-default.html` (NEW FILE)

**Action**:
- Create new template file for curious story generation
- Structure: Cover slide → `<!--INSERT_SLIDES_HERE-->` → CTA slide
- Use placeholders: `{{storytitle}}`, `{{potraitcoverurl}}`, `{{storytitle_audiourl}}`, etc.
- Match structure similar to `test-news-1.html` but with curious-specific styling
- Add `<!--INSERT_SLIDES_HERE-->` placeholder between cover and CTA

**Template Structure**:
```html
<amp-story>
  <!-- Cover Slide -->
  <amp-story-page id="cover-slide">
    <!-- Uses {{potraitcoverurl}} and {{storytitle}} -->
  </amp-story-page>
  
  <!--INSERT_SLIDES_HERE-->
  
  <!-- CTA Slide -->
  <amp-story-page id="cta-slide">
    <!-- Uses {{potraitcoverurl}} -->
  </amp-story-page>
</amp-story>
```

**Note**: Keep `curious-template-1.html` (quiz template) separate - it's for a different use case.

**Expected Result**:
```html
<amp-story-page id="cover-slide">...</amp-story-page>
<!--INSERT_SLIDES_HERE-->
<amp-story-page id="cta-slide">...</amp-story-page>
```

---

### Phase 2: Template-Specific Slide Generators

#### Task 2.1: Create CuriousDefaultSlideGenerator
**File**: `app/services/template_slide_generators.py`

**Action**:
- Create `CuriousDefaultSlideGenerator` class
- Implement `generate_slide()` method matching `curious-default.html` structure
- Use appropriate CSS classes from the template (e.g., `curious-container`, `curious-text`)
- Handle HTML escaping
- Support default background images

**Code Structure**:
```python
class CuriousDefaultSlideGenerator:
    """Generator for curious-default template."""
    
    def generate_slide(
        self,
        paragraph: str,
        audio_url: str,
        background_image_url: Optional[str] = None,
        slide_id: str = "slide",
    ) -> str:
        # Match the HTML structure in curious-default.html
        # Use appropriate CSS classes (curious-container, curious-text, etc.)
        # Return AMP story page HTML
```

**Requirements**:
- Match the exact HTML structure from `curious-default.html`
- Use correct CSS classes (curious-container, curious-text, curious-footer)
- Default background image: `polarisslide.png`
- HTML escape paragraph text
- Include audio video element
- Follow same pattern as TestNews1SlideGenerator

---

#### Task 2.2: Update Template Registry
**File**: `app/services/template_slide_generators.py`

**Action**:
- Add curious template generators to `TEMPLATE_GENERATORS` dictionary
- Update `get_slide_generator()` to handle curious templates
- Organize code with clear sections (News vs Curious)

**Code Changes**:
```python
TEMPLATE_GENERATORS: dict[str, TemplateSlideGenerator] = {
    # News mode templates
    "test-news-1": TestNews1SlideGenerator(),
    "test-news-2": TestNews2SlideGenerator(),
    
    # Curious mode templates (story generation)
    "curious-default": CuriousDefaultSlideGenerator(),
    # Future: "curious-modern": CuriousModernSlideGenerator(),
    
    # Note: "curious-template-1" is a quiz template, not for story generation
}
```

---

### Phase 3: CuriousModelClient Enhancement

#### Task 3.1: Add slide_count Support
**File**: `app/services/model_clients.py`

**Action**:
- Update `CuriousModelClient.generate()` method signature
- Add `slide_count` parameter (optional, default None)
- Limit sections based on slide_count
- Calculate middle slides: `slide_count - 2` (cover + CTA)

**Code Changes**:
```python
def generate(
    self, 
    prompt: RenderedPrompt, 
    insights: DocInsights,
    slide_count: Optional[int] = None,  # NEW
) -> NarrativeResponse:
    user_prompt = self._compose_user_prompt(prompt.user, insights)
    raw_output = self._language_model.complete(prompt.system, user_prompt)
    sections = self._split_sections(raw_output)
    
    # NEW: Limit sections based on slide_count
    if slide_count:
        middle_slides_count = max(0, slide_count - 2)  # Exclude cover (1) and CTA (1)
        sections = sections[:middle_slides_count] if middle_slides_count > 0 else sections
    
    slide_deck = _build_slide_deck(sections, self._template_key, prompt.metadata.get("language"))
    # ... rest of the method
```

**Requirements**:
- Maintain backward compatibility (slide_count is optional)
- Handle edge cases (slide_count < 2, too many sections)
- Log slide count decisions

---

### Phase 4: Orchestrator Integration

#### Task 4.1: Pass slide_count to CuriousModelClient
**File**: `app/services/orchestrator.py`

**Action**:
- Update orchestrator to pass `slide_count` to CuriousModelClient
- Add conditional logic similar to News mode
- Ensure both modes get slide_count support

**Code Changes**:
```python
# Around line 112-126
if payload.mode == Mode.NEWS and hasattr(model_client, 'generate'):
    narrative = model_client.generate(
        rendered_prompt,
        doc_insights,
        slide_count=payload.slide_count,
        category=request.category,
        subcategory=None,
        emotion=None,
    )
elif payload.mode == Mode.CURIOUS and hasattr(model_client, 'generate'):
    # NEW: Pass slide_count to CuriousModelClient
    narrative = model_client.generate(
        rendered_prompt,
        doc_insights,
        slide_count=payload.slide_count,  # NEW
    )
else:
    narrative = model_client.generate(rendered_prompt, doc_insights)
```

**Requirements**:
- Check if model_client has generate method
- Pass slide_count only if available
- Maintain error handling

---

### Phase 5: HTML Renderer - Curious Mode Support

#### Task 5.1: Add Curious Mode Default Image Handling
**File**: `app/services/html_renderer.py`

**Action**:
- Update `PlaceholderMapper.map()` method
- Add handling for Curious mode with no image_source
- Set default images for curious mode (similar to news mode)
- Generate placeholder values for `s1image1`, `s2image1`, etc.

**Code Changes**:
```python
# In PlaceholderMapper.map() method, around line 141-197

# Images - Special handling for News mode with no image_source
if record.mode == Mode.NEWS and not record.image_assets:
    # ... existing news mode logic ...
elif record.mode == Mode.CURIOUS and not record.image_assets:
    # NEW: Curious mode + no image_source → use default images
    default_cover = self._default_cover_image
    default_bg = self._default_bg_image
    placeholders["image0"] = default_cover
    placeholders["potraitcoverurl"] = self._generate_resized_url(default_cover, 720, 1280)
    placeholders["portraitcoverurl"] = placeholders["potraitcoverurl"]
    placeholders["msthumbnailcoverurl"] = self._generate_resized_url(default_cover, 300, 300)
    # Set default images for all slides
    for idx in range(1, len(record.slide_deck.slides) + 1):
        placeholders[f"s{idx}image1"] = default_bg
elif image_source == "custom" and record.image_assets:
    # ... existing custom image logic ...
```

**Requirements**:
- Use same default images as news mode (polariscover.png, polarisslide.png)
- Generate resized URLs for cover (720x1280) and thumbnail (300x300)
- Set `s1image1`, `s2image1`, etc. for all slides

---

#### Task 5.2: Update _generate_all_slides for Curious Mode
**File**: `app/services/html_renderer.py`

**Action**:
- Ensure `_generate_all_slides()` works correctly for curious mode
- Verify template key extraction works for curious templates
- Test that correct generator is selected

**Requirements**:
- Template key "curious-template-1" should map to CuriousTemplate1SlideGenerator
- Default image handling should work
- Audio mapping should work correctly

---

### Phase 6: Template Structure Verification

#### Task 6.1: Verify curious-template-1.html Structure
**File**: `app/curious_template/curious-template-1.html`

**Action**:
- Verify cover slide uses `{{potraitcoverurl}}` or `{{image0}}`
- Verify CTA slide uses `{{potraitcoverurl}}` or `{{image0}}`
- Check all placeholders are properly defined
- Ensure `<!--INSERT_SLIDES_HERE-->` exists

**Placeholders to Verify**:
- `{{storytitle}}` - Cover slide title
- `{{storytitle_audiourl}}` - Cover slide audio
- `{{potraitcoverurl}}` - Cover and CTA images
- `{{image0}}` - Alternative cover image
- `{{pagetitle}}` - Page title
- `{{metadescription}}` - Meta description
- `{{publishedtime}}` - Publication time
- All other placeholders from PlaceholderMapper

---

### Phase 7: Testing & Validation

#### Task 7.1: Create Test JSON for Curious Mode
**File**: `example_curious_mode.json`

**Action**:
- Create example JSON payload for curious mode
- Include all required fields
- Test with different image sources (ai, pexels, custom)
- Test with different slide counts

**Example**:
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 5,
  "user_input": "How does quantum computing work?",
  "image_source": "ai",
  "prompt_keywords": [
    "quantum",
    "computing",
    "science"
  ],
  "voice_engine": "azure_basic"
}
```

---

#### Task 7.2: Test Complete Flow
**Action**:
- Test story generation with curious mode
- Verify HTML output is generated
- Check that slides are inserted correctly
- Verify images and audio are mapped
- Test with different slide counts

---

## File Structure After Implementation

```
app/
├── curious_template/
│   ├── curious-template-1.html         ✅ Exists (quiz template - keep separate)
│   └── curious-default.html            ⚠️  CREATE: Story generation template
│
├── news_template/
│   ├── test-news-1.html                 ✅ Exists
│   └── test-news-2.html                 ✅ Exists
│
└── services/
    ├── template_slide_generators.py     ⚠️  Update: Add CuriousDefaultSlideGenerator
    ├── model_clients.py                  ⚠️  Update: Add slide_count to CuriousModelClient
    ├── orchestrator.py                   ⚠️  Update: Pass slide_count to CuriousModelClient
    └── html_renderer.py                  ⚠️  Update: Add curious mode image handling
```

---

## Implementation Checklist

### Phase 1: Template Setup
- [ ] Create `curious-default.html` template file
- [ ] Add cover slide with placeholders (`{{potraitcoverurl}}`, `{{storytitle}}`, `{{storytitle_audiourl}}`)
- [ ] Add `<!--INSERT_SLIDES_HERE-->` placeholder
- [ ] Add CTA slide with placeholders
- [ ] Verify all required placeholders are in template
- [ ] Add curious-specific CSS styles

### Phase 2: Slide Generators
- [ ] Create `CuriousDefaultSlideGenerator` class
- [ ] Implement `generate_slide()` method
- [ ] Match HTML structure from `curious-default.html`
- [ ] Use correct CSS classes (curious-container, curious-text, etc.)
- [ ] Add to `TEMPLATE_GENERATORS` registry with key "curious-default"
- [ ] Update `get_slide_generator()` function (should already work)
- [ ] Organize code with clear sections (News vs Curious)

### Phase 3: CuriousModelClient
- [ ] Add `slide_count` parameter to `generate()` method
- [ ] Implement section limiting logic
- [ ] Handle edge cases (slide_count < 2, too many sections)
- [ ] Maintain backward compatibility

### Phase 4: Orchestrator
- [ ] Add conditional logic for Curious mode
- [ ] Pass `slide_count` to CuriousModelClient
- [ ] Test error handling

### Phase 5: HTML Renderer
- [ ] Add Curious mode default image handling
- [ ] Generate placeholder values for curious mode
- [ ] Test image mapping
- [ ] Verify audio mapping works

### Phase 6: Testing
- [ ] Create test JSON file
- [ ] Test with default images (image_source: null)
- [ ] Test with AI images (image_source: "ai")
- [ ] Test with Pexels images (image_source: "pexels")
- [ ] Test with custom images (image_source: "custom")
- [ ] Test with different slide counts (4, 5, 6, etc.)
- [ ] Verify HTML output is correct
- [ ] Check all slides are generated
- [ ] Verify images and audio are mapped correctly

---

## Code Organization Principles

### 1. Modular Structure
- Separate generators for each template
- Clear separation between News and Curious mode code
- Use sections/comments to organize code

### 2. Clean Code
- Follow existing code style
- Add docstrings to new classes/methods
- Use type hints
- Add comments for complex logic

### 3. Scalability
- Easy to add new templates (just add class + registry entry)
- Template registry pattern for easy extension
- Consistent naming conventions

### 4. Maintainability
- Clear file organization
- Logical grouping of related code
- Consistent patterns across modes

---

## Naming Conventions

### Templates
- News: `test-news-{number}.html` → `TestNews{Number}SlideGenerator`
- Curious: `curious-template-{number}.html` → `CuriousTemplate{Number}SlideGenerator`

### Examples
- `test-news-1.html` → `TestNews1SlideGenerator`
- `test-news-2.html` → `TestNews2SlideGenerator`
- `curious-template-1.html` → `CuriousTemplate1SlideGenerator`
- `curious-template-2.html` → `CuriousTemplate2SlideGenerator`

---

## Testing Strategy

### Unit Tests
- Test slide generator for each template
- Test template registry lookup
- Test slide_count limiting in CuriousModelClient

### Integration Tests
- Test complete story generation flow
- Test HTML rendering with different templates
- Test image and audio mapping

### Manual Tests
- Generate stories with different templates
- Verify HTML output in browser
- Check all slides render correctly
- Verify images and audio work

---

## Success Criteria

✅ **Phase 1 Complete**: Template has INSERT_SLIDES_HERE placeholder
✅ **Phase 2 Complete**: CuriousTemplate1SlideGenerator created and registered
✅ **Phase 3 Complete**: CuriousModelClient supports slide_count
✅ **Phase 4 Complete**: Orchestrator passes slide_count to CuriousModelClient
✅ **Phase 5 Complete**: HTML renderer handles curious mode images
✅ **Phase 6 Complete**: Template structure verified
✅ **Phase 7 Complete**: All tests pass, stories generate correctly

---

## Next Steps After v0

### Future Enhancements
- Add more curious templates (curious-template-2, etc.)
- Implement two-phase generation for curious mode (like news mode)
- Add category/subcategory detection for curious mode
- Add custom image support with portrait resolution
- Add template-specific animations/effects

---

## Notes

- Maintain backward compatibility with existing code
- Follow existing patterns from News mode implementation
- Keep code clean, modular, and well-documented
- Test thoroughly before marking tasks complete

---

**Last Updated**: 2025-01-XX
**Version**: v0.1
**Status**: Ready for Implementation
