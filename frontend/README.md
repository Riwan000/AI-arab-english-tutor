# English Tutor — React Frontend

A minimal Vite + React frontend for the AI English Tutor, talking to the
existing FastAPI backend in `api/`. This is a plain, dependency-light
replacement for the Streamlit UI (`app.py`, `components/`), which stays in
the repo untouched.

## Run it

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at `http://localhost:5173`. It expects the FastAPI
backend running at `http://localhost:8000` (override with `VITE_API_URL` —
copy `.env.example` to `.env` and edit it).

## Backend setup required

The FastAPI backend's CORS allowlist must include the Vite dev server's
origin. Add it to the project root's `.env`:

```
CORS_ORIGINS=http://localhost:8501,http://localhost:5173
```

(`CORS_ORIGINS` is a comma-separated list — see `api/config.py`.) Then start
the backend as usual:

```bash
uvicorn api.main:app --reload --port 8000
```

## Build

```bash
npm run build
```

Outputs a static bundle to `frontend/dist/`.

## Structure

- `src/App.jsx` — owns top-level view state (`auth` → `picker` → `lesson` →
  `chat` → `summary`), the current user/token, and UI language.
- `src/api/client.js` — one `apiFetch` helper plus small per-resource
  wrappers (auth, lessons, chat, voice, sessions, usage).
- `src/i18n.js` — UI chrome strings (Arabic default, English toggle). Lesson
  content and chat replies come from the backend already localized.
- `src/components/` — one component per view/concern, plain `useState`/
  `useEffect`, no router or state-management library.
