"""
Streamlit Frontend for Story Generation API
Calls FastAPI backend for story generation
"""

import streamlit as st
import requests
import json
import os
from typing import Optional, List
from pathlib import Path

# =========================
# Configuration
# =========================
# Get FastAPI URL from secrets or environment variable or use default
try:
    FASTAPI_BASE_URL = st.secrets.get("fastapi", {}).get("BASE_URL", "http://localhost:8000")
except:
    FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")

API_ENDPOINT = f"{FASTAPI_BASE_URL}/stories"

# =========================
# Helper Functions
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
    layout="wide"
)

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
    
    st.markdown("---")
    st.markdown("### 📚 API Endpoints")
    st.code(f"POST {api_url}/stories")
    st.code(f"GET {api_url}/stories/{{id}}")
    st.code(f"GET {api_url}/stories/{{id}}/html")

# Main Form
with st.form("story_form", clear_on_submit=False):
    st.header("📝 Create New Story")
    
    # Mode Selection
    mode = st.selectbox(
        "Mode",
        options=["news", "curious"],
        help="Select story mode: News for articles, Curious for educational content"
    )
    
    # Template Selection
    if mode == "news":
        template_key = st.selectbox(
            "Template",
            options=["test-news-1", "test-news-2"],
            help="Select template for News mode"
        )
        default_slide_count = 4
        slide_count_range = (4, 10)
    else:  # curious
        template_key = st.selectbox(
            "Template",
            options=["curious-template-1"],
            help="Select template for Curious mode"
        )
        default_slide_count = 7
        slide_count_range = (7, 15)
    
    # Slide Count
    slide_count = st.number_input(
        "Slide Count",
        min_value=slide_count_range[0],
        max_value=slide_count_range[1],
        value=default_slide_count,
        help=f"Number of slides ({slide_count_range[0]}-{slide_count_range[1]})"
    )
    
    # Category
    category = st.text_input(
        "Category",
        value="News" if mode == "news" else "Education",
        help="Story category"
    )
    
    # User Input (Unified)
    st.markdown("### 📄 Content Input")
    user_input = st.text_area(
        "Content",
        height=150,
        help="Enter text, URL(s), or content. URLs will be automatically extracted."
    )
    
    # Image Source (conditional)
    st.markdown("### 🖼️ Image Settings")
    if mode == "news":
        image_source = st.radio(
            "Image Source",
            options=["default", "custom"],
            format_func=lambda x: "Default Images" if x == "default" else "Custom Image",
            help="News mode: Use default images or upload custom"
        )
        image_source = None if image_source == "default" else "custom"
        prompt_keywords = None
    else:  # curious
        image_source = st.radio(
            "Image Source",
            options=["ai", "pexels", "custom"],
            help="Curious mode: AI generated, Pexels, or custom image"
        )
        # Prompt Keywords for Curious mode
        prompt_keywords_input = st.text_input(
            "Prompt Keywords (comma-separated)",
            help="Keywords for AI image generation (Curious mode only)"
        )
        prompt_keywords = [k.strip() for k in prompt_keywords_input.split(",") if k.strip()] if prompt_keywords_input else []
    
    # Custom Image Upload (if custom selected)
    uploaded_file = None
    if image_source == "custom":
        uploaded_file = st.file_uploader(
            "Upload Image",
            type=["jpg", "jpeg", "png", "webp"],
            help="Upload custom image for slide backgrounds"
        )
        if uploaded_file:
            st.info("⚠️ Note: Image needs to be uploaded to S3 first. Use attachment URL in production.")
    
    # Voice Engine
    voice_engine = st.selectbox(
        "Voice Engine",
        options=["azure_basic", "elevenlabs_pro"],
        help="Text-to-speech engine"
    )
    
    # Submit Button
    submitted = st.form_submit_button("🚀 Generate Story", use_container_width=True)

# Process Form Submission
if submitted:
    if not user_input:
        st.error("❌ Please enter content (text or URL)")
    else:
        # Build payload
        payload = {
            "mode": mode,
            "template_key": template_key,
            "slide_count": slide_count,
            "user_input": user_input,
            "category": category,
            "image_source": image_source,
            "voice_engine": voice_engine,
        }
        
        # Add prompt_keywords for Curious mode
        if mode == "curious" and prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords
        
        # Add attachment if custom image uploaded
        if image_source == "custom" and uploaded_file:
            # Note: In production, upload to S3 first and use URL
            st.warning("⚠️ File upload: In production, upload image to S3 first and provide URL in 'attachments' field")
        
        # Show payload (for debugging)
        with st.expander("📋 Request Payload", expanded=False):
            st.json(payload)
        
        # Call API
        with st.spinner("🔄 Generating story... This may take a few minutes."):
            try:
                # Use API URL from session state (sidebar input)
                current_api_url = st.session_state.get("api_url", FASTAPI_BASE_URL)
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
                st.rerun()
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
            st.rerun()

# Footer
st.markdown("---")
st.markdown("### 📖 API Documentation")
st.markdown("""
- **POST /stories** - Create a new story
- **GET /stories/{id}** - Get story details
- **GET /stories/{id}/html** - Get rendered HTML
- **GET /templates** - List available templates
""")

