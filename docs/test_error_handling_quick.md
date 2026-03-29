# Quick Error Handling Test Guide

## 🚀 Quick Tests (No Config Changes Required)

### 1. Invalid JSON
```bash
# PowerShell
$body = "{ invalid json }"
Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```
**Expected**: 422 Unprocessable Entity

### 2. Missing Required Fields
```bash
$body = @{
    mode = "news"
    # Missing other fields
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```
**Expected**: 422 with field validation errors

### 3. Invalid Field Values
```bash
$body = @{
    mode = "invalid_mode"
    template_key = "test-news-1"
    slide_count = -5
    user_input = "test"
    category = "News"
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```
**Expected**: 422 with validation errors

### 4. Wrong Data Types
```bash
$body = @{
    mode = "news"
    template_key = 12345  # Should be string
    slide_count = "four"  # Should be integer
    user_input = "test"
    category = "News"
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```
**Expected**: 422 with type validation errors

---

## ⚠️ Advanced Tests (Require Config Changes)

### 5. DALL-E API Failure
**Step 1**: Temporarily modify `config/settings.toml`:
```toml
[ai_image]
endpoint = "https://invalid-endpoint.com"
api_key = "invalid-key"
```

**Step 2**: Run test:
```bash
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "test"
    category = "News"
    image_source = "ai"
    prompt_keywords = @("test")
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```

**Expected**: 
- System retries 3 times
- Returns 500 after retries exhausted
- Check logs for retry messages

**Step 3**: Restore original config

---

### 6. Database Error
**Step 1**: Temporarily modify `config/settings.toml`:
```toml
[database]
DATABASE_URL = "postgresql://invalid:invalid@invalid:5432/invalid"
```

**Step 2**: Run test:
```bash
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "test"
    category = "News"
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```

**Expected**:
- Story generation succeeds (200 OK)
- Database save fails gracefully
- Check logs: "Failed to save story to database (non-critical)"

**Step 3**: Restore original config

---

### 7. S3 Upload Failure
**Step 1**: Temporarily modify `config/settings.toml`:
```toml
[aws]
AWS_ACCESS_KEY = "invalid"
AWS_SECRET_KEY = "invalid"
```

**Step 2**: Run test with custom images:
```bash
$body = @{
    mode = "news"
    template_key = "test-news-1"
    slide_count = 4
    user_input = "test"
    category = "News"
    image_source = "custom"
    attachments = @("s3://suvichaarapp/media/images/backgrounds/20251129/test.jpg")
    voice_engine = "azure_basic"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/stories" -Method POST -ContentType "application/json" -Body $body
```

**Expected**:
- Story generation continues
- S3 upload fails gracefully
- Check logs: "Failed to upload image to S3"

**Step 3**: Restore original config

---

## 📋 Expected Behavior Summary

| Test | Status Code | Behavior |
|------|------------|----------|
| Invalid JSON | 422 | FastAPI validation error |
| Missing Fields | 422 | Field validation errors |
| Invalid Values | 422 | Value validation errors |
| DALL-E Failure | 500 | Retry 3 times, then error |
| TTS Failure | 500 or 200 | Story generated, audio might be missing |
| S3 Upload Failure | 200 | Story generated, images might use fallback |
| Database Error | 200 | Story generated, database save skipped |

---

## 🔍 Logs to Check

After running tests, check server logs for:
- `ERROR: Error creating story: ...`
- `WARNING: Rate limited (429), waiting ...`
- `WARNING: 400 Bad Request on attempt ...`
- `WARNING: Failed to save story to database (non-critical): ...`
- `ERROR: Failed to upload image to S3: ...`

---

## 🧪 Running the Test Script

```bash
# Make sure API server is running
python test_error_handling.py
```

The script will:
1. Test invalid inputs (no config changes needed)
2. Show instructions for advanced tests (require config changes)
3. Run a control test with valid request

