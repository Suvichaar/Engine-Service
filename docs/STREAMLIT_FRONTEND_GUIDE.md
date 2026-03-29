# Streamlit Frontend Guide

## Overview

`streamlit_frontend.py` is a clean Streamlit UI that calls the FastAPI backend for story generation. It provides a user-friendly form interface without embedding business logic.

## Architecture

```
┌─────────────────┐         HTTP/REST         ┌─────────────────┐
│  Streamlit UI   │ ────────────────────────> │  FastAPI Backend │
│  (Frontend)     │ <──────────────────────── │  (Business Logic)│
└─────────────────┘         JSON Response     └─────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
pip install streamlit requests
```

### 2. Configure FastAPI URL

Create `.streamlit/secrets.toml`:

```toml
[fastapi]
BASE_URL = "http://localhost:8000"  # Change to your FastAPI URL
```

Or set environment variable:
```bash
export FASTAPI_BASE_URL="http://localhost:8000"
```

### 3. Start FastAPI Backend

```bash
# Terminal 1: Start FastAPI
uvicorn app.main:app --reload --port 8000
```

### 4. Start Streamlit Frontend

```bash
# Terminal 2: Start Streamlit
streamlit run streamlit_frontend.py
```

## Features

### ✅ Clean Form UI
- Mode selection (News/Curious)
- Template selection
- Slide count input
- Content input (text/URL)
- Image source selection
- Voice engine selection

### ✅ API Integration
- Calls `POST /stories` to create stories
- Calls `GET /stories/{id}` to retrieve stories
- Calls `GET /stories/{id}/html` to get HTML

### ✅ Results Display
- Story URLs (canurl, canurl1)
- Story metadata
- Slide content preview
- HTML download

### ✅ Error Handling
- Clear error messages
- Request timeout handling
- HTTP error display

## Usage Flow

1. **Select Mode**: Choose "news" or "curious"
2. **Select Template**: Choose appropriate template
3. **Set Slide Count**: Enter number of slides
4. **Enter Content**: 
   - Text content
   - URL (will be extracted automatically)
   - File reference
5. **Configure Images**:
   - News: Default or Custom
   - Curious: AI, Pexels, or Custom
6. **Select Voice Engine**: Choose TTS engine
7. **Generate**: Click "Generate Story" button
8. **View Results**: See URLs, metadata, and content

## Example Workflows

### News Mode
```
Mode: news
Template: test-news-1
Slide Count: 4
Content: https://indianexpress.com/article/...
Image Source: default
Voice: azure_basic
```

### Curious Mode
```
Mode: curious
Template: curious-template-1
Slide Count: 7
Content: How does quantum computing work?
Image Source: ai
Prompt Keywords: quantum, computing, science
Voice: azure_basic
```

## API Endpoints Used

### Create Story
```python
POST http://localhost:8000/stories
Content-Type: application/json

{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Content here...",
  "image_source": null,
  "voice_engine": "azure_basic",
  "category": "News"
}
```

### Get Story
```python
GET http://localhost:8000/stories/{story_id}
```

### Get HTML
```python
GET http://localhost:8000/stories/{story_id}/html
```

## Advantages

### ✅ Separation of Concerns
- Frontend: UI/UX only
- Backend: Business logic, processing

### ✅ Scalability
- Multiple frontends can use same backend
- Backend can be deployed separately
- Easy to add new frontends (React, Vue, etc.)

### ✅ Maintainability
- Changes to UI don't affect backend
- Changes to backend don't affect UI
- Easy to test both independently

### ✅ Reusability
- Backend API can be used by:
  - Streamlit UI
  - Web frontend
  - Mobile app
  - CLI tools
  - Other services

## Troubleshooting

### FastAPI Not Running
```
Error: Request failed: Connection refused
```
**Solution**: Start FastAPI backend first (`uvicorn app.main:app --reload`)

### Wrong API URL
```
Error: HTTP Error 404
```
**Solution**: Check `FASTAPI_BASE_URL` in secrets or environment

### Timeout Errors
```
Error: Request timeout
```
**Solution**: Story generation takes time. Increase timeout in code if needed.

## Next Steps

1. **Add Authentication**: Add API key/auth to requests
2. **Add Progress Tracking**: Use WebSockets for real-time updates
3. **Add File Upload**: Direct S3 upload for images
4. **Add History**: Store previous stories in session
5. **Add Export**: Export stories in different formats

## Comparison with Old Streamlit Apps

| Feature | Old Apps | New Frontend |
|---------|----------|--------------|
| Business Logic | Embedded | In Backend |
| API Calls | Direct Azure/AWS | Via FastAPI |
| Scalability | Limited | High |
| Maintainability | Hard | Easy |
| Reusability | Low | High |

