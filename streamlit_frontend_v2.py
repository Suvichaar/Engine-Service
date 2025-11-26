#!/usr/bin/env python3
"""
Streamlit Frontend v2 - Simplified version for testing upload functionality
"""

import streamlit as st
import requests
import os
from typing import Optional

# Configuration
st.set_page_config(
    page_title="Story Generator v2",
    page_icon="📖",
    layout="wide"
)

def main():
    st.title("📖 Story Generator v2 - Test Version")
    st.markdown("Simplified frontend to test upload functionality")
    
    # Mode Selection (outside form)
    mode = st.selectbox(
        "Mode",
        options=["news", "curious"],
        help="Select story mode"
    )
    
    st.markdown("---")
    
    # Form
    with st.form("test_form"):
        st.subheader("Story Configuration")
        
        # Template
        if mode == "news":
            template_options = ["test-news-1", "test-news-2"]
            default_slide_count = 4
        else:
            template_options = ["curious-template-1", "template-v19"]
            default_slide_count = 7
            
        template_key = st.selectbox("Template", template_options)
        slide_count = st.number_input("Slide Count", min_value=4, max_value=15, value=default_slide_count)
        
        # Content Input
        user_input = st.text_area(
            "Content",
            placeholder="Enter article URL or content...",
            height=100
        )
        
        # Category
        category = st.text_input("Category", value="News" if mode == "news" else "Education")
        
        # Image Source
        st.subheader("🖼️ Background Images")
        
        if mode == "news":
            image_source_options = ["default", "custom"]
            image_source_labels = ["Default Images", "Custom Images"]
        else:
            image_source_options = ["ai", "pexels", "custom"]
            image_source_labels = ["AI Generated", "Pexels Stock", "Custom Images"]
        
        image_source_display = st.radio(
            "Image Source",
            options=image_source_options,
            format_func=lambda x: dict(zip(image_source_options, image_source_labels))[x],
            help="Choose image source for slide backgrounds"
        )
        
        # Convert display value to API value
        if mode == "news":
            image_source = None if image_source_display == "default" else "custom"
        else:
            image_source = image_source_display
        
        # Custom Image Upload
        uploaded_files = []
        if image_source == "custom":
            st.markdown("### 📤 Upload Custom Images")
            st.info(f"Upload up to {slide_count} images for slide backgrounds")
            
            uploaded_files = st.file_uploader(
                "Choose image files",
                type=["jpg", "jpeg", "png", "webp"],
                accept_multiple_files=True,
                help=f"Upload {slide_count} images (720x1280 recommended)"
            )
            
            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)} files uploaded")
                
                # Show preview
                cols = st.columns(min(4, len(uploaded_files)))
                for idx, file in enumerate(uploaded_files):
                    with cols[idx % 4]:
                        st.image(file, caption=f"Image {idx+1}", use_container_width=True)
                
                # Show handling info
                if len(uploaded_files) != slide_count:
                    if len(uploaded_files) > slide_count:
                        st.warning(f"⚠️ {len(uploaded_files)} images uploaded for {slide_count} slides. Extra images will be ignored.")
                    else:
                        st.warning(f"⚠️ {len(uploaded_files)} images uploaded for {slide_count} slides. Last image will be repeated.")
        
        # Prompt Keywords (for Curious mode AI/Pexels)
        prompt_keywords = []
        if mode == "curious" and image_source in ["ai", "pexels"]:
            keywords_input = st.text_input(
                "Prompt Keywords (comma-separated)",
                placeholder="quantum, computing, science",
                help="Keywords for AI image generation or Pexels search"
            )
            if keywords_input:
                prompt_keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
        
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
        st.markdown("---")
        st.subheader("📋 Form Data")
        
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
        
        # Add prompt keywords if applicable
        if prompt_keywords:
            payload["prompt_keywords"] = prompt_keywords
        
        # Handle file uploads (mock S3 URLs for testing)
        if uploaded_files:
            mock_s3_urls = []
            for idx, file in enumerate(uploaded_files):
                mock_url = f"s3://test-bucket/images/bg_{idx+1}_{file.name}"
                mock_s3_urls.append(mock_url)
            payload["attachments"] = mock_s3_urls
            
            st.info(f"📤 Mock S3 URLs generated for {len(uploaded_files)} files")
        
        # Display payload
        st.json(payload)
        
        # Test API call (optional)
        api_url = st.text_input("API URL (optional)", value="http://localhost:8000")
        
        if st.button("🔄 Test API Call"):
            try:
                response = requests.post(f"{api_url}/api/stories/", json=payload, timeout=30)
                if response.status_code == 200:
                    st.success("✅ API call successful!")
                    st.json(response.json())
                else:
                    st.error(f"❌ API call failed: {response.status_code}")
                    st.text(response.text)
            except Exception as e:
                st.error(f"❌ Connection error: {str(e)}")

if __name__ == "__main__":
    main()
