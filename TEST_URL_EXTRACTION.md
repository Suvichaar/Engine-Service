# URL Extraction Test Guide

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install newspaper3k pillow
   ```

2. **Start the FastAPI server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Test Files

- `test_url_extraction.json` - Test payload with article URL
- `test_url_extraction.py` - Automated test script

## Running the Test

### Option 1: Automated Test Script
```bash
python test_url_extraction.py
```

### Option 2: Manual API Test

#### 1. Create Story
```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d @test_url_extraction.json
```

#### 2. Check Story Details
```bash
# Replace {story_id} with the ID from step 1
curl "http://localhost:8000/stories/{story_id}"
```

#### 3. Get Rendered HTML
```bash
curl "http://localhost:8000/stories/{story_id}/html"
```

## Expected Results

✅ **URL Content Extraction:**
- Article text should be extracted and stored in `semantic_chunks`
- Article title and summary should be available
- Source should be the URL

✅ **Article Images:**
- Article images should be extracted
- Stored in `doc_insights.metadata["article_images"]`
- Images should be downloaded and uploaded to S3
- Images should appear in `image_assets`

✅ **Story Generation:**
- Story should be generated using article content
- Slides should contain article-based narrative
- HTML should render correctly

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'newspaper'`
**Solution:** Install newspaper3k
```bash
pip install newspaper3k pillow
```

### Issue: URL extraction fails
**Possible causes:**
- Network connectivity issues
- URL is not accessible
- Article format not supported by newspaper3k

**Check logs:**
- Look for warnings in server logs about URL extraction
- Check if article images are being extracted

### Issue: No article images found
**Possible causes:**
- Article doesn't have images
- Images are blocked by CORS or authentication
- Image download fails

**Check:**
- `doc_insights.metadata["article_images"]` in story details
- Server logs for image download errors

## Test Payload

The test uses this article URL:
```
https://indianexpress.com/article/cities/pune/killed-injured-pune-accident-navale-bridge-selfie-point-10363830/?ref=hometop_hp
```

This should extract:
- Article title
- Article text/content
- Article summary
- Article images (if available)

