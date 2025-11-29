"""Test script to verify custom image URL generation."""
import base64
import json
from urllib.parse import urlparse

# Test S3 URI
s3_uri = "s3://suvichaarapp/media/images/backgrounds/20251129/8a56c5ae-8b4b-44f3-a885-5e69a23c0776.jpg"

# Extract S3 key
parsed = urlparse(s3_uri)
s3_key = parsed.path.lstrip("/")
bucket = parsed.netloc

print("=" * 80)
print("CUSTOM IMAGE URL GENERATION TEST")
print("=" * 80)
print(f"S3 URI: {s3_uri}")
print(f"Bucket: {bucket}")
print(f"Extracted S3 Key: {s3_key}")
print()

# Generate base64 template URL (correct format)
template = {
    "bucket": bucket,
    "key": s3_key,
    "edits": {
        "resize": {
            "width": 720,
            "height": 1280,
            "fit": "cover"
        }
    }
}

encoded = base64.urlsafe_b64encode(json.dumps(template).encode()).decode()
cdn_url = f"https://media.suvichaar.org/{encoded}"

print("Expected CDN URL Format:")
print(f"  {cdn_url[:150]}...")
print()
print("URL should:")
print("  ✓ Start with: https://media.suvichaar.org/")
print("  ✓ Contain base64-encoded template")
print("  ✓ NOT contain: cdn.suvichaar.org")
print("  ✓ NOT be simple path format")
print()

# Test wrong formats (for comparison)
wrong_format_1 = f"https://cdn.suvichaar.org/{s3_key}"
wrong_format_2 = f"https://media.suvichaar.org/sm/{s3_key}"
wrong_format_3 = f"https://media.suvichaar.org/{s3_key}"

print("❌ WRONG FORMATS (should NOT see these):")
print(f"  Wrong 1 (cdn domain): {wrong_format_1}")
print(f"  Wrong 2 (variant path): {wrong_format_2}")
print(f"  Wrong 3 (direct path): {wrong_format_3}")
print()

print("=" * 80)

