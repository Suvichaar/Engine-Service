# Storytelling Newslab Service v2

A production-ready FastAPI backend for generating interactive AMP Story slide decks from mixed multimedia inputs. Supports **News** (factual briefing) and **Curious** (explainable storytelling) modes with dynamic template rendering, AI image generation, voice synthesis, and S3 integration.

## ✨ Features

### Story Generation Modes
- **News Mode**: Generate factual news stories from URLs, text, or documents
  - Multiple templates (`test-news-1`, `test-news-2`, etc.)
  - Dynamic slide generation based on `slide_count`
  - Article content extraction from URLs
  - Category/subcategory/emotion detection

- **Curious Mode**: Create educational explainable stories
  - Fixed and dynamic templates (`curious-template-1`, etc.)
  - Structured content generation with alt texts for images
  - Topic-based storytelling

### Image Sources
- **AI Generated** (DALL-E 3): Generate images from content-based prompts
- **Pexels**: Royalty-free stock images
- **Custom Upload**: User-provided images (URL, S3 URI, or local file)
- **Default Images**: Fallback images for News mode
- **Article Images**: Auto-extracted from article URLs

### Voice Synthesis
- **Azure TTS**: Multiple voice options
- **ElevenLabs**: High-quality voice synthesis
- Individual audio per slide

### Content Processing
- **URL Extraction**: Automatically extract text and images from article URLs
- **Unified Input**: ChatGPT-style single input field (auto-detects URLs, text, or files)
- **Document Intelligence**: OCR and document parsing (Azure Document Intelligence)
- **Language Detection**: Automatic language detection and translation

### Storage & Delivery
- **S3 Integration**: Upload images, audio, and HTML to AWS S3
- **CloudFront CDN**: Resized image variants via CloudFront
- **Local HTML Output**: Generated stories saved locally for testing
- **Database Support**: Optional PostgreSQL storage (can be disabled)

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL (optional, for database storage)
- AWS Account (for S3/CloudFront)
- Azure Account (for OpenAI, TTS, Document Intelligence)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Iamkrmayank/Newsengine-Service.git
   cd Newsengine-Service
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows (PowerShell)
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure settings**
   ```bash
   cp config/settings.example.toml config/settings.toml
   ```
   Edit `config/settings.toml` with your credentials:
   - Azure OpenAI (text generation)
   - Azure DALL-E (image generation)
   - Azure Speech Services (TTS)
   - AWS S3 (storage)
   - PostgreSQL (optional)

   ⚠️ **Important**: Never commit `config/settings.toml` - it contains secrets!

5. **Run the API**
   ```bash
   uvicorn app.main:app --reload
   ```
   API will be available at `http://localhost:8000`

## 📚 API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### `POST /stories`
Create a new story from various input sources.

**Request Body:**
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "category": "News",
  "user_input": "https://example.com/article",
  "image_source": "ai",
  "voice_engine": "azure_basic",
  "prompt_keywords": ["technology", "AI"]
}
```

**Response:**
```json
{
  "id": "story-uuid",
  "mode": "news",
  "slide_deck": { ... },
  "image_assets": [ ... ],
  "voice_assets": [ ... ],
  "canurl": "https://stories.suvichaar.org/{id}",
  "created_at": "2025-01-21T..."
}
```

#### `GET /stories/{story_id}`
Retrieve a stored story by ID.

#### `GET /templates`
List available prompt templates/modes.

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | string | Yes | `"news"` or `"curious"` |
| `template_key` | string | Yes | Template name (e.g., `"test-news-1"`, `"curious-template-1"`) |
| `slide_count` | integer | Yes | Number of slides (4-10 for News, 7+ for Curious) |
| `user_input` | string | No | Unified input (URL, text, or file reference) |
| `image_source` | string | No | `"ai"`, `"pexels"`, `"custom"`, or `null` (default for News) |
| `voice_engine` | string | No | `"azure_basic"` or `"elevenlabs"` |
| `prompt_keywords` | array | No | Keywords for image generation |

### Image Source Rules

#### News Mode
- `image_source: null` → Uses default images (`polariscover.png`, `polarisslide.png`)
- `image_source: "custom"` → Uses uploaded image (resized to 720x1280 portrait)
- `image_source: "pexels"` → Fetches from Pexels API
- `image_source: "ai"` → Generates with DALL-E 3

#### Curious Mode
- `image_source: "ai"` → Generates images using alt texts from content
- `image_source: "pexels"` → Fetches from Pexels
- `image_source: "custom"` → Uses uploaded images

## 📁 Project Structure

```
app/
├── api/                    # FastAPI endpoints and schemas
├── config/                 # Settings loader and configuration
├── curious_template/       # Curious mode HTML templates
├── domain/                 # DTOs, interfaces, and domain models
├── news_template/          # News mode HTML templates
├── persistence/            # Database repositories (PostgreSQL)
├── prompts/                # Prompt templates for News/Curious modes
├── services/                # Core service implementations
│   ├── analysis.py         # Content analysis and insights
│   ├── document_intelligence.py  # OCR and document parsing
│   ├── html_renderer.py    # HTML template rendering
│   ├── image_pipeline.py   # Image generation and processing
│   ├── ingestion.py        # Content ingestion and aggregation
│   ├── model_clients.py    # LLM clients (News/Curious)
│   ├── orchestrator.py     # Main story orchestration
│   ├── template_slide_generators.py  # Dynamic slide generation
│   ├── user_input.py       # Unified input detection
│   └── voice_synthesis.py  # Text-to-speech generation
├── utils/                  # Utility functions
└── main.py                 # FastAPI application entry point

config/
├── settings.example.toml  # Configuration template (safe to commit)
└── settings.toml          # Your actual config (DO NOT COMMIT)

tests/                      # Pytest test suites
output/                     # Generated HTML files (local testing)
```

## 🔧 Configuration

### Settings File Structure

```toml
[azure_api]
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.cognitiveservices.azure.com"
AZURE_OPENAI_API_KEY = "YOUR_API_KEY"
AZURE_OPENAI_DEPLOYMENT = "gpt-5-chat"
AZURE_OPENAI_API_VERSION = "2025-01-01-preview"

[ai_image]
AI_IMAGE_ENDPOINT = "https://your-endpoint/.../dall-e-3/images/generations"
AI_IMAGE_API_KEY = "YOUR_DALLE_KEY"

[azure_speech]
AZURE_SPEECH_KEY = "YOUR_SPEECH_KEY"
AZURE_SPEECH_REGION = "eastus"
VOICE_NAME = "hi-IN-AaravNeural"

[aws]
AWS_ACCESS_KEY = "YOUR_ACCESS_KEY"
AWS_SECRET_KEY = "YOUR_SECRET_KEY"
AWS_REGION = "ap-south-1"
AWS_BUCKET = "your-bucket-name"
CDN_BASE = "https://cdn.yourdomain.org/"
```

See `config/settings.example.toml` for complete configuration options.

## 📖 Usage Examples

### News Mode - Default Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "https://indianexpress.com/article/...",
  "image_source": null,
  "voice_engine": "azure_basic"
}
```

### News Mode - AI Generated Images
```json
{
  "mode": "news",
  "template_key": "test-news-1",
  "slide_count": 4,
  "user_input": "Breaking news: AI breakthrough",
  "image_source": "ai",
  "prompt_keywords": ["technology", "AI"],
  "voice_engine": "azure_basic"
}
```

### Curious Mode - Educational Story
```json
{
  "mode": "curious",
  "template_key": "curious-template-1",
  "slide_count": 7,
  "user_input": "How does quantum computing work?",
  "image_source": "ai",
  "prompt_keywords": ["quantum", "computing"],
  "voice_engine": "azure_basic"
}
```

### Using cURL
```bash
curl -X POST "http://localhost:8000/stories" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "news",
    "template_key": "test-news-1",
    "slide_count": 4,
    "user_input": "https://example.com/article",
    "image_source": "ai",
    "voice_engine": "azure_basic"
  }'
```

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

## 📝 Documentation

- [API Usage Guide](API_USAGE_GUIDE.md) - Complete API reference with examples
- [Frontend Integration Guide](FRONTEND_INTEGRATION_GUIDE.md) - Frontend developer guide
- [Implementation Plan](Implementation_v0.md) - Curious mode implementation details

## 🔒 Security

- **Never commit** `config/settings.toml` (contains API keys and secrets)
- Use `config/settings.example.toml` as a template
- All sensitive files are in `.gitignore`
- Database saving can be disabled for testing

## 🛠️ Development

### Adding New Templates

1. Create HTML template in `app/news_template/` or `app/curious_template/`
2. Add slide generator in `app/services/template_slide_generators.py`
3. Register in `TEMPLATE_GENERATORS` dictionary

### Adding New Image Providers

1. Implement `ImageProvider` protocol in `app/services/image_pipeline.py`
2. Add to provider list in `app/main.py`

### Adding New Voice Providers

1. Implement voice synthesis interface in `app/services/voice_synthesis.py`
2. Register in `app/main.py`


## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞Support

For issues, questions, or contributions, please open an issue on GitHub.

