# Codex TikTok SaaS (Mock-ready)

This repo implements a lightweight, production-shaped SaaS for TikTok automation with multi-tenancy, quota enforcement, mocks for all external providers, and Docker-based local runtime.

## What it does
- FastAPI backend with JWT auth, org/projects, planning (30x3 calendar), quota metering, asset generation, mock TikTok publishing, analytics.
- Celery worker/beat for scheduled work.
- React + Vite + Tailwind frontend with calendar, video library, analytics, and demo login auto-flow.
- Mocks for OpenRouter LLM, video rendering (ffmpeg dummy MP4 + thumbnail), TikTok publisher, ASR, storage.
- Seeds a full demo tenant with plans and metrics.

## Assumptions
- Official TikTok API is integrated via an adapter scaffold; runtime defaults to mocks (`USE_MOCK_PROVIDERS=true`).
- pgvector is off by default; RAG fallback is stubbed/in-memory (documented in `docs/ARCHITECTURE.md`).
- Credentials encryption is placeholder; BYOK hook is in `models.Credential.encrypted_secret`.
- Frontend uses the backend via `/api` proxy in Vite dev; in compose it resolves to `backend:8000`.

## Quickstart
```bash
python -m venv .venv && .\.venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload
# frontend
cd frontend && npm install && npm run dev
```

## Docker (recommended)
```bash
docker compose -f infra/docker-compose.yml up --build
```

## Seed demo data
```bash
make migrate   # optional; metadata create_all also runs
make seed
```

## Demo credentials (local only)
- Email: `demo@codex.local`
- Password: `demopass123`
Change via `settings.demo_password` or `.env`.

## Environment
Copy `.env.example` to `.env` and adjust:
- `DATABASE_URL`, `REDIS_URL`, `BROKER_URL`
- `USE_MOCK_PROVIDERS=true` (default)
- `OPENROUTER_API_KEY`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` for real adapters (scaffolded)
- `STORAGE_PATH` for media

## Make targets
- `make up` / `make down` / `make logs`
- `make test` – runs unit tests (quota, tenant isolation, orchestrator schema)
- `make seed` – seeds demo org/user/project/plan

## Structure
- `backend/` FastAPI app, Celery worker
- `frontend/` React Vite UI
- `infra/` docker-compose.yml
- `migrations/` alembic env
- `docs/` checklist, architecture, API
- `scripts/seed.py` demo data

## Production notes
- Swap `LocalStorage` with S3/MinIO via envs; use tenant prefixes.
- Replace `MockTikTokPublisher` and `MockLLM` with real adapters (OpenRouter, TikTok OAuth2) once keys are available.
- Enable pgvector in Postgres for production retrieval.
- Harden auth (refresh rotation, password reset emails, rate limits) before exposure.
