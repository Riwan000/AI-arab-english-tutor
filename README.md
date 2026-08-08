# AI English Tutor for Arabic Speakers

Phase 1 MVP — a Streamlit app that teaches English grammar one lesson at a time through guided AI conversation with bilingual corrections.

## Setup

### 1. Backend API

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # add OPENROUTER_API_KEY (backend only)
uvicorn api.main:app --reload --port 8000
```

### 2. Streamlit frontend

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml — set BACKEND_URL only (no OpenRouter key in Streamlit)
streamlit run app.py
```

The frontend talks to the API over HTTP. `OPENROUTER_API_KEY` must only be set in the backend `.env`, never in Streamlit secrets.

## Docs

- [prd.md](prd.md) — product requirements
- [tech-stack.md](tech-stack.md) — technical architecture
- [hld.md](hld.md) — high-level design
- [directory.md](directory.md) — project structure
- [db.md](db.md) — database design
- [backend.md](backend.md) — backend architecture & API plan
