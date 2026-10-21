# Phase 1 — Project Skeleton

> **Duration:** 3–5 days  
> **Objective:** Set up a buildable mono-repo with TypeScript PWA frontend, Python/FastAPI backend, shared contracts, CI pipeline, and local dev workflow — requiring zero API keys.

---

## 🎯 Objective

Create the foundational project structure so that a fresh `git clone` produces a running application on both Windows and Linux. The skeleton includes all tooling (linting, type checking, formatting, testing), a baseline "hello world" API + map page, and a CI pipeline. **No external data sources are connected yet.**

---

## 📋 Prerequisites

- **Phase 0 COMPLETE** — pilot district selected, sources verified, blockers documented
- Node.js 20+ and npm/pnpm installed
- Python 3.12+ with pip/uv installed
- Git installed

---

## 📝 Detailed Tasks

### Task 1.1 — Initialize Mono-repo

**Action:** Create the root project structure.

```bash
# Root directory: garuda/
mkdir -p apps/web services/api services/ingestion packages/contracts \
         data/fixtures docs tests
```

**Root files to create:**

| File | Purpose |
|------|---------|
| `README.md` | Project overview, setup instructions, attribution |
| `.gitignore` | Python, Node, IDE, OS files, `.env`, secrets |
| `Makefile` or `justfile` | Unified commands: `make dev`, `make test`, `make lint` |
| `docker-compose.yml` | Optional — for PostgreSQL + PostGIS local dev |
| `.env.example` | Template showing all env vars (no actual secrets) |
| `LICENCE` | Project licence (e.g., MIT or Apache-2.0) |
| `ATTRIBUTION.md` | Data source and library attributions |

> [!IMPORTANT]
> Docker must NOT be mandatory. Document both Docker and native Windows/Linux setup paths.

---

### Task 1.2 — Frontend Scaffold (apps/web)

**Action:** Initialize the TypeScript + React + Vite PWA.

```bash
cd apps/web
npx -y create-vite@latest ./ --template react-ts
```

**Configure:**

| Tool | Config File | Purpose |
|------|-------------|---------|
| TypeScript | `tsconfig.json` | Strict mode, path aliases |
| Vite | `vite.config.ts` | Dev server, proxy to FastAPI, PWA plugin |
| ESLint | `eslint.config.js` | Linting rules |
| Vitest | `vitest.config.ts` | Unit/component tests |
| PWA | `vite-plugin-pwa` | Service worker, manifest, offline shell |

**Key files to create:**

```
apps/web/
├── src/
│   ├── main.tsx              # App entry point
│   ├── App.tsx               # Root component with routing
│   ├── components/
│   │   └── MapView.tsx       # Placeholder MapLibre container
│   ├── pages/
│   │   └── HomePage.tsx      # Landing page with map
│   ├── api/
│   │   └── client.ts         # API client (TanStack Query setup)
│   ├── types/
│   │   └── contracts.ts      # Shared TypeScript types
│   └── styles/
│       └── index.css         # Global styles
├── public/
│   ├── manifest.json         # PWA manifest
│   └── favicon.svg           # App icon
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

**Install key dependencies:**

```bash
npm install react react-dom maplibre-gl @tanstack/react-query zod
npm install -D typescript @types/react @types/react-dom vite \
  @vitejs/plugin-react vitest vite-plugin-pwa eslint
```

**Acceptance test:** `npm run build` succeeds with zero type errors.

---

### Task 1.3 — Backend Scaffold (services/api)

**Action:** Initialize the Python/FastAPI backend.

```
services/api/
├── src/
│   └── garuda_api/
│       ├── __init__.py
│       ├── main.py            # FastAPI app instance
│       ├── config.py          # Settings (Pydantic BaseSettings)
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── health.py      # GET /api/v1/health
│       │   └── places.py      # Placeholder: GET /api/v1/places/search
│       ├── models/
│       │   ├── __init__.py
│       │   ├── place.py       # Place, BoundaryVersion models
│       │   ├── source.py      # Source model
│       │   ├── observation.py # Observation model
│       │   └── common.py      # DataStatus, ApiError, etc.
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── base.py        # Abstract base adapter class
│       └── services/
│           ├── __init__.py
│           └── place_service.py # Place resolution logic
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Test fixtures, HTTPX test client
│   └── test_health.py         # Health endpoint test
├── pyproject.toml             # Dependencies, tool config
└── README.md
```

**Key dependencies (pyproject.toml):**

```toml
[project]
name = "garuda-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.9",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",        # For test client
    "ruff>=0.6",          # Linting + formatting
    "mypy>=1.11",         # Type checking
]
```

**Acceptance test:** `pytest` passes; `uvicorn garuda_api.main:app` starts and `GET /api/v1/health` returns `200`.

---

### Task 1.4 — Shared Contracts (packages/contracts)

**Action:** Define the core data contracts shared between frontend and backend.

**Python side (`packages/contracts/python/`):**

```python
# Core enums and types used everywhere

class DataStatus(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"
    APPROXIMATE = "approximate"
    UNVERIFIED = "unverified"

class PlaceType(str, Enum):
    STATE = "state"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"  # block / tehsil
    VILLAGE = "village"
    POINT = "point"

class Place(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str] = []
    place_type: PlaceType
    parent_id: str | None = None
    coordinates: tuple[float, float] | None = None  # (lat, lng)
    resolution_method: str | None = None
    geometry_available: bool = False

class Source(BaseModel):
    id: str
    publisher: str
    name: str
    url: str | None = None
    licence: str | None = None
    access_mode: str  # "api" | "download" | "manual"
    verification_status: str  # VERIFIED | VERIFIED_WITH_LIMITS | etc.
    last_success: datetime | None = None

class Observation(BaseModel):
    field_name: str
    value: float | str | None
    unit: str | None = None
    place_id: str
    source_id: str
    reference_period_start: date | None = None
    reference_period_end: date | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    quality_status: DataStatus
    notes: str | None = None
```

**TypeScript side (`packages/contracts/typescript/`):**
- Mirror the above types using Zod schemas for runtime validation
- Export both Zod schemas and inferred TypeScript types

---

### Task 1.5 — Health Endpoint

**Action:** Implement `GET /api/v1/health` as the first working endpoint.

```python
@router.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "note": "This is application health, not public-health data."
    }
```

> [!CAUTION]
> The endpoint name `/health` must explicitly distinguish itself from public-health alerts. Include a note field.

---

### Task 1.6 — CI Pipeline

**Action:** Set up GitHub Actions (free tier) for automated checks.

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e "services/api[dev]"
      - run: ruff check services/api/
      - run: mypy services/api/src/
      - run: pytest services/api/tests/

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd apps/web && npm ci
      - run: cd apps/web && npm run lint
      - run: cd apps/web && npm run typecheck
      - run: cd apps/web && npm run test -- --run
      - run: cd apps/web && npm run build
```

---

### Task 1.7 — Local Development Setup Documentation

**Action:** Write comprehensive local setup docs for both paths.

**`docs/SETUP.md`** must cover:

1. **Native path (no Docker)**
   - Install Python 3.12+ (pyenv or system)
   - Install Node.js 20+ (nvm or system)
   - Create Python venv, install deps
   - `npm install` in `apps/web/`
   - Run backend: `uvicorn garuda_api.main:app --reload --port 8000`
   - Run frontend: `cd apps/web && npm run dev`
   - Verify: open `http://localhost:5173`, check API proxy to `8000`

2. **Docker path (optional)**
   - `docker compose up` starts API + optional PostGIS
   - Frontend still runs natively or in container

3. **Windows-specific notes**
   - PowerShell vs. bash commands
   - Path separator issues
   - Known VSCode settings

---

### Task 1.8 — Baseline Demo Page

**Action:** Create a minimal map page that renders without any API key.

```tsx
// apps/web/src/pages/HomePage.tsx
// - Render a MapLibre GL JS map centered on Odisha
// - Use a free, compliant tile source (document which one)
// - Show a banner: "🦅 Garuda — Demo Mode · No live data connected"
// - Display the pilot district outline if a fixture boundary exists
```

> [!NOTE]
> All demo content must be clearly labelled as DEMO. No fake data points, outbreak markers, or fabricated statistics.

---

## 📂 Expected File Changes

```
NEW: README.md
NEW: .gitignore
NEW: .env.example
NEW: LICENCE
NEW: ATTRIBUTION.md
NEW: Makefile
NEW: docker-compose.yml
NEW: .github/workflows/ci.yml
NEW: docs/SETUP.md
NEW: apps/web/  (entire scaffold)
NEW: services/api/  (entire scaffold)
NEW: packages/contracts/  (core types)
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] `git clone` → follow `docs/SETUP.md` → running app on **Linux**
- [ ] `git clone` → follow `docs/SETUP.md` → running app on **Windows**
- [ ] `npm run build` in `apps/web/` succeeds with **zero type errors**
- [ ] `ruff check` and `mypy` pass on backend code
- [ ] `pytest` passes (at least health endpoint test)
- [ ] `vitest` passes in frontend
- [ ] `GET /api/v1/health` returns 200 with version info
- [ ] Map page renders in browser showing Odisha region
- [ ] **No API key** required for the baseline demo
- [ ] `.env.example` exists; no actual secrets committed
- [ ] Demo page clearly labelled as "DEMO"

---

## 🤖 Agent Instructions

1. Before writing code, inspect Phase 0 outputs and report the plan.
2. Use exact dependency versions, not `latest`.
3. Strict TypeScript — no `any` types, no `@ts-ignore`.
4. Python code must pass `ruff` and `mypy` without disabling rules.
5. Do NOT add any data source adapters yet — this is skeleton only.
6. The map tile source must be documented and compliant (see Phase 0 findings).
7. Label every demo/placeholder element with `DEMO` or `PLACEHOLDER`.
8. Report exact commands run and their outputs.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Vite + FastAPI proxy issues on Windows | Document both native proxy config and manual CORS setup |
| MapLibre requires a tile source on first load | Use documented free tile endpoint or local static tiles |
| PWA service worker caches stale code during dev | Disable SW in development mode |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] CI pipeline runs green on push
- [ ] `docs/SETUP.md` is complete and tested
- [ ] No placeholder code that could be mistaken for real functionality
- [ ] Phase 1 report written with commands, test results, and known limitations

---

*Derived from: Development Plan §3 (Technology Stack), §6 (Stage 1), §11 (Agent Protocol)*
