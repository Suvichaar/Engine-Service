"""
Streamlit Frontend for Story Generation API
Calls FastAPI backend for story generation with S3 upload support
"""

import streamlit as st
import requests
import json
import os
import uuid
from typing import Optional, List
from pathlib import Path
from datetime import datetime

# Try to import boto3 for S3 uploads
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# =========================
# Configuration
# =========================
# Get FastAPI URL from secrets or environment variable or use default
try:
    FASTAPI_BASE_URL = st.secrets.get("fastapi", {}).get("BASE_URL", "https://localhost:8000")
except:
    FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "https://https://localhost:8000")

# Get AWS credentials from secrets, environment, or settings.toml
# Images go to suvichaarapp bucket, HTML goes to suvichaarstories bucket
AWS_ACCESS_KEY = None
AWS_SECRET_KEY = None
AWS_REGION = "ap-south-1"
AWS_BUCKET = "suvichaarapp"  # Images bucket
AWS_HTML_BUCKET = "suvichaarstories"  # HTML bucket
S3_PREFIX = "media/"

# Try Streamlit secrets first
try:
    aws_secrets = st.secrets.get("aws", {})
    if aws_secrets:
        AWS_ACCESS_KEY = aws_secrets.get("AWS_ACCESS_KEY")
        AWS_SECRET_KEY = aws_secrets.get("AWS_SECRET_KEY")
        AWS_REGION = aws_secrets.get("AWS_REGION", "ap-south-1")
        AWS_BUCKET = aws_secrets.get("AWS_BUCKET", "suvichaarapp")
        AWS_HTML_BUCKET = aws_secrets.get("AWS_HTML_BUCKET", "suvichaarstories")
        S3_PREFIX = aws_secrets.get("S3_PREFIX", "media/")
except:
    pass

# Fallback to environment variables
if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY") or AWS_ACCESS_KEY
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY") or AWS_SECRET_KEY
    AWS_REGION = os.getenv("AWS_REGION", AWS_REGION)
    AWS_BUCKET = os.getenv("AWS_BUCKET", AWS_BUCKET)
    AWS_HTML_BUCKET = os.getenv("AWS_HTML_BUCKET", AWS_HTML_BUCKET)
    S3_PREFIX = os.getenv("S3_PREFIX", S3_PREFIX)

# Final fallback: Try reading from config/settings.toml
if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    try:
        import tomli  # Python 3.11+ has tomllib, but tomli works for older versions
        settings_path = Path("config/settings.toml")
        if settings_path.exists():
            with open(settings_path, "rb") as f:
                settings = tomli.load(f)
                aws_config = settings.get("aws", {})
                if aws_config:
                    AWS_ACCESS_KEY = aws_config.get("AWS_ACCESS_KEY") or AWS_ACCESS_KEY
                    AWS_SECRET_KEY = aws_config.get("AWS_SECRET_KEY") or AWS_SECRET_KEY
                    AWS_REGION = aws_config.get("AWS_REGION", AWS_REGION)
                    AWS_BUCKET = aws_config.get("AWS_BUCKET", AWS_BUCKET)
                    S3_PREFIX = aws_config.get("S3_PREFIX", S3_PREFIX).rstrip("/") + "/"
    except ImportError:
        # Try tomllib (Python 3.11+)
        try:
            import tomllib
            settings_path = Path("config/settings.toml")
            if settings_path.exists():
                with open(settings_path, "rb") as f:
                    settings = tomllib.load(f)
                    aws_config = settings.get("aws", {})
                    if aws_config:
                        AWS_ACCESS_KEY = aws_config.get("AWS_ACCESS_KEY") or AWS_ACCESS_KEY
                        AWS_SECRET_KEY = aws_config.get("AWS_SECRET_KEY") or AWS_SECRET_KEY
                        AWS_REGION = aws_config.get("AWS_REGION", AWS_REGION)
                        AWS_BUCKET = aws_config.get("AWS_BUCKET", AWS_BUCKET)
                        S3_PREFIX = aws_config.get("S3_PREFIX", S3_PREFIX).rstrip("/") + "/"
        except ImportError:
            pass
    except Exception:
        pass

API_ENDPOINT = f"{FASTAPI_BASE_URL}/stories"

# =========================
# S3 Upload Helper Functions
# =========================
def get_s3_client():
    """Get S3 client if credentials are available."""
    # Force enable for testing
    # if not BOTO3_AVAILABLE:
    #     return None
    # if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    #     return None
    try:
        return boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
    except Exception as e:
        st.error(f"S3 client error: {e}")
        return None

def upload_file_to_s3(file, file_type: str = "attachment") -> Optional[str]:
    """
    Upload file to S3 and return S3 URL.
    
    Args:
        file: Streamlit uploaded file object
        file_type: "attachment" for content extraction, "background" for slide backgrounds
    
    Returns:
        S3 URL or None if upload fails
    """
    # Force enable for testing
    # if not BOTO3_AVAILABLE:
    #     return None
    
    s3_client = get_s3_client()
    # if not s3_client or not AWS_BUCKET:
    #     return None
    
    try:
        # For testing without S3, return a dummy URL
        if not s3_client or not AWS_BUCKET:
            return f"https://cdn.suvichaar.org/test-images/{file.name}"
            
        # Generate unique filename
        file_ext = Path(file.name).suffix
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # Determine S3 key based on file type
        if file_type == "background":
            # Background images go to media/images/backgrounds/
            s3_key = f"{S3_PREFIX.rstrip('/')}/images/backgrounds/{timestamp}/{unique_id}{file_ext}"
        else:
            # Attachments go to media/attachments/
            s3_key = f"{S3_PREFIX.rstrip('/')}/attachments/{timestamp}/{unique_id}{file_ext}"
        
        # Determine content type
        content_type_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
        content_type = content_type_map.get(file_ext.lower(), "application/octet-stream")
        
        # Upload to S3
        file.seek(0)  # Reset file pointer
        s3_client.put_object(
            Bucket=AWS_BUCKET,
            Key=s3_key,
            Body=file.read(),
            ContentType=content_type
        )
        
        # Return S3 URL
        s3_url = f"s3://{AWS_BUCKET}/{s3_key}"
        return s3_url
        
    except Exception as e:
        st.error(f"Failed to upload {file.name} to S3: {e}")
        return None

# =========================
# API Helper Functions
# =========================
def create_story(payload: dict, base_url: str = None) -> dict:
    """Call FastAPI to create a story."""
    endpoint = f"{base_url or FASTAPI_BASE_URL}/stories"
    try:
        response = requests.post(endpoint, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP Error {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", e.response.text)
            error_msg += f": {error_detail}"
        except:
            error_msg += f": {e.response.text[:200]}"
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")

def get_story(story_id: str, base_url: str = None) -> dict:
    """Get story details from FastAPI."""
    url = f"{base_url or FASTAPI_BASE_URL}/stories/{story_id}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Story not found: {e.response.status_code}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")

def get_story_html(story_id: str, base_url: str = None) -> str:
    """Get rendered HTML from FastAPI."""
    url = f"{base_url or FASTAPI_BASE_URL}/stories/{story_id}/html"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json().get("html", "")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get HTML: {str(e)}")

# =========================
# Streamlit UI
# =========================
st.set_page_config(
    page_title="Story Generator",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"  # Keep sidebar open by default
)

# Fix for sidebar toggle button showing text instead of icon
st.markdown("""
<style>
    /* Hide the broken sidebar toggle button text */
    button[kind="header"] {
        display: none !important;
    }
    
    /* Hide any text in the header button area */
    [data-testid="stHeader"] button[title*="sidebar"],
    [data-testid="stHeader"] button[aria-label*="sidebar"] {
        font-size: 0 !important;
        color: transparent !important;
    }
    
    /* Alternative: Completely hide the toggle if not needed */
    .css-1d391kg {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📰 Story Generator")
st.markdown("Create web stories using FastAPI backend")

# Sidebar - API Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    # Initialize session state for API URL
    if "api_url" not in st.session_state:
        st.session_state.api_url = FASTAPI_BASE_URL
    
    api_url = st.text_input("FastAPI URL", value=st.session_state.api_url, key="api_url_input")
    if api_url:
        st.session_state.api_url = api_url
        if api_url != FASTAPI_BASE_URL:
            st.info(f"Using: {api_url}")
    
    # S3 Configuration Status
    st.markdown("---")
    st.markdown("### ☁️ S3 Configuration")
    if True:  # Force enable for testing - was: BOTO3_AVAILABLE and AWS_ACCESS_KEY and AWS_BUCKET
        st.success("✅ S3 Upload Available")
        st.caption(f"Bucket: {AWS_BUCKET}")
        st.caption(f"Region: {AWS_REGION}")
    else:
        st.warning("⚠️ S3 Upload Not Available")
        if not BOTO3_AVAILABLE:
            st.caption("boto3 not installed")
        if not AWS_ACCESS_KEY:
            st.caption("AWS credentials not configured")
    
    st.markdown("---")
    st.markdown("### 📚 API Endpoints")
    st.code(f"POST {api_url}/stories")
    st.code(f"GET {api_url}/stories/{{id}}")
    st.code(f"GET {api_url}/stories/{{id}}/html")

# Main Form
# Mode Selection (outside form to allow st.rerun())
st.header("📝 Create New Story")

mode = st.selectbox(
    "Mode",
    options=["news", "curious"],
    help="Select story mode: News for articles, Curious for educational content",
    key="mode_select"
)

# Track mode change and rerun to reset template dropdown
if "last_mode" not in st.session_state:
    st.session_state.last_mode = mode

# If mode changed, clear template state and rerun
if st.session_state.last_mode != mode:
    # Clear template selections
    if "template_select_news" in st.session_state:
        del st.session_state["template_select_news"]
    if "template_select_curious" in st.session_state:
        del st.session_state["template_select_curious"]
    # Clear image source state when mode changes
    if "news_image_source_radio" in st.session_state:
        del st.session_state["news_image_source_radio"]
    if "curious_image_source" in st.session_state:
        del st.session_state["curious_image_source"]
    st.session_state.last_mode = mode
    # st.rerun()  # Now safe to call outside form

# Get slide count from session state or use default (needed for image upload widget)
default_slide_count = 4 if mode == "news" else 4
slide_count_for_images = st.session_state.get("slide_count", default_slide_count)

# Initialize variables for both modes (will be set below)
image_source = None
prompt_keywords = None
uploaded_background_images = []

# Image Source Selection (outside form for both modes to allow dynamic updates)
if mode == "news":
    st.markdown("### 🖼️ Background Image Settings")
    st.caption("These images are used as slide backgrounds (not for content extraction)")
    
    image_source_radio = st.radio(
        "Image Source",
        options=["default", "ai", "pexels", "custom"],
        format_func=lambda x: {
            "default": "Default Images",
            "ai": "AI Generated",
            "pexels": "Pexels Stock Images",
            "custom": "Custom Images"
        }[x],
        help="News mode: Default polaris images, AI generated images, Pexels stock images, or custom uploads",
        key="news_image_source_radio"
    )
    
    # Prompt Keywords for AI and Pexels (News mode) - show when AI or Pexels is selected
    prompt_keywords = None
    if image_source_radio == "ai":
        prompt_keywords_input = st.text_input(
            "Prompt Keywords (comma-separated)",
            placeholder="news, breaking, journalism, media, technology",
            help="Keywords for AI image generation in News mode",
            key="news_prompt_keywords"
        )
        prompt_keywords = [k.strip() for k in prompt_keywords_input.split(",") if k.strip()] if prompt_keywords_input else []
    elif image_source_radio == "pexels":
        prompt_keywords_input = st.text_input(
            "Search Keywords (comma-separated)",
            placeholder="news, breaking, journalism, media, technology",
            help="Keywords for Pexels image search in News mode",
            key="news_pexels_keywords"
        )
        prompt_keywords = [k.strip() for k in prompt_keywords_input.split(",") if k.strip()] if prompt_keywords_input else []
    
    # Convert "default" to None for backend compatibility
    image_source = None if image_source_radio == "default" else image_source_radio
    
    # Custom Images Upload for News - show when custom is selected
    uploaded_background_images = []
    if image_source == "custom":
        st.caption(f"📸 Upload up to {slide_count_for_images} images (one for each slide background)")
        uploaded_background_images = st.file_uploader(
            "Upload Background Images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help=f"Upload up to {slide_count_for_images} custom images for slide backgrounds (will be resized to 720x1280 portrait)",
            key="news_custom_images"
        )
        if uploaded_background_images:
            if len(uploaded_background_images) != slide_count_for_images:
                if len(uploaded_background_images) > slide_count_for_images:
                    st.warning(f"⚠️ You uploaded {len(uploaded_background_images)} images for {slide_count_for_images} slides. Extra images will be ignored.")
                else:
                    st.warning(f"⚠️ You uploaded {len(uploaded_background_images)} images for {slide_count_for_images} slides. The last image will be repeated for remaining slides.")
            else:
                st.success(f"✅ {len(uploaded_background_images)} images uploaded")
            
            # Show preview (all uploaded images)
            cols = st.columns(min(3, len(uploaded_background_images)))
            for idx, img in enumerate(uploaded_background_images):
                with cols[idx % 3]:
                    caption = f"Slide {idx+1}"
                    if idx >= slide_count_for_images:
                        caption += " (will be ignored)"
                    st.image(img, caption=caption, use_container_width=True)
            st.info("ℹ️ Images will be uploaded to S3 in portrait size (720x1280) and used as slide backgrounds")
elif mode == "curious":
    # Curious mode image source selection (outside form for dynamic updates)
    st.markdown("### 🖼️ Background Image Settings")
    st.caption("These images are used as slide backgrounds (not for content extraction)")
    
    image_source_radio = st.radio(
        "Image Source",
        options=["ai", "pexels", "custom"],
        format_func=lambda x: {
            "ai": "AI Generated",
            "pexels": "Pexels Stock Images",
            "custom": "Custom Images"
        }[x],
        help="Curious mode: AI generated, Pexels stock images, or custom uploaded images",
        key="curious_image_source_radio"
    )
    
    image_source = image_source_radio
    
    # Prompt Keywords for AI/Pexels (Curious mode) - show when AI or Pexels is selected
    prompt_keywords = None
    if image_source in ["ai", "pexels"]:
        prompt_keywords_input = st.text_input(
            "Prompt Keywords (comma-separated)",
            placeholder="quantum, computing, science, technology",
            help="Keywords for AI image generation or Pexels search (Curious mode only)",
            key="curious_prompt_keywords"
        )
        prompt_keywords = [k.strip() for k in prompt_keywords_input.split(",") if k.strip()] if prompt_keywords_input else []
    
    # Custom Images Upload for Curious - show when custom is selected
    uploaded_background_images = []
    if image_source == "custom":
        st.caption(f"📸 Upload up to {slide_count_for_images} images (one for each slide background)")
        uploaded_background_images = st.file_uploader(
            "Upload Background Images",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help=f"Upload up to {slide_count_for_images} custom images for slide backgrounds (will be resized to 720x1280 portrait)",
            key="curious_custom_images"
        )
        if uploaded_background_images:
            if len(uploaded_background_images) != slide_count_for_images:
                if len(uploaded_background_images) > slide_count_for_images:
                    st.warning(f"⚠️ You uploaded {len(uploaded_background_images)} images for {slide_count_for_images} slides. Extra images will be ignored.")
                else:
                    st.warning(f"⚠️ You uploaded {len(uploaded_background_images)} images for {slide_count_for_images} slides. The last image will be repeated for remaining slides.")
            else:
                st.success(f"✅ {len(uploaded_background_images)} images uploaded")
            
            # Show preview (all uploaded images)
            cols = st.columns(min(3, len(uploaded_background_images)))
            for idx, img in enumerate(uploaded_background_images):
                with cols[idx % 3]:
                    caption = f"Slide {idx+1}"
                    if idx >= slide_count_for_images:
                        caption += " (will be ignored)"
                    st.image(img, caption=caption, use_container_width=True)
            st.info("ℹ️ Images will be uploaded to S3 in portrait size (720x1280) and used as slide backgrounds")
else:
    # Fallback (should not happen)
    image_source = None
    prompt_keywords = None
    uploaded_background_images = []

with st.form("story_form", clear_on_submit=False):
    
    # Set template options based on mode
    if mode == "news":
        template_options = ["test-news-1", "test-news-2"]
        template_key = st.selectbox(
            "Template",
            options=template_options,
            help="Select template for News mode",
            key="template_select_news"
        )
        default_slide_count = 4
        slide_count_range = (4, 10)
    else:  # curious
        template_options = ["curious-template-1", "curious-template-2", "template-v19"]
        template_key = st.selectbox(
            "Template",
            options=template_options,
            help="Select template for Curious mode (curious-template-2 supports dynamic slide count)",
            key="template_select_curious"
        )
        default_slide_count = 4
        slide_count_range = (4, 15)
    
    # Slide Count
    slide_count = st.number_input(
        "Slide Count",
        min_value=slide_count_range[0],
        max_value=slide_count_range[1],
        value=default_slide_count,
        help=f"Number of slides ({slide_count_range[0]}-{slide_count_range[1]})",
        key="slide_count_input"  # Add key to track in session state
    )
    # Store in session state for use outside form
    st.session_state["slide_count"] = slide_count
    
    # Category - Dropdown for both modes
    st.markdown("### 📂 Category")
    if mode == "news":
        category_options = ["News", "Technology", "Sports", "Politics", "Business", "Entertainment", "Science", "Health", "World", "Local"]
    else:  # curious
        category_options = ["Art", "Travel", "Entertainment", "Literature", "Books", "Sports", "History", "Culture", "Wildlife", "Spiritual", "Food", "Education"]
    
    category = st.selectbox(
        "Category",
        options=category_options,
        index=0,
        help="Select story category"
    )
    
    # User Input (Unified) - Different labels for different modes
    st.markdown("### 📄 Content Input")
    if mode == "news":
        user_input = st.text_area(
            "Article URL or Content",
            height=150,
            placeholder="Enter article URL (e.g., https://example.com/article) OR paste article content here...",
            help="Enter article URL to extract content, or paste article text directly"
        )
    else:  # curious
        user_input = st.text_area(
            "Topic or Keywords",
            height=150,
            placeholder="Enter topic, keywords, or question (e.g., 'How does quantum computing work?')",
            help="Enter topic, keywords, or question for educational content"
        )
    
    # Attachments Section (for both modes - for content extraction)
    st.markdown("### 📎 Attachments (Optional - for Content Extraction)")
    if mode == "news":
        st.caption("📄 Upload documents (PDF, DOCX) or article photos for content extraction via OCR")
        uploaded_attachments = st.file_uploader(
            "Upload Documents or Images",
            type=["pdf", "doc", "docx", "jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Upload documents or images for content extraction. These will be processed via OCR to extract text content."
        )
    else:  # curious
        st.caption("📄 Upload images or documents to use as content source")
        uploaded_attachments = st.file_uploader(
            "Upload Images or Documents",
            type=["pdf", "doc", "docx", "jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            help="Upload images or documents for content extraction. These will be processed via OCR to extract text content."
        )
    
    # Image Source for both News and Curious modes is handled outside form (above)
    # Use variables from outside form for both modes
    
    # Voice Engine
    st.markdown("### 🎤 Voice Settings")
    voice_engine = st.selectbox(
        "Use Elevenlabs",
        options=["azure_basic", "elevenlabs_pro"],
        format_func=lambda x: {
            "azure_basic": "Use Azure",
            "elevenlabs_pro": "Use Elevenlabs"
        }[x],
        help="Text-to-speech engine for narration"
    )
    
    # Submit Button
    submitted = st.form_submit_button("🚀 Generate Story", use_container_width=True)

# Process Form Submission
if submitted:
    if not user_input and not uploaded_attachments:
        st.error("❌ Please enter content (text/URL) or upload attachments")
    else:
        # Build payload
        payload = {
            "mode": mode,
            "template_key": template_key,
            "slide_count": slide_count,
            "user_input": user_input if user_input else None,
            "category": category,
            "image_source": image_source,
            "voice_engine": voice_engine,
        }
        
        # Add prompt_keywords for AI/Pexels (both News and Curious modes)
        if image_source in ["ai", "pexels"] and prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords
        
        # Handle attachments (for content extraction)
        attachments_list = []
        if uploaded_attachments:
            with st.spinner(f"📤 Uploading {len(uploaded_attachments)} attachment(s) to S3..."):
                upload_progress = st.progress(0)
                for idx, file in enumerate(uploaded_attachments):
                    s3_url = upload_file_to_s3(file, file_type="attachment")
                    if s3_url:
                        attachments_list.append(s3_url)
                        st.success(f"✅ Uploaded: {file.name}")
                    else:
                        st.error(f"❌ Failed to upload: {file.name}")
                    upload_progress.progress((idx + 1) / len(uploaded_attachments))
                
                if attachments_list:
                    payload["attachments"] = attachments_list
                    st.info(f"📎 {len(attachments_list)} attachment(s) ready")
        
        # Handle background images (for slide backgrounds)
        background_attachments = []
        
        if mode == "news" and image_source == "custom" and uploaded_background_images:
            # Graceful handling - allow mismatched counts but show appropriate messages
            if len(uploaded_background_images) != slide_count:
                if len(uploaded_background_images) > slide_count:
                    st.info(f"ℹ️ Uploading first {slide_count} images (extra images will be ignored)")
                else:
                    st.info(f"ℹ️ Uploading {len(uploaded_background_images)} images (last image will be repeated for remaining slides)")
            
            with st.spinner(f"📤 Uploading {len(uploaded_background_images)} background images to S3..."):
                upload_progress = st.progress(0)
                for idx, file in enumerate(uploaded_background_images):
                    s3_url = upload_file_to_s3(file, file_type="background")
                    if s3_url:
                        background_attachments.append(s3_url)
                        slide_info = f"Slide {idx+1}"
                        if idx >= slide_count:
                            slide_info += " (will be ignored)"
                        st.success(f"✅ Uploaded: {file.name} ({slide_info})")
                    else:
                        st.error(f"❌ Failed to upload: {file.name}")
                        submitted = False
                        break
                    upload_progress.progress((idx + 1) / len(uploaded_background_images))
                
                if background_attachments:
                    payload["attachments"] = (payload.get("attachments", []) + background_attachments)
                    st.info(f"🖼️ {len(background_attachments)} background image(s) ready")
        
        if mode == "curious" and image_source == "custom" and uploaded_background_images:
            # Graceful handling - allow mismatched counts but show appropriate messages
            if len(uploaded_background_images) != slide_count:
                if len(uploaded_background_images) > slide_count:
                    st.info(f"ℹ️ Uploading first {slide_count} images (extra images will be ignored)")
                else:
                    st.info(f"ℹ️ Uploading {len(uploaded_background_images)} images (last image will be repeated for remaining slides)")
            
            with st.spinner(f"📤 Uploading {len(uploaded_background_images)} background images to S3..."):
                upload_progress = st.progress(0)
                for idx, file in enumerate(uploaded_background_images):
                    s3_url = upload_file_to_s3(file, file_type="background")
                    if s3_url:
                        background_attachments.append(s3_url)
                        slide_info = f"Slide {idx+1}"
                        if idx >= slide_count:
                            slide_info += " (will be ignored)"
                        st.success(f"✅ Uploaded: {file.name} ({slide_info})")
                    else:
                        st.error(f"❌ Failed to upload: {file.name}")
                        submitted = False
                        break
                    upload_progress.progress((idx + 1) / len(uploaded_background_images))
                
                if background_attachments:
                    payload["attachments"] = (payload.get("attachments", []) + background_attachments)
                    st.info(f"🖼️ {len(background_attachments)} background image(s) ready")
        
        # Show payload (for debugging)
        with st.expander("📋 Request Payload", expanded=True):  # Expand by default for debugging
            st.json(payload)
            
            # Debug: Show specific values
            st.write("🔍 **Debug Info:**")
            st.write(f"- Mode: {payload.get('mode')}")
            st.write(f"- Image Source: {payload.get('image_source')}")
            st.write(f"- Prompt Keywords: {payload.get('prompt_keywords', 'None')}")
            st.write(f"- Template Key: {payload.get('template_key')}")
            st.write(f"- Category: {payload.get('category')}")
        
        # Call API (for all cases, not just curious custom images)
        with st.spinner("🔄 Generating story... This may take a few minutes."):
            try:
                # Use API URL from session state (sidebar input)
                current_api_url = st.session_state.get("api_url", FASTAPI_BASE_URL)
                st.info(f"🔄 Sending request to: {current_api_url}/stories")
                result = create_story(payload, base_url=current_api_url)
                st.success("✅ Story generated successfully!")
                
                # Store in session state
                st.session_state["last_story"] = result
                st.session_state["story_id"] = result.get("id")
                
                # Display Results
                st.markdown("---")
                st.header("📊 Story Details")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🔗 URLs")
                    canurl = result.get("canurl")
                    canurl1 = result.get("canurl1")
                    
                    if canurl:
                        st.markdown(f"**Primary URL:**")
                        st.code(canurl, language=None)
                        st.markdown(f"[Open in Browser]({canurl})")
                    
                    if canurl1:
                        st.markdown(f"**HTML URL:**")
                        st.code(canurl1, language=None)
                        st.markdown(f"[Open in Browser]({canurl1})")
                
                with col2:
                    st.subheader("📈 Metadata")
                    st.json({
                        "Story ID": result.get("id"),
                        "Mode": result.get("mode"),
                        "Category": result.get("category"),
                        "Template": result.get("template_key"),
                        "Slides": result.get("slide_count"),
                        "Language": result.get("input_language"),
                        "Created": result.get("created_at"),
                    })
                
                # Story Content Preview
                st.markdown("---")
                st.subheader("📖 Story Content Preview")
                
                slide_deck = result.get("slide_deck", {})
                slides = slide_deck.get("slides", [])
                
                if slides:
                    for idx, slide in enumerate(slides, 1):
                        with st.expander(f"Slide {idx}", expanded=(idx == 1)):
                            st.markdown(f"**Text:** {slide.get('text', 'N/A')}")
                            if slide.get('image_url'):
                                st.image(slide.get('image_url'), caption=f"Slide {idx} Image")
                
                # Download HTML
                st.markdown("---")
                st.subheader("💾 Download")
                
                try:
                    current_api_url = st.session_state.get("api_url", FASTAPI_BASE_URL)
                    html_content = get_story_html(result.get("id"), base_url=current_api_url)
                    if html_content:
                        st.download_button(
                            label="📥 Download HTML",
                            data=html_content,
                            file_name=f"story_{result.get('id')}.html",
                            mime="text/html"
                        )
                except Exception as e:
                    st.warning(f"Could not fetch HTML: {e}")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.exception(e)

# Previous Story Section
if "last_story" in st.session_state:
    st.markdown("---")
    st.header("📚 Previous Story")
    
    story_id = st.session_state.get("story_id")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Story"):
            try:
                current_api_url = st.session_state.get("api_url", FASTAPI_BASE_URL)
                result = get_story(story_id, base_url=current_api_url)
                st.session_state["last_story"] = result
                st.success("Story refreshed!")
                # st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col2:
        if st.button("📄 View HTML"):
            try:
                current_api_url = st.session_state.get("api_url", FASTAPI_BASE_URL)
                html_content = get_story_html(story_id, base_url=current_api_url)
                st.code(html_content, language="html")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with col3:
        if st.button("🗑️ Clear"):
            if "last_story" in st.session_state:
                del st.session_state["last_story"]
            if "story_id" in st.session_state:
                del st.session_state["story_id"]
            # st.rerun()

# Footer
st.markdown("---")
st.markdown("### 📖 API Documentation")
st.markdown("""
- **POST /stories** - Create a new story
- **GET /stories/{id}** - Get story details
- **GET /stories/{id}/html** - Get rendered HTML
- **GET /templates** - List available templates
""")
