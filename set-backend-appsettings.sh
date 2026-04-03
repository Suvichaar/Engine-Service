#!/bin/bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./set-backend-appsettings.sh <resource-group> <app-name>

Reads required values from environment variables and pushes them to Azure App Service.

Required environment variables:
  DATABASE_URL
  AI_IMAGE_ENDPOINT
  AI_IMAGE_API_KEY
  AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_API_KEY
  AZURE_OPENAI_DEPLOYMENT

Optional environment variables:
  AZURE_OPENAI_API_VERSION   Default: 2025-01-01-preview
  AZURE_SPEECH_KEY
  AZURE_SPEECH_REGION
  AZURE_SPEECH_VOICE
  AZURE_DI_ENDPOINT
  AZURE_DI_KEY
  AWS_ACCESS_KEY
  AWS_SECRET_KEY
  AWS_REGION
  AWS_BUCKET
  S3_PREFIX
  HTML_S3_PREFIX
  CDN_PREFIX_MEDIA
  CDN_HTML_BASE
  CDN_BASE
  DEFAULT_ERROR_IMAGE
  STORY_BASE_URL
  HTML_BUCKET
  ELEVENLABS_API_KEY
  ELEVENLABS_VOICE_ID
  PEXELS_API_KEY
  VOICE_BUCKET
  VOICE_PREFIX
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage
  exit 1
fi

RESOURCE_GROUP="$1"
APP_NAME="$2"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

require_cmd az

for name in \
  DATABASE_URL \
  AI_IMAGE_ENDPOINT \
  AI_IMAGE_API_KEY \
  AZURE_OPENAI_ENDPOINT \
  AZURE_OPENAI_API_KEY \
  AZURE_OPENAI_DEPLOYMENT
do
  require_var "$name"
done

AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-01-01-preview}"

SETTINGS=(
  "WEBSITES_PORT=8000"
  "DATABASE_URL=${DATABASE_URL}"
  "AI_IMAGE_ENDPOINT=${AI_IMAGE_ENDPOINT}"
  "AI_IMAGE_API_KEY=${AI_IMAGE_API_KEY}"
  "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}"
  "AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}"
  "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}"
  "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}"
)

append_if_set() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    SETTINGS+=("${name}=${!name}")
  fi
}

for name in \
  AZURE_SPEECH_KEY \
  AZURE_SPEECH_REGION \
  AZURE_SPEECH_VOICE \
  AZURE_DI_ENDPOINT \
  AZURE_DI_KEY \
  AWS_ACCESS_KEY \
  AWS_SECRET_KEY \
  AWS_REGION \
  AWS_BUCKET \
  S3_PREFIX \
  HTML_S3_PREFIX \
  CDN_PREFIX_MEDIA \
  CDN_HTML_BASE \
  CDN_BASE \
  DEFAULT_ERROR_IMAGE \
  STORY_BASE_URL \
  HTML_BUCKET \
  ELEVENLABS_API_KEY \
  ELEVENLABS_VOICE_ID \
  PEXELS_API_KEY \
  VOICE_BUCKET \
  VOICE_PREFIX
do
  append_if_set "$name"
done

az webapp config appsettings set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings "${SETTINGS[@]}" \
  --output none

echo "Backend app settings updated for $APP_NAME"
echo "Restarting web app..."
az webapp restart \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --output none

echo "Done."
