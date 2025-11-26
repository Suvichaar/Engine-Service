# Test Scripts for Story Generation System

This folder contains comprehensive test cases for validating the story generation system across different modes, image sources, and edge cases.

## 📁 Test Categories

### News Mode Tests
- `test_news_mode_single_image.json` - Traditional single image for all slides
- `test_news_mode_multiple_images_perfect.json` - Perfect image count (4 images for 4 slides)
- `test_news_mode_extra_images.json` - More images than slides (graceful handling)
- `test_news_mode_fewer_images.json` - Fewer images than slides (repeat last image)
- `test_news_mode_default_images.json` - Default polaris images
- `test_news_mode_ai_images.json` - AI-generated images with DALL-E

### Curious Mode Tests
- `test_curious_mode_perfect_images.json` - Perfect image count (7 images for 7 slides)
- `test_curious_mode_ai_images.json` - AI-generated images with DALL-E
- `test_curious_mode_pexels_images.json` - Pexels stock images
- `test_curious_mode_extra_images.json` - More images than slides
- `test_curious_mode_fewer_images.json` - Fewer images than slides

### Special Feature Tests
- `test_url_generation_news.json` - Title-based URL generation for News mode
- `test_attachments_content_extraction.json` - OCR and content extraction
- `test_dual_purpose_attachments.json` - Attachments for both content and backgrounds
- `test_seo_metadata.json` - SEO metadata generation
- `test_voice_synthesis.json` - Audio generation and synthesis

## 🧪 How to Use Tests

### Manual Testing
1. Copy JSON payload from any test file
2. Send POST request to `/api/stories/` endpoint
3. Verify expected behavior matches actual results

### Automated Testing (Future)
```bash
# Run all tests
python run_tests.py

# Run specific category
python run_tests.py --category news_mode
python run_tests.py --category curious_mode
python run_tests.py --category special_features
```

## 📊 Expected Behaviors

### Graceful Image Handling
- **Perfect match**: No warnings, 1:1 mapping
- **Extra images**: First N images used, rest ignored with warning
- **Fewer images**: All images used, last image repeated for remaining slides

### URL Generation
- **News mode**: Title-based slugs with Nano ID
- **Curious mode**: UUID-based URLs
- **Format**: `https://suvichaar.org/stories/{slug_nano}` (News), UUID (Curious)

### Image Sources
- **News mode**: `null` (default) or `"custom"` only
- **Curious mode**: `"ai"`, `"pexels"`, or `"custom"`
- **Attachments**: Dual purpose (content extraction + backgrounds if `image_source: "custom"`)

### SEO Metadata
- Page title: `{story_title} | Suvichaar`
- Meta description: LLM-generated (max 160 chars)
- Meta keywords: LLM-generated (8-12 keywords)
- Language: `en-US` or `hi-IN`
- Content type: `News` or `Article`

## 🔍 Validation Checklist

For each test, verify:
- [ ] Story generates successfully
- [ ] Correct number of slides created
- [ ] Images mapped correctly to slides
- [ ] Audio files generated (if voice_engine specified)
- [ ] SEO metadata populated
- [ ] URLs generated in correct format
- [ ] HTML saved to S3 (News mode)
- [ ] Graceful handling messages displayed (if applicable)

## 🚨 Common Issues to Test

1. **Image count mismatch** - Should handle gracefully
2. **Missing attachments** - Should use defaults or skip
3. **Invalid URLs** - Should extract content or show error
4. **Large slide counts** - Should generate correctly
5. **Special characters in titles** - Should slugify properly
6. **Mixed content types** - Should process all attachments

## 📝 Adding New Tests

When adding new test cases:
1. Follow the JSON structure of existing tests
2. Include `description` and `expected_behavior`
3. Test edge cases and error conditions
4. Document any special setup requirements
5. Update this README with new test categories

## 🔧 Test Environment Setup

Ensure the following before running tests:
- FastAPI backend running on configured port
- AWS S3 credentials configured
- Azure OpenAI API keys set up
- Pexels API key available (for Pexels tests)
- Database connection (optional, can be disabled)

---

**Last Updated**: 2025-01-21  
**Total Test Cases**: 16  
**Coverage**: News mode, Curious mode, Image handling, URL generation, SEO, Voice synthesis
