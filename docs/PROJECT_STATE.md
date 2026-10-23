# 🦅 Garuda — Project State, Progression and Open Work

> **Read this first.** It is the current, evidence-based picture of the project: what has been
> built, in what order, what is actually true today, what is still fixture, and what remains.
> Written for the next developer *and* the next AI agent, so neither has to infer state from
> commit messages or from documentation that describes intent rather than reality.

| Field | Value |
|:---|:---|
| **Last updated** | 2026-10-23 |
| **Describes** | The tree after `9d3ad36`, plus this document |
| **Pilot region** | Khordha District, Odisha, India (`IN-OD-29`) |
| **Maturity** | Working pilot on seeded data. No live public dataset is ingested yet. |
| **Spend** | ₹0. Every dependency and endpoint in the default path is anonymous and keyless. |

---

## 1. What Garuda is

A place-intelligence explorer: pick a place in India (search or map click) and see source-backed
population, health, services, infrastructure, environment, resilience, history and weather panels,
plus satellite imagery of the area. The product's entire value is that a figure shown is a figure
someone can check; when it cannot be checked, the UI must say so.

Backend serves the contract; frontend renders it; the seed database holds the pilot dataset.

---

## 2. Snapshot

| Area | Reality today |
|:---|:---|
| **Stack** | FastAPI (Python 3.12) + SQLAlchemy 2.0 + Alembic (1 migration); React 18 + TypeScript 5.6 + Vite 5; MapLibre GL 4 (2D map); CesiumJS 1.146 (opt-in 3D globe at `/?globe=1`) |
| **Database** | SQLite by default (`garuda_local.db`, gitignored), Postgres supported by configuration |
| **Routes** | 19 endpoints across 5 routers (`places`, `observations`, `sources`, `admin`, `health`) |
| **Pilot data** | 10 places, 19 aliases, 7 sources, 103 observations across 8 domains |
| **Tests** | 103 backend (`pytest`), 4 frontend (`vitest`), 20 imagery (+4 skipped network tests) |
| **Static checks** | `mypy backend/app` clean (38 files), `tsc --noEmit` clean, `vite build` succeeds |
| **CI** | None yet — `.github/` is empty; all checks below are run locally |

---

## 3. How a request flows

```
map click / search
      │
      ▼
GET /api/v1/places/reverse  ──► boundary_service: which pilot boundary encloses this point?
      │                          (returns inside_coverage + coverage_note; never a silent "nearest")
      ▼
GET /api/v1/places/{id}/profile
      │
      ▼
place_service ──► observation_service ──► freshness.determine_status()
      │                                        (one rule decides current/historical/stale/unverified)
      ▼
PlaceProfile { place, hierarchy, panels[domain] = { status, observations[{ value, source_url,
               reference_period_end, quality_status }], data_gaps } }
      │
      ▼
HomePage: renders the value *and* the panel's own status badge; a panel with no data renders
          "NOT AVAILABLE" and never a substitute figure.
```

Globe path is separate: `GlobePage` → `cesium/config.ts` supplies GIBS WMTS, OpenFreeMap basemap
and Mapterhorn terrain; `imagery.ts` builds layer URLs. The locally built Sentinel-2 mosaic under
`frontend/public/imagery/` is optional and gitignored.

---

## 4. Progression (what each commit actually delivered)

| Commit | Date | Delivered |
|:---|:---|:---|
| `f81fe4f` | 2026-10-21 | Phase 0 source register, Phase 1 skeleton, first frontend shell. Scaffolding, not data. |
| `22cca6d` | 2026-10-22 | Breadth pass: 8 domain panels, seed dataset, map, admin import, consolidated docs. A wide UI over fixture data. |
| `d90d0e4` / `ce274cd` | 2026-10-22 | README and gitignore work; no runtime change. |
| `076b2a9` | 2026-10-22 | Configuration aliasing, type safety, observation filter fixes. |
| `0b39744` | 2026-10-22 | Seven-domain frontend/backend integration, health routing, "staging qualification". |
| `c9471ab` | 2026-10-22 | 11-task backend hardening: migrations, provider adapters, hot backup. **Important:** adapters parse payloads; nothing fetches from a provider. |
| `14698e5` | 2026-10-23 | Opt-in CesiumJS globe (GIBS imagery, terrain, region fly-to). |
| `9d3ad36` | 2026-10-23 | **Honesty milestone.** Coverage semantics, truthful freshness, `source_url` in the contract, fabricated UI fallbacks deleted, MapLibre boundary property fixed, Vitest suite, `make dev`, Sentinel-2 tooling. |

The arc matters: commits 1–8 built a complete-looking surface whose numbers were fixtures.
Commit 9 made the surface stop claiming more than the data supports. Anything after this point
should start from §5, not from the pre-`9d3ad36` behaviour.

---

## 5. What is true today, and what is still fixture

| Capability | Status | Evidence / limit |
|:---|:---|:---|
| Place search over the in-repo table | **Real** | 10 places with aliases; `/places/search`. Not India-wide. |
| Reverse geocode + coverage honesty | **Real** | Returns `inside_coverage` and a `coverage_note`; an out-of-coverage pin is refused, not mapped onto the nearest boundary. |
| Boundary geometry | **Schematic fixture** | `backend/data/fixtures/boundaries/khordha_pilot.geojson`. Not LGD, not survey-grade. |
| Profile panels and statuses | **Real mechanism** | Status derives from `freshness.determine_status`; 8 domains; empty panels are `unavailable` with `data_gaps`. |
| Demographics (Census 2011) | **Reference-dated, unverified provenance link** | Rows carry `reference_period_end` and render as `historical`; `source_url` is not populated (0 of 103), so the app cannot link to the record it cites. |
| Health, services, infrastructure, environment, resilience, history, weather | **Fixture** | 43 of 103 observations carry no reference period and are therefore `unverified`; they render behind that badge, never as current measurements. |
| Health alerts | **Real endpoint, empty data** | `/places/{id}/alerts` filters by validity window and category; no bulletin has been ingested. |
| Satellite imagery on the globe | **Real tiles, no acquisition date** | GIBS (anonymous, CORS `*`), OpenFreeMap basemap, Mapterhorn terrain. The UI does not yet print the imagery date. |
| Sentinel-2 mosaic pipeline | **Works, offline-tested** | `tools/imagery/build_composite.py`, region `odisha-test`, manifest records scene id/date/cloud. Not wired into the UI. |
| Frontend data honesty | **Real and tested** | 4 component tests: coverage notice (both branches), not-available card, status badges. |
| Provider integration | **None** | Zero live datasets ingested. `provider_adapters.py` is parsing only. |

### Provider verdicts (probed 2026-10-23, no credentials)

| Provider | Verdict |
|:---|:---|
| NASA GIBS WMTS | **approved** — `200`, `access-control-allow-origin: *`, date in URL |
| Earth Search STAC (Sentinel-2 L2A) | **approved** — anonymous `200`, 931 scenes over the Khordha bbox |
| Mapterhorn terrain (Copernicus GLO-30) | **approved** (already shipped) |
| WorldPop REST | **approved as modelled** — must be labelled estimated/approximate |
| Overpass API | **conditional** — `502 at capacity` is normal; one bounded query per user action, never on map load |
| Census of India bulk tables | **conditional** — authoritative but bulk download, not an API |
| Wikimedia / Wikidata | **conditional** — names and culture only, never statistics |
| NASA FIRMS | **rejected** — `Invalid MAP_KEY` without registration |
| ISRO / NRSC Bhoonidhi | **rejected** — no verified anonymous interface |
| Public Nominatim as the app's geocoder | **rejected** — OSMF policy forbids autocomplete/systematic reverse use by apps |
| CARTO raster basemaps | **rejected** — keyless requests now return watermarked tiles |

---

## 6. What is not built

- No live public dataset in any panel; every indicator is seeded.
- No `source_url` (0/103) and no `published_at`, so no per-record links in the UI.
- No imagery acquisition date on the globe; no scene catalogue, timeline, before/after, or change detection.
- No real administrative geometry or LGD codes; the resolver only knows the 10 seeded places.
- No WorldPop modelled layer, no facility directory, no health bulletin ingest.
- No frontend tests beyond `HomePage` states; no globe tests.
- No CI workflow: `.github/` is empty, so nothing runs these checks automatically.
- No deployment configuration (no Dockerfile, no `vercel.json`). Production behaviour is
  **unverified**; the API expects a writable SQLite file today.
- `tools/imagery` has no shipped usage document (the local `docs/imagery-pipeline.md` is gitignored).

---

## 7. Roadmap and acceptance criteria

One capability end-to-end before the next. Every item names the evidence that proves it works.
No item may introduce a credential, a paid service, or persistence of a user's selected location.

### Milestone 1.5 — finish making the current UI honest
1. **Unverified panels: show the figure or show nothing.** Decide one behaviour for `unverified`
   cards and test it. *Done when:* a component test proves an unverified value is not presented as
   a present-day measurement.
2. **Imagery date on the globe.** Build the GIBS URL with the date segment and print
   `Imagery: <layer> — <date>`. *Done when:* the rendered page shows the date in the WMTS path,
   with one unit test on the URL builder.
3. **Provenance links.** Populate `source_url` (and `published_at` where a source publishes one) in
   the seed/ingest path and render it per metric. *Done when:* a profile shows a resolvable link per
   sourced figure, and undated fixtures show none.

### Milestone 2 — imagery and time comparison
4. **Scene catalogue** over Earth Search STAC (bbox + range → scenes with `datetime`,
   `eo:cloud_cover`, `proj:epsg`). *Done when:* a recorded-fixture unit test plus a bounded live
   smoke test behind `GARUDA_NETWORK_TESTS=1`.
5. **Timeline UI** listing scenes for the pin's bbox; selecting one changes the imagery and its date
   is visible. *Done when:* the shown date matches the STAC item.
6. **Before/after only where two real scenes exist**, stating both dates. *Done when:* it refuses to
   render with one side missing.
7. **Change detection, honestly labelled** (NDVI or built-up delta with method note and confidence
   caveat; no land-use claims). *Done when:* unit-tested on synthetic rasters.

### Milestone 3 — real Odisha statistics
8. **One bulk source, one district, end-to-end** (Census 2011 PCA district tables for Khordha), with
   table file name, table code, reference period and publisher in provenance.
   *Done when:* the panel is `historical`, cites the table, and values match the parsed file.
9. **WorldPop as an explicitly modelled layer**, labelled approximate, with its year.
10. **Health: facility directory before surveillance** — district facility list first; case counts
    only once a bulletin with a week-ending date is parsed. *Done when:* each observation has
    `reference_period_end` and `source_url`.
11. **Retire the remaining fixtures.** Any indicator without a source becomes `unavailable` with a
    `data_gap` reason. *Done when:* the pilot profile contains zero undated values.

### Milestone 4 — change, industry, environment
12. **One mining/industrial record ingest** (manual, documented, URL and date), presented next to
    imagery change — never as its explanation.
13. **Water and vegetation proxies** from Sentinel-2 indices with method and scene dates; the panel
    never says "flooded now".

### Milestone 5 — India, then world
14. **Real geometry + LGD codes**, replacing the schematic fixture (keep it as a labelled fallback).
    *Done when:* a pin in another Odisha district resolves to that district.
15. **Generalise the resolver and source registry** so a new state is data, not a code fork.
    *Done when:* adding a state requires no change under `frontend/src`.
16. **Geocoding beyond the in-repo table** — self-hosted Nominatim or a bulk OSM extract. The public
    Nominatim instance is excluded by its own usage policy.

### Cross-cutting, whenever a provider is added
Hard timeout; cancel on a new pin; bounded response size; per-provider failure state; no retries
against capacity errors; attribution + reference date in the response; a recorded-fixture unit test
**and** a separately marked live smoke test so a mock can never be mistaken for an integration.

---

## 8. Rules for any change

These are enforced by review, and the first four are covered by tests. Do not relax them to make a
panel look fuller.

1. **Never invent a value, a profile, an alert, or a boundary.** If the backend has nothing, the UI
   says "not available" and why. The deleted fallbacks in `HomePage.tsx` are the precedent.
2. **Coverage is explicit.** Location responses carry `inside_coverage` + `coverage_note`; a pin
   outside the pilot never inherits the nearest boundary's statistics.
3. **One freshness rule.** `backend/app/services/freshness.py` is the only place that decides
   `current`/`historical`/`stale`/`unverified`. Data without a reference period is never `current`.
4. **Provenance travels with the value.** Publisher, licence, record URL and reference period belong
   in the response contract, not in a hardcoded caption.
5. **No retention.** A user's selected or bookmarked place lives in React state for the session;
   never in `localStorage`, `sessionStorage`, cookies or a server-side log of pinned areas.
6. **Anonymous by default.** No key, no account, no paid tier in the default path. Check a
   provider's usage policy before writing an adapter — two providers were rejected on policy alone.
7. **No secrets in git.** `.env` is ignored; `.env.example` is the template.
8. **A new "we don't know" state needs a test**, because that state is the easiest thing to
   accidentally fill in.

---

## 9. Verification ladder

Run from the repository root. A green build alone is not evidence that the delivered behaviour is
right; the last two rows are what prove it.

| Command | Proves | Today |
|:---|:---|:---|
| `make test` | Backend unit, contract and integration behaviour | 103 passed |
| `make test-frontend` | UI honesty states (coverage, not-available, badges) | 4 passed |
| `make test-imagery` | Sentinel-2 pipeline offline | 20 passed, 4 skipped |
| `make lint` | Backend type safety | clean (38 files) |
| `make build` | TypeScript + production bundle | succeeds |
| `make dev` | Both servers on 8000 / 5173 | see §12 |
| `curl` the endpoint | The JSON a user actually receives | required for API/UI changes |

`make test-imagery-live` (gated by `GARUDA_NETWORK_TESTS=1`) is the only network test; everything
else must pass offline.

---

## 10. Code map

| Path | Responsibility |
|:---|:---|
| `backend/app/api/routes/` | HTTP surface: `places` (search/reverse/profile/alerts/boundaries/status), `observations`, `sources`, `admin`, `health` |
| `backend/app/domain/contracts.py` | Response models; the contract mirrored in `frontend/src/types/contracts.ts` |
| `backend/app/domain/common.py` | `DataStatus`, `HealthCategory`, domain names. Changing these changes the public API |
| `backend/app/services/freshness.py` | The single freshness/status rule and per-domain max age |
| `backend/app/services/boundary_service.py` | Point-in-polygon resolution, `inside_coverage`, distance, `coverage_note` |
| `backend/app/services/place_service.py` | Profile assembly, panel status, serialisation |
| `backend/app/services/provider_adapters.py` | Parsers for external payloads. **Parsing only — no fetch path exists.** |
| `backend/app/services/http_client.py` | Shared outbound HTTP with timeout/size bounds |
| `backend/seed_pilot.py` | The pilot dataset. Idempotent; provenance comments state which values are fixtures |
| `backend/data/fixtures/` | Schematic boundaries and sample payloads |
| `frontend/src/pages/HomePage.tsx` | The 2D experience: search, panels, badges, not-available card, coverage notice |
| `frontend/src/pages/GlobePage.tsx`, `components/CesiumGlobe.tsx`, `cesium/` | The opt-in 3D globe |
| `frontend/src/components/MapView.tsx` | MapLibre map, boundary layers, click handling |
| `frontend/src/api/client.ts` | Fetch wrappers + the in-repo `PILOT_PLACES` table |
| `tools/imagery/` | Sentinel-2 mosaic builder, region config, offline tests |

---

## 11. Documentation map

| Document | Use |
|:---|:---|
| **`docs/PROJECT_STATE.md`** (this) | Current truth, progression, open work. Start here. |
| `README.md` | Product overview, setup, API reference, testing |
| `docs/SETUP.md` | Step-by-step local setup |
| `docs/PRODUCTION.md` | Deployment and operations manual |
| `docs/source-register/` | Per-domain source evaluations, licence inventory, blockers |
| `docs/phases/` | **Historical plan** (Phases 00–10). Useful for intent, not for current state. |
| `docs/PILOT_VERIFICATION_REPORT.md` | **Superseded.** It declares the pilot "verified & ready" with "grounded open data across seven domains"; the 2026-10-23 audit found those domains were fixtures. Read §5 here instead. |
| `docs/cesium-poc.md` | Globe proof-of-concept notes |

---

## 12. Pitfalls learned the hard way

- **Ports are not negotiable.** `make dev` frees `8000` and `5173` by stopping whatever holds them,
  and Vite runs with `strictPort` so it fails loudly rather than drifting to 5174, where the `/api`
  proxy does not exist.
- **Use `localhost`, not `127.0.0.1`.** Vite binds the IPv6 loopback; `127.0.0.1:5173` refuses.
- **Frontend tests need no backend.** The API client and the map are mocked; `HomePage` itself runs.
- **Imagery tests need `numpy`/`rasterio`.** They run under the system Python via
  `make test-imagery`; the project `.venv` does not carry those packages.
- **`.venv` already exists**, and `backend/.venv` is a symlink to it. Running
  `python3 -m venv .venv` inside `backend/` fails by design; `pip install` outside the activated
  venv hits PEP 668.
- **Re-seeding is idempotent** (`make seed`). Re-run it after changing freshness semantics so stored
  `quality_status` matches the read-time rule.
- **Undated means unverified.** Adding a fixture value without a reference period will make its panel
  `unverified` — that is the intended behaviour, not a bug to "fix" in the UI.

---

## 13. Keeping this document honest

Update it in the same commit as any change to: coverage semantics, status rules, the response
contract, seeded data, tested UI states, or the roadmap. When a claim here stops being true, the
document is worse than no document, because the next agent will build on it.
