# 🦅 Garuda — India Place Intelligence Platform

## Master Implementation Roadmap

> **Vision:** An open-source-first, zero-planned-spend explorer where a person can search for or click any supported place in India—including remote areas—and see source-backed information about population, public health, facilities, education, policy, history, culture, weather, disasters and environmental change.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Code Name** | Garuda (the eagle's eye) |
| **Document Version** | 1.0 — 18 October 2026 |
| **Licence Target** | Open-source-first |
| **Spend Target** | ₹0 (zero planned spend) |
| **Pilot Region** | One district in Odisha (to be selected in Phase 0) |

---

## Non-Negotiable Principles

These **cannot** be relaxed or deferred — every phase must honour them:

1. **No hallucination** — every factual claim traces to a validated source record.
2. **No fake live data** — historical is "historical", stale is "stale", unavailable is "unavailable".
3. **No invented boundaries** — if a village boundary doesn't exist, show coordinates + nearest known admin unit.
4. **No paid API/hosting** required in the default path.
5. **No committed secrets** — ever.
6. **No individual health diagnosis** — the map is not a medical tool.
7. **No unapproved public deployment**.
8. **No silent fallback** across incompatible metrics.
9. **Documented, permitted data access** with verified licences and attribution.
10. **Unknown is acceptable; hallucination is not.**

---

## Technology Stack (Agreed)

| Layer | Choice | Notes |
|-------|--------|-------|
| **Frontend** | TypeScript + React + Vite (PWA) | One responsive codebase — Android, Windows, Linux |
| **Mapping** | MapLibre GL JS | Open-source map renderer; pan/zoom/tilt |
| **Map Data** | OpenStreetMap-derived + verified boundary datasets | ODbL attribution applies |
| **Backend** | Python 3.12+, FastAPI, Pydantic, httpx | Typed contracts, async provider integrations |
| **Geospatial DB** | PostgreSQL + PostGIS; Shapely/GeoPandas | Spatial matching, point-in-polygon |
| **Local Storage** | SQLite (local/small); PostgreSQL (shared) | Local-first, portable |
| **Frontend Data** | TanStack Query + Zod validation | Loading/error states, retries, staleness |
| **Charts** | Apache ECharts | Only chart dated observations |
| **Testing** | pytest, HTTPX test client, Vitest, Playwright | Contract tests, edge-case fixtures |
| **CI/Packaging** | GitHub Actions (free tier), optional Docker Compose | Docker not mandatory |

---

## Repository Structure (Target)

```
garuda/
├── apps/web/                  # TypeScript PWA — UI, map, components
├── services/api/              # FastAPI routes & middleware
├── services/ingestion/        # Source adapters & refresh jobs
├── packages/contracts/        # Shared schemas & types (Pydantic + Zod)
├── data/fixtures/             # Small licensed test fixtures
├── docs/                      # Source register, runbooks, phase docs
│   └── phases/                # ← You are here
└── tests/                     # Unit, contract, integration, e2e
```

---

## Phase Overview

| Phase | Name | Est. Duration | Key Deliverable |
|-------|------|---------------|-----------------|
| **0** | [Feasibility & Source Verification](./PHASE_00_FEASIBILITY.md) | 3–5 days | Verified pilot sources, sample fixtures, blocker log |
| **1** | [Project Skeleton](./PHASE_01_SKELETON.md) | 3–5 days | Buildable mono-repo, CI, local run on Win/Linux |
| **2** | [Map & Place Search](./PHASE_02_MAP_SEARCH.md) | 1–2 weeks | MapLibre + geocoder → resolve supported geography |
| **3** | [Place Profile & Provenance](./PHASE_03_PROFILE_PROVENANCE.md) | 1 week | Profile panels, source cards, missing-data states |
| **4** | [Population, Services, Education & History](./PHASE_04_DATA_DOMAINS.md) | 2–4 weeks | One verified dataset per domain, traced to sources |
| **5** | [Health MVP](./PHASE_05_HEALTH_MVP.md) | 2–4 weeks | Official bulletins, historical/current split, facilities |
| **6** | [Resilience & Offline](./PHASE_06_RESILIENCE_OFFLINE.md) | 1–2 weeks | Cache, diagnostics, PWA shell, saved places, export |
| **7** | [Weather & Disasters (v2)](./PHASE_07_WEATHER_DISASTERS.md) | 2–4 weeks | IMD/NDMA alerts, forecast charts, validity windows |
| **8** | [Satellite & Environment (v2/v3)](./PHASE_08_SATELLITE_ENVIRONMENT.md) | 3–8+ weeks | ISRO/Sentinel imagery, change analysis |
| **9** | [Hardening & Release](./PHASE_09_HARDENING_RELEASE.md) | 1–3 weeks | Security, a11y, perf, attribution, packaging |
| **10** | [Pilot & Expansion](./PHASE_10_PILOT_EXPANSION.md) | Ongoing | Odisha pilot, feedback, gradual expansion |

---

## Version Roadmap

### Version 1 — Credible Place Intelligence (Phases 0–6)
- Responsive PWA with search, click, coordinate selection
- Place profiles: population, health, facilities, education, history/culture
- Verified public datasets with provenance, freshness, coverage
- Local-first operation; no paid key required

### Version 2 — Weather, Disaster & Satellite (Phases 7–8)
- Weather observations/forecasts with station/model coverage
- Official disaster alerts with issuer, validity windows, severity
- Indian satellite products first; Sentinel/NASA fallback
- Historical imagery comparisons, environmental indicators

### Version 3 — Advanced Analysis (Future)
- Historical timelines, spatial aggregation, district/block comparisons
- Moderated user reports
- Institutional exports, role-based access, audit logs
- Modelled risk indicators with documented methodology

---

## How to Use These Phase Documents

Each phase file follows a consistent structure:

1. **Objective** — what this phase achieves
2. **Prerequisites** — what must be done before starting
3. **Detailed Tasks** — numbered, actionable work items
4. **File Changes** — expected files to create/modify
5. **Acceptance Criteria** — exit gates (automated tests where possible)
6. **Agent Instructions** — specific directives for the coding agent
7. **Risks & Mitigations** — phase-specific concerns
8. **Definition of Done** — checklist before moving to next phase

> [!IMPORTANT]
> **Do NOT advance to the next phase just because the app compiles.** Each phase has explicit exit gates that must pass.

---

*Document generated from: India_Place_Intelligence_Platform_Development_Plan.pdf v1.0*
