# 🛠️ Garuda — Local Setup & Development Guide

This guide details how to set up, configure, initialize, and run the Garuda India Place Intelligence Platform on Linux, macOS, and Windows.

---

## 📁 Repository Structure

```
garuda/
├── backend/                  # FastAPI backend, data fixtures, seeders & tests
├── frontend/                 # React + TypeScript + Vite PWA & MapLibre GL
├── docs/                     # Unified documentation, pilot reports, plan & runbooks
├── garuda_local.db           # Pre-seeded SQLite pilot database
├── Makefile                  # Developer workflow commands
├── README.md                 # Project overview and quick start
└── .env.example              # Environment configuration template
```

---

## 📋 System Prerequisites

| Dependency | Minimum Version | Verified Version | Purpose |
|------------|-----------------|------------------|---------|
| **Python** | 3.12+ | 3.12.3 | FastAPI backend, geospatial processing, data adapters |
| **Node.js** | 20+ | 20.x | Frontend build and Vite development server |
| **npm** | 10+ | 10.x | Frontend package management |
| **SQLite** | 3.35+ | 3.40+ | Local-first relational database (WAL mode, foreign keys) |
| **Git** | 2.30+ | 2.43+ | Version control |

> [!NOTE]
> **Zero Paid Spend:** No credit card, API keys, or paid cloud services are required. The default configuration uses local SQLite, CARTO/OSM raster basemaps, and verified open public data fixtures.

---

## 🚀 Quick Setup (Linux / macOS)

### 1. Clone & Enter Repository
```bash
git clone https://github.com/johan-droid/Garuda.git
cd Garuda
```

### 2. Configure Environment
```bash
# Copy template configuration
cp .env.example .env
```
Default `.env` configuration:
```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///garuda_local.db
ADMIN_API_KEY=garuda-local-dev-admin-key-2026
SECRET_KEY=garuda-insecure-dev-secret-replace-in-production-32chars
RATE_LIMIT_ENABLED=true
LOG_JSON=false
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

### 3. Backend Setup & Seed
```bash
# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -e backend

# Initialize database schema and seed pilot data (Odisha / Khordha)
make init-db
make seed
```

### 4. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 5. Start Development Servers

You can use the provided `Makefile` or run them in separate terminals:

**Terminal 1 (Backend API on http://localhost:8000):**
```bash
source .venv/bin/activate
make dev-backend
```

**Terminal 2 (Frontend PWA on http://localhost:5173):**
```bash
make dev-frontend
```

Open your browser to `http://localhost:5173`. The Vite proxy will automatically forward API requests to `http://localhost:8000`.

---

## 🪟 Windows Setup (PowerShell)

### 1. Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e backend
```

### 2. Environment Configuration
```powershell
Copy-Item .env.example .env
```

### 3. Initialize & Seed Database
```powershell
$env:PYTHONPATH = "backend"
python -m app.db.init_db
python backend\seed_pilot.py
```

### 4. Start Development Servers
**Backend:**
```powershell
$env:PYTHONPATH = "backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```powershell
cd frontend
npm install
npm run dev
```

---

## 🧪 Testing & Verification

Run the full automated test suite to ensure system integrity:

```bash
# Run all backend unit & integration tests (52 tests)
PYTHONPATH=backend pytest backend

# Run type check on backend
PYTHONPATH=backend mypy backend/app

# Run frontend build check
cd frontend && npm run build
```

---

## 📡 API Endpoint Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Operational health probe (version, pilot region) |
| `/health/ready` | GET | Readiness probe (checks DB connectivity) |
| `/api/v1/places/search?q={query}` | GET | Search places by canonical name or historical alias |
| `/api/v1/places/{id}/profile` | GET | Multi-domain place profile (demographics, health, services, etc.) |
| `/api/v1/places/{id}/observations` | GET | Detailed observations with citable provenance records |
| `/api/v1/places/{id}/alerts` | GET | Official public health alerts with validity periods |
| `/api/v1/places/boundaries` | GET | GeoJSON boundaries for supported administrative units |
| `/api/v1/places/reverse?lat={lat}&lng={lng}` | GET | Reverse geocodes coordinates to enclosing admin unit |
| `/api/v1/sources` | GET | Public data source registry (licences, attributions) |
| `/api/v1/sources/diagnostics` | GET | Real-time source health, latency, and refresh records |
| `/api/v1/admin/import` | POST | Atomic import batch (requires `Authorization: Bearer <ADMIN_API_KEY>`) |
