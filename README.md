# Storytelling Newslab Service

Modular FastAPI backend (in progress) for generating narrative slide decks from mixed multimedia inputs. The current codebase delivers fully-tested domain types and service layers that will power Curious (explainable storytelling) and News (factual briefing) experiences.

## Project Status

- ✅ Core domain models and interfaces
- ✅ Service implementations (input normalization, language detection, ingestion, document intelligence, analysis, prompt selection, model routing, narrative generation)
- ✅ Prompt configuration system
- ✅ Configuration loader (`config/settings.example.toml`)
- ✅ Extensive unit test suite (`pytest`)
- 🚧 Orchestrator & FastAPI endpoints (next milestone)
- 🚧 External adapters (Azure DI/LLM, ElevenLabs/Azure TTS, S3 media pipeline)
- 🚧 Persistence & asset pipelines

## Repository Layout

```
app/
├── config/                # Settings loader (`get_settings`)
├── domain/                # DTOs and service protocols
├── prompts/               # Curious/News prompt templates + registry
├── services/              # Concrete service implementations (analysis, ingestion, etc.)
config/
└── settings.example.toml  # Template for secrets/configuration
tests/                     # Pytest suites covering each service
```

## Getting Started

1. **Install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows (PowerShell)
   pip install -r requirements.txt
   ```
   *(requirements file TBD; install `pydantic`, `fasttext` (optional), `pytest`, etc. manually if missing).*

2. **Create local settings**
   ```bash
   cp config/settings.example.toml config/settings.toml
   ```
   Populate real credentials for Azure, AWS, etc. Do **not** commit `config/settings.toml`.

3. **Run tests**
   ```bash
   pytest
   ```
   Current suite: 37 passing tests covering all services and HTTP endpoints.

4. **Start the API (development)**
   ```bash
   uvicorn app.main:app --reload
   ```
   - `POST /stories` — create a story (uses orchestrator pipeline)
   - `GET /stories/{id}` — fetch a stored story
   - `GET /templates` — list available prompt modes

## Next Steps (Roadmap)

- Replace stubbed HTTP integrations with live credentials in `config/settings.toml`:
  - Azure Translator (language detection via `AZURE_TRANSLATOR_KEY/ENDPOINT`)
  - Azure Document Intelligence (OCR)
  - Azure OpenAI (Chat + DALL·E image generation)
  - Pexels API (fallback imagery)
  - ElevenLabs / Azure Speech TTS
- Wire production-grade storage (S3 uploads, CloudFront distributions).
- Harden template renderer, add placeholder validation, support duration extraction for audio.
- Implement slide template renderer, image pipeline, voice pipeline, and persistence (Postgres).
- Add integration tests + smoke CLI/health checks.
- Instrument logging, metrics, and tracing; secure endpoints with auth.

## Contributing

1. Fork / clone the repository.
2. Create a branch for your feature or fix.
3. Run `pytest` before opening a PR.
4. Document configuration or API changes in this README.

## License

Add your preferred license text or delete this section if proprietary.

