# AI English Tutor for Arabic Speakers

Phase 1 MVP — a Streamlit app that teaches English grammar one lesson at a time through guided AI conversation with bilingual corrections.

## Setup

### Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate  # macOS/Linux

# Full stack (API + Streamlit)
pip install -r requirements.txt

# API only (separate API host or Docker)
pip install -r requirements-api.txt
```

## Local development (two processes)

Run the FastAPI backend and Streamlit frontend in separate terminals.

### Terminal 1 — API

```bash
cp .env.example .env          # add OPENROUTER_API_KEY (backend only)
uvicorn api.main:app --reload --port 8000
```

### Terminal 2 — Streamlit

Point the frontend at the local API with `BACKEND_URL`:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml — BACKEND_URL = "http://localhost:8000"
streamlit run app.py
```

Or set the environment variable instead of secrets:

```bash
# Linux / macOS
BACKEND_URL=http://localhost:8000 streamlit run app.py

# Windows PowerShell
$env:BACKEND_URL="http://localhost:8000"; streamlit run app.py
```

The frontend talks to the API over HTTP. `OPENROUTER_API_KEY` must only be set in the backend `.env`, never in Streamlit secrets.

## Docs

- [prd.md](prd.md) — product requirements
- [tech-stack.md](tech-stack.md) — technical architecture
- [hld.md](hld.md) — high-level design
- [directory.md](directory.md) — project structure
- [db.md](db.md) — database design
- [backend.md](backend.md) — backend architecture & API plan
