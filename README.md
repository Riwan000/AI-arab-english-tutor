# AI English Tutor for Arabic Speakers

An app that teaches English grammar one lesson at a time through guided AI conversation with bilingual corrections, backed by a FastAPI API and a React/Vite frontend.

## Setup

### Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
```

## Local development (two processes)

Run the FastAPI backend and React frontend in separate terminals.

### Terminal 1 — API

```bash
cp .env.example .env          # add OPENROUTER_API_KEY (backend only)
uvicorn api.main:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies to `http://localhost:8000` by default; override with the `VITE_API_URL` environment variable if the backend runs elsewhere. See `frontend/README.md` for details.

The frontend talks to the API over HTTP. `OPENROUTER_API_KEY` must only be set in the backend `.env`, never exposed to the frontend.

## Deploy API to Render (free tier)

The repo includes a `Dockerfile` and `render.yaml` for [Render](https://render.com).

### Option A — Blueprint (recommended)

1. Push this repo to GitHub.
2. In [Render](https://dashboard.render.com): **New → Blueprint** → connect the repo.
3. When prompted, set secrets:
   - `OPENROUTER_API_KEY` — from [OpenRouter](https://openrouter.ai/keys)
   - `CORS_ORIGINS` — your frontend's deployed URL (e.g. `https://ai-english-tutor-frontend.onrender.com`).
4. Deploy. When live, open `https://<your-service>.onrender.com/api/v1/health` — expect `{"status":"ok"}`.

The Blueprint also deploys the frontend as the `ai-english-tutor-frontend` static site service (see `render.yaml`), which serves the React app and talks to the API via `VITE_API_URL`.

### Option B — Manual web service

1. **New → Web Service** → connect repo.
2. **Runtime:** Docker · **Instance type:** Free.
3. **Health check path:** `/api/v1/health`
4. **Environment variables:**

| Key | Value |
|-----|-------|
| `OPENROUTER_API_KEY` | your OpenRouter key |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `DEFAULT_MODEL` | `openai/gpt-4.1` |
| `DATABASE_PATH` | `/app/database/english_tutor.db` |
| `RETENTION_DAYS` | `5` |
| `CORS_ORIGINS` | Frontend deployed URL (comma-separated if multiple) |

5. Deploy and verify the health endpoint.

### Optional: Persistent SQLite disk (issue #66)

By default, SQLite on Render is **ephemeral** — data resets on redeploy. To keep past sessions across deploys, mount a persistent disk at `/app/database`.

**Requirements:** Starter plan or higher (~$7/mo). Free tier cannot attach disks.

#### Already deployed via Blueprint

1. Render Dashboard → **ai-english-tutor-api** → **Disks** → **Add Disk**
   - **Name:** `sqlite-data`
   - **Mount path:** `/app/database`
   - **Size:** 1 GB
2. Upgrade to **Starter** if prompted (required for disks).
3. Confirm `DATABASE_PATH` = `/app/database/english_tutor.db` (Environment tab).
4. Redeploy. End a session, trigger a redeploy, then check past sessions still appear.

#### New Blueprint deploys

`render.yaml` uses the **free** plan by default. Add a persistent disk manually in the Render Dashboard after upgrading to Starter (see above). Do not add a `disk` block to `render.yaml` on the free plan — it will fail to deploy.

### Free-tier notes

- The service **spins down after ~15 min idle**; the first request after that may take 30–60s (cold start).
- Without a persistent disk, SQLite data may reset on redeploy. Fine for demo.
- With a persistent disk (Starter+), session data survives redeploys.
- After deploying the API, set `VITE_API_URL` in the frontend service's env vars to your Render API URL (e.g. `https://ai-english-tutor-api.onrender.com`).

## Docs

- [prd.md](prd.md) — product requirements
- [tech-stack.md](tech-stack.md) — technical architecture
- [hld.md](hld.md) — high-level design
- [directory.md](directory.md) — project structure
- [db.md](db.md) — database design
- [backend.md](backend.md) — backend architecture & API plan
