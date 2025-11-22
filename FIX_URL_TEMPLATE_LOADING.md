# Fix: URL Template Key Loading

## Problem
When `template_key` was a URL (e.g., `"https://example.com/templates/test-news-1.html"`), the system was trying to load from the actual URL instead of extracting the template name and loading from local file system.

## Root Cause
In `TemplateLoader.load()`, even when `source="file"` was explicitly passed, the code was auto-detecting and changing `source` to `"url"` if `template_key` looked like a URL.

## Solution
Modified `TemplateLoader.load()` to respect the explicit `source="file"` parameter:
- If `source == "file"` → Always load from local file system
- Extract template name from URL if needed (handled by `_load_from_file()`)
- Don't auto-detect when source is explicitly "file"

## Code Changes

### Before:
```python
def load(self, template_key: str, mode: Mode, source: str = "file") -> str:
    if source == "file":
        # Auto-detect URL or S3
        if template_key.startswith(("http://", "https://")):
            source = "url"  # ❌ Changed even though "file" was explicit
        elif template_key.startswith("s3://"):
            source = "s3"
    
    if source == "url":
        return self._load_from_url(template_key)  # ❌ Tried to load from actual URL
```

### After:
```python
def load(self, template_key: str, mode: Mode, source: str = "file") -> str:
    # If source is explicitly "file", always load from local file system
    if source == "file":
        return self._load_from_file(template_key, mode)  # ✅ Always loads locally
    
    # Auto-detect only if source is not explicitly "file"
    if template_key.startswith(("http://", "https://")):
        return self._load_from_url(template_key)
    # ...
```

## How It Works Now

### Example 1: URL Template Key
**Input:**
```json
{
  "template_key": "https://example.com/templates/test-news-1.html"
}
```

**Flow:**
1. Orchestrator calls: `html_renderer.render(..., template_source="file")`
2. `TemplateLoader.load()` receives: `source="file"` (explicit)
3. Checks: `source == "file"` → ✅ Yes
4. Calls: `_load_from_file(template_key, mode)`
5. `_load_from_file()` extracts: `"test-news-1"` from URL
6. Loads: `app/news_template/test-news-1.html` (local file)
7. ✅ **Success**: Template loaded from local file system

### Example 2: File Name Template Key
**Input:**
```json
{
  "template_key": "test-news-1"
}
```

**Flow:**
1. Same as above, but no URL extraction needed
2. Loads: `app/news_template/test-news-1.html` directly
3. ✅ **Success**: Template loaded from local file system

## Benefits

✅ **Respects Explicit Parameter**: When `source="file"` is passed, it's always respected
✅ **URL Template Keys Work**: Extracts template name and loads locally
✅ **No Network Calls**: Doesn't try to fetch from actual URLs
✅ **Consistent Behavior**: All templates load from local file system

## Testing

Test with:
```bash
# Test URL template key
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @example_template_url_test-news-1.json
```

**Expected Result:**
- ✅ Template loads from: `app/news_template/test-news-1.html`
- ✅ HTML file saved: `output/{story_id}.html`
- ✅ Template-specific slides generated correctly

## Files Modified

- `app/services/html_renderer.py` - Updated `TemplateLoader.load()` method

---

**Status**: ✅ Fixed and ready to test!

