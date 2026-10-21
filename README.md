# 🦅 Garuda — India Place Intelligence Platform

> **Vision:** An open-source-first, zero-planned-spend explorer where anyone can search for or click any supported place in India—including remote areas—and see verified, source-backed information about population, public health, facilities, education, policy, history, culture, weather, disasters, and environmental change.

---

## ⚡ Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm

### Backend Setup (FastAPI)
```bash
# Activate virtual environment
source .venv/bin/activate

# Run backend test suite
PYTHONPATH=services/api pytest services/api

# Run backend dev server (port 8000)
PYTHONPATH=services/api uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup (React + Vite + TypeScript PWA)
```bash
cd apps/web
npm install
npm run dev
```

---

## 🏛️ Architecture & Principles
1. **No Hallucination:** Every factual data point traces to a verified source record with licence and attribution.
2. **Zero Paid Spend:** Designed to operate entirely on verified public open data, local-first SQLite, and free-tier resources.
3. **Explicit Data Freshness:** Clear demarcation between current, historical, stale, and unavailable datasets.

---

## 📜 Licence & Attribution
- Project Licence: MIT Licence. See [LICENCE](./LICENCE).
- Data Sources & Open-Source Libraries: See [ATTRIBUTION.md](./ATTRIBUTION.md).
