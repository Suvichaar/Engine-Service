"""One-time helper to pre-bake the default OG image.

Downloads `default_cover_image` (or a URL passed via --source), resizes to
1200x630 JPG with cover-fit, and uploads to S3 at `og-images/_default.jpg`.

Run from backend/ directory:

    python scripts/bake_default_og_image.py

Requires AWS credentials in environment / settings.toml so boto3 can authenticate.
"""

from __future__ import annotations

import argparse
import logging
import sys
from io import BytesIO
from pathlib import Path

import boto3
import httpx
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import get_settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bake_og")


def bake(source_url: str, bucket: str, key: str, region: str, access_key: str | None, secret_key: str | None) -> None:
    logger.info("Downloading source: %s", source_url)
    resp = httpx.get(source_url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()

    with Image.open(BytesIO(resp.content)) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        og = ImageOps.fit(img, (1200, 630), method=Image.LANCZOS, centering=(0.5, 0.5))
        buf = BytesIO()
        og.save(buf, format="JPEG", quality=85, optimize=True)
        body = buf.getvalue()

    s3_kwargs = {"region_name": region or "us-east-1"}
    if access_key and secret_key:
        s3_kwargs["aws_access_key_id"] = access_key
        s3_kwargs["aws_secret_access_key"] = secret_key
    s3 = boto3.client("s3", **s3_kwargs)

    logger.info("Uploading to s3://%s/%s (%d bytes)", bucket, key, len(body))
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="image/jpeg",
        CacheControl="public, max-age=31536000",
    )
    logger.info("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-bake default OG image into S3")
    parser.add_argument("--source", help="Source image URL. Defaults to settings.branding.default_cover_image.")
    parser.add_argument("--key", default="og-images/_default.jpg", help="Destination S3 key.")
    args = parser.parse_args()

    settings = get_settings()
    source = args.source or settings.branding.default_cover_image
    bucket = settings.aws.bucket
    region = settings.aws.region
    access_key = settings.aws.access_key
    secret_key = settings.aws.secret_key

    if not source:
        parser.error("No source URL: pass --source or configure branding.default_cover_image")
    if not bucket or bucket == "placeholder":
        parser.error("aws.bucket is not configured")

    bake(source, bucket, args.key, region, access_key, secret_key)


if __name__ == "__main__":
    main()
