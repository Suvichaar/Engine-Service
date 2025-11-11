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
   Current suite: 27 passing tests covering all services.

4. **Start the API (development)**
   ```bash
   uvicorn app.main:app --reload
   ```
   - `POST /stories` — create a story (uses orchestrator pipeline)
   - `GET /stories/{id}` — fetch a stored story
   - `GET /templates` — list available prompt modes

## Next Steps (Roadmap)

- Build orchestration service connecting all existing components.
- Expose FastAPI routes (`POST /stories`, `GET /stories/{id}`, `GET /templates`, etc.).
- Integrate production adapters:
  - Azure Document Intelligence for OCR
  - Azure OpenAI (GPT) for narrative generation
  - ElevenLabs/Azure TTS & S3/CloudFront for media
- Implement slide template renderer, image pipeline, voice pipeline, and persistence (Postgres).
- Add integration tests + smoke CLI/health checks.

## Contributing

1. Fork / clone the repository.
2. Create a branch for your feature or fix.
3. Run `pytest` before opening a PR.
4. Document configuration or API changes in this README.

## License

Add your preferred license text or delete this section if proprietary.

