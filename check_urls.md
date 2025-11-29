# Custom Image URL Debugging Guide

## Expected URL Format
```
https://media.suvichaar.org/{base64_encoded_template}
```

Example:
```
https://media.suvichaar.org/eyJidWNrZXQiOiAic3V2aWNoYWFyYXBwIiwgImtleSI6ICJtZWRpYS9pbWFnZXMvYmFja2dyb3VuZHMvMjAyNTExMjkvOGE1NmM1YWUtOGI0Yi00NGYzLWE4OD...
```

## Wrong Formats (Should NOT see these)

1. **Wrong CDN Domain:**
   ```
   https://cdn.suvichaar.org/...
   ```

2. **Variant Path Format:**
   ```
   https://media.suvichaar.org/sm/media/images/backgrounds/...
   ```

3. **Direct Path Format:**
   ```
   https://media.suvichaar.org/media/images/backgrounds/...
   ```

## How to Debug

### Step 1: Check Server Logs
Look for these log messages:
- `"Detected S3 URI: ... extracted key: ..."`
- `"Using existing S3 key (skipping upload): ..."`
- `"Generated resized URL from S3 key: ..."`
- `"Generated CDN URL for variant ..."`

### Step 2: Check Generated HTML
Open the generated story HTML and search for image URLs. They should:
- Start with `https://media.suvichaar.org/`
- Contain base64-encoded content (long string)
- NOT contain `cdn.suvichaar.org`

### Step 3: Verify Configuration
Check `config/settings.toml`:
```toml
CDN_PREFIX_MEDIA = "https://media.suvichaar.org/"
```

### Step 4: Restart Server
After code changes, restart the FastAPI server:
```bash
# Stop current server (Ctrl+C)
# Then restart
uvicorn app.main:app --reload
```

## Common Issues

1. **Server not restarted** - Old code still running
2. **Caching** - Browser or CDN cache showing old URLs
3. **Wrong CDN base** - Configuration issue
4. **Exception in URL generation** - Check logs for errors

