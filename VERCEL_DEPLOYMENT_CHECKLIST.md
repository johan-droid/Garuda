# Garuda — Vercel Deployment Readiness Checklist

**Repository:** `/home/ashutoshsahoo/Downloads/Garuda`  
**Target:** Vercel (frontend) + external backend service (Railway/Render/fly.io)  
**Blocker (R1):** Vercel serverless + SQLite is incompatible — ephemeral filesystem, no persistent write.  
**Decision required:** Database must move to PostgreSQL (Neon, Supabase, Railway DB, etc.) before any production deploy.

---

## Phase 0 — Pre-flight (do this first)

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 0.1 | All local tests pass: backend 191, frontend 67, imagery 20+4 skipped | | Run `make test` before any deploy |
| 0.2 | `mypy backend/app` clean | | `Success: no issues found in 47 source files` |
| 0.3 | `tsc --noEmit` clean | | Frontend typecheck exit 0 |
| 0.4 | `npm run build` (frontend) succeeds | | `✓ built in ~19s` |
| 0.5 | Working tree clean, all changes committed | | `git status` → nothing to commit |
| 0.6 | `.env` is NOT committed (gitignored) | | `.env` is in `.gitignore`; `.env.example` is committed |

## Phase 1 — Database (critical blocker R1)

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1.1 | Provision PostgreSQL (Neon, Supabase, Railway DB, or managed PG) | | SQLite cannot run on Vercel serverless (ephemeral FS) |
| 1.2 | Get `DATABASE_URL` (postgres:// or postgresql:// connection string) | | Required for `Settings.DATABASE_URL` |
| 1.3 | Update `backend/app/core/config.py` validator if needed | | Currently defaults to SQLite; production must override via env |
| 1.4 | Run Alembic migrations against production DB | | `alembic upgrade head` — migrations live in `backend/alembic/` |
| 1.5 | Seed pilot data on production DB | | `python backend/seed_pilot.py` — idempotent (uses `session.merge`) |
| 1.6 | Verify `/health` reports `database.ok: true` | | Health endpoint checks DB connectivity |
| 1.7 | Set `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS` for serverless | | Smaller pool for serverless (e.g., pool_size=2, max_overflow=5) |

## Phase 2 — Backend (not on Vercel serverless)

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 2.1 | Choose backend platform: Railway, Render, fly.io, or self-hosted | | FastAPI cannot run as Vercel serverless with SQLite; use a dedicated service |
| 2.2 | Dockerfile builds cleanly: `docker build -t garuda-api:latest .` | | Multi-stage, non-editable install, unprivileged user |
| 2.3 | `docker-compose up` works locally | | Backend + nginx frontend proxy |
| 2.4 | Set `ENVIRONMENT=production` | | Triggers production secret validation |
| 2.5 | Set `DEBUG=false` | | Production validator rejects `DEBUG=true` |
| 2.6 | Generate `SECRET_KEY` (32+ chars) | | `openssl rand -hex 32` |
| 2.7 | Generate `ADMIN_API_KEY` (16+ chars) | | `openssl rand -hex 16` |
| 2.8 | Set `PILOT_REGION=IN-OD` | | Default pilot region |
| 2.9 | Set `ALLOWED_ORIGINS` to include production frontend domain | | Wildcard `*` rejected in production; must list exact origins |
| 2.10 | Set `LOG_JSON=true`, `LOG_LEVEL=INFO` | | Structured logs for production observability |
| 2.11 | Configure `RATE_LIMIT_ENABLED=true` | | Rate limiting middleware active |
| 2.12 | Health check endpoint responds: `GET /health` → 200 | | Used by platform health checks and frontend `checkHealth()` |
| 2.13 | CORS allows the Vercel frontend domain | | `ALLOWED_ORIGINS` must include `https://<your-app>.vercel.app` |
| 2.14 | Set `GARUDA_BACKEND_URL` in Vercel env | | Used by `vercel.json` routes to proxy `/api` and `/health` |

## Phase 3 — Frontend on Vercel

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 3.1 | `vercel.json` committed at repo root | | Created; configures `@vercel/static-build` with `distDir: frontend/dist` |
| 3.2 | `frontend/package.json` `build` script works | | `tsc --noEmit && vite build` |
| 3.3 | `frontend/vite.config.ts` proxy only for dev | | Production uses `vercel.json` routes; dev proxy is localhost-only |
| 3.4 | `frontend/nginx.conf` NOT needed on Vercel | | nginx config is for Docker compose only; Vercel serves static directly |
| 3.5 | CESIUM assets copied to `frontend/public/cesium/` at build | | `cesiumAssets()` Vite plugin handles this on `npm run build` |
| 3.6 | No `VITE_*` secrets in frontend bundle | | `test_no_credentials.py` scans for credential shapes; all provider hosts are anonymous |
| 3.7 | Frontend points to production backend | | `GARUDA_BACKEND_URL` env var in Vercel; routes proxy `/api` and `/health` |
| 3.8 | SPA fallback route works | | `vercel.json` route `{ "src": "/(.*)", "dest": "/frontend/dist/index.html" }` |

## Phase 4 — Vercel-specific configuration

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 4.1 | Import repo into Vercel dashboard | | Connect GitHub repo `johan-droid/Garuda` |
| 4.2 | Set framework preset to "None" / static | | `vercel.json` sets `"framework": null` |
| 4.3 | Install command: `cd frontend && npm install --no-audit --no-fund` | | Matches `vercel.json` |
| 4.4 | Build command: `cd frontend && npx tsc --noEmit && vite build` | | Matches `vercel.json` |
| 4.5 | Output directory: `frontend/dist` | | Matches `vercel.json` `distDir` |
| 4.6 | Add environment variables in Vercel dashboard | | `GARUDA_BACKEND_URL`, plus any frontend-only vars |
| 4.7 | Add custom domain (optional) | | Update `ALLOWED_ORIGINS` on backend to match |
| 4.8 | Enable automatic deployments from `main` branch | | Vercel default |

## Phase 5 — Post-deployment verification

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 5.1 | Frontend loads at `https://<app>.vercel.app` | | SPA shell renders |
| 5.2 | `/health` proxies to backend | | Returns JSON with `status: healthy` |
| 5.3 | `/api/v1/places/reverse` works | | Proxy to backend; returns coverage verdict |
| 5.4 | `/api/v1/places/IN-OD-29/profile` works | | Returns panel data with honest `unverified` statuses |
| 5.5 | No CORS errors in browser console | | `ALLOWED_ORIGINS` includes Vercel domain |
| 5.6 | No credential warnings | | `test_no_credentials.py` passes on built bundle |
| 5.7 | Globe page (`/?globe=1`) renders | | Cesium loads, GIBS base layer shows |
| 5.8 | Database is writable | | `POST /api/v1/places/saved-places` works (if authenticated) |
| 5.9 | Logs are visible | | `LOG_JSON=true` structured logs in platform dashboard |
| 5.10 | Rollback plan documented | | Previous Vercel deployment can be redeployed instantly |

## Phase 6 — Known risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **R1** SQLite + Vercel serverless | High — DB writes fail, data lost on function recycle | **Must** use PostgreSQL; SQLite is local-dev only |
| **R2** Backend not on Vercel | Medium — Frontend and backend are separate services | Deploy backend on Railway/Render/fly.io; proxy via `vercel.json` |
| **R3** No Vercel config existed | Low | `vercel.json` created; review before first deploy |
| **R4** `docs/plans/` and `GARUDA_*.md` gitignored | Low — Hermes planning docs intentionally excluded | Not production code; do not un-ignore |
| **R5** Trailing space in repo path (`/Downloads/Garuda `) | Low — breaks Alembic `script_location` resolution | Do not deploy from a path with trailing space |

---

## Quick commands

```bash
# Local full-stack (recommended for dev)
bash start.sh

# Backend only
cd backend && python -m app.db.init_db && python backend/seed_pilot.py && PYTHONPATH=backend uvicorn app.main:app --reload

# Frontend only
cd frontend && npm install && npm run dev

# Tests
make test               # backend: 191 passed
make test-frontend      # frontend: 67 passed
make test-imagery       # pipeline: 20 passed, 4 skipped
make lint               # mypy: clean

# Production DB provisioning (example: Neon)
# 1. Create project at neon.tech
# 2. Copy connection string to DATABASE_URL
# 3. PYTHONPATH=backend alembic upgrade head
# 4. python backend/seed_pilot.py

# Vercel deploy
# vercel login && vercel --prod
```

---

## Sign-off

- [ ] All Phase 0–5 checks complete
- [ ] Backend deployed on separate service with PostgreSQL
- [ ] Frontend deployed on Vercel
- [ ] `/health`, `/api`, and globe routes verified in production
- [ ] CORS and secrets configured
- [ ] Rollback tested

**Deployment owner:** _______________   **Date:** _______________
| 0.7 | `garuda_local.db` is NOT committed | | `*.db` is gitignored; database is seeded at runtime |