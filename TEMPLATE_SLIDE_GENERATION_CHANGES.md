# Template-Specific Slide Generation - Implementation Summary

## Overview
Implemented template-specific slide generators so different templates can have different slide HTML structures.

---

## Changes Made

### 1. Created `app/services/template_slide_generators.py` (NEW FILE)

**Purpose**: Template-specific slide generators for different HTML templates.

**Key Components**:
- `TemplateSlideGenerator` (Protocol) - Interface for slide generators
- `TestNews1SlideGenerator` - Generator for `test-news-1` template
  - Uses `centered-container` and `text1` classes
  - Default background: `polarisslide.png`
- `TestNews2SlideGenerator` - Generator for `test-news-2` template
  - Temporary: Same structure as test-news-1 (will be updated later)
- `TEMPLATE_GENERATORS` registry - Maps template names to generators
- `get_slide_generator()` - Auto-detects template from:
  - File names: `"test-news-1"` → `TestNews1SlideGenerator`
  - URLs: `"https://example.com/test-news-1.html"` → extracts `"test-news-1"`
  - S3: `"s3://bucket/test-news-1.html"` → extracts `"test-news-1"`

---

### 2. Updated `app/services/html_renderer.py`

**Changes**:
1. **Added import**: `from app.services.template_slide_generators import get_slide_generator`

2. **Updated `TemplateLoader._load_from_file()`**:
   - Now extracts template name from URLs
   - Example: `"https://example.com/test-news-1.html"` → loads `app/news_template/test-news-1.html`

3. **Updated `HTMLTemplateRenderer.render()`**:
   - Passes `template_key` to `_generate_all_slides()`

4. **Updated `HTMLTemplateRenderer._generate_all_slides()`**:
   - Now accepts `template_key` parameter
   - Uses `get_slide_generator(template_key)` to get template-specific generator
   - Calls `slide_generator.generate_slide()` instead of old `generate_amp_slide()`

5. **Removed `generate_amp_slide()` function**:
   - Old function removed (replaced by template-specific generators)
   - Updated `__all__` exports

---

## How It Works

### Flow:
1. User provides `template_key` (file name or URL)
2. `TemplateLoader` loads template from `app/news_template/` folder
3. `get_slide_generator()` extracts template name and returns appropriate generator
4. `_generate_all_slides()` uses template-specific generator to create slides
5. Slides are inserted at `<!--INSERT_SLIDES_HERE-->` marker

### Template Detection:
- `"test-news-1"` → `TestNews1SlideGenerator`
- `"test-news-2"` → `TestNews2SlideGenerator`
- `"https://example.com/test-news-1.html"` → Extracts `"test-news-1"` → `TestNews1SlideGenerator`
- Unknown template → Defaults to `TestNews1SlideGenerator`

---

## Example Input JSON

### Example 1: test-news-1 Template (File Name)
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 2: test-news-2 Template (File Name)
```json
{
  "mode": "news",
  "template_key": "test-news-2",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 3: test-news-1 Template (URL - Auto-extracts to file)
```json
{
  "mode": "news",
  "template_key": "https://example.com/templates/test-news-1.html",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

### Example 4: test-news-2 Template (URL - Auto-extracts to file)
```json
{
  "mode": "news",
  "template_key": "https://example.com/templates/test-news-2.html",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/",
  "image_source": "pexels",
  "voice_engine": "azure_basic"
}
```

---

## Features

✅ **Template-Specific Slide Generation**
- Each template has its own slide generator
- Different HTML structures for different templates

✅ **URL Template Key Support**
- Can pass URL in `template_key`
- System extracts template name and loads from `app/news_template/` folder

✅ **Default Background Image**
- Uses `polarisslide.png` as default if no image provided

✅ **Backward Compatible**
- Old file name format still works
- Unknown templates default to `test-news-1` generator

---

## Files Created/Modified

### Created:
1. `app/services/template_slide_generators.py` - Template-specific generators
2. `example_template_test-news-1.json` - Example for test-news-1
3. `example_template_test-news-2.json` - Example for test-news-2
4. `example_template_url_test-news-1.json` - Example with URL template key
5. `example_template_url_test-news-2.json` - Example with URL template key

### Modified:
1. `app/services/html_renderer.py` - Updated to use template-specific generators

---

## Next Steps (Future)

1. **Update TestNews2SlideGenerator**: 
   - Replace temporary implementation with actual test-news-2 structure
   - Use classes: `_f09cc7b`, `_6120891`, `page-fullbleed-area`, etc.

2. **Add More Templates**:
   - Add generators for other templates as needed
   - Register in `TEMPLATE_GENERATORS` dict

3. **Template Metadata**:
   - Consider adding template metadata in HTML comments
   - Auto-detect slide structure from template

---

## Testing

Test with:
```bash
# Test test-news-1
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_test-news-1.json

# Test test-news-2
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_test-news-2.json

# Test URL template key
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_url_test-news-1.json
```

---

## Summary

✅ Template-specific slide generators implemented
✅ URL template key support added
✅ Default background image handling
✅ Backward compatible with existing code
✅ Example JSON files created

All changes are complete and ready for testing!

