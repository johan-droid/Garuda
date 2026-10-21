# Phase 0 — Feasibility & Source Verification

> **Duration:** 3–5 days  
> **Objective:** Validate that the Odisha pilot is viable before writing any application code.

---

## 🎯 Objective

Pick a specific Odisha pilot area (one district + manageable set of blocks/villages) and verify that boundary files, population tables, health bulletins, and a place-search path can actually be tested. This is **research and validation only** — no app code is written in this phase.

---

## 📋 Prerequisites

- Access to a machine with internet for source research
- A text editor for documenting findings
- Familiarity with the source document (Sections 4, 5, 16)

---

## 📝 Detailed Tasks

### Task 0.1 — Select Pilot District

**Action:** Choose one Odisha district based on **data availability**, not news stories.

| Criterion | Requirement |
|-----------|-------------|
| Boundary files exist | GeoJSON/Shapefile for district + blocks + villages |
| Population data exists | Census table with at least total population by village |
| Health data exists | At least one official bulletin or IDSP/NCDC record |
| Place search works | Nominatim or equivalent returns results for the area |

**Output:** A written justification in `docs/source-register/pilot-selection.md` explaining why this district was chosen.

> [!WARNING]
> Do NOT choose a pilot location because a news story suggests an outbreak. Choose based on verifiable data coverage.

---

### Task 0.2 — Boundary/Geography Source Verification

**Action:** For each candidate boundary source, fill out the verification checklist.

```markdown
## Source: [Name]
- **Publisher:** 
- **URL:** 
- **Licence/Terms:** 
- **Attribution required:** 
- **Access mode:** (download / API / manual)
- **Rate limits:** 
- **Format:** (GeoJSON / Shapefile / TopoJSON)
- **Coverage:** (state / district / block / village)
- **Vintage/Version:** 
- **Sample retrieved:** Yes/No (date: YYYY-MM-DD)
- **Status:** VERIFIED / VERIFIED WITH LIMITS / MANUAL ONLY / UNAVAILABLE / NOT YET TESTED
- **Notes:**
```

**Sources to evaluate:**
1. Survey of India open data / geospatial publications
2. Census of India administrative tables
3. OpenStreetMap / Nominatim geocoder
4. State-level GIS portals (Odisha)
5. Any other documented boundary source

**Output:** `docs/source-register/geography-sources.md`

---

### Task 0.3 — Population Data Source Verification

**Action:** Verify at least one population dataset can be obtained for the pilot area.

**Sources to evaluate:**
1. Census of India 2011 (Office of Registrar General)
2. Census 2021 data (if available)
3. Official open-data portal (data.gov.in)
4. State-level statistical publications

**For each source, document:**
- Reference year and definitions
- Geographic level (village / block / district)
- Download format and access method
- Licence and attribution requirements
- Whether interpolation/projection is involved (if so, flag it — no undisclosed interpolation)

**Output:** `docs/source-register/population-sources.md`  
**Output:** `data/fixtures/population-sample.json` — a small sample fixture with retrieval date

---

### Task 0.4 — Health Data Source Verification

**Action:** Verify at least one official health-domain record exists for the pilot area, OR explicitly document that no suitable machine-readable feed exists.

**Sources to evaluate:**
1. MoHFW (Ministry of Health and Family Welfare) publications
2. NCDC (National Centre for Disease Control) weekly bulletins
3. IDSP (Integrated Disease Surveillance Programme) — public materials only
4. National Health Mission state-level data
5. Odisha state health department publications
6. Official open-data catalogues

**Critical checks:**
- ⚠️ "Public bulletin" ≠ "live API" — many are PDFs requiring manual ingestion
- Distinguish: official alerts vs. historical cases vs. routine surveillance
- Note geographic resolution (state / district / block / village)
- Record update frequency and lag time

**Output:** `docs/source-register/health-sources.md`  
**Output:** `data/fixtures/health-sample.json` — a small sample fixture (or documented finding of unavailability)

---

### Task 0.5 — Map Provider & Tile Source Verification

**Action:** Verify that the chosen map tile provider is compliant with its terms.

**Check for each provider:**

| Check | Status |
|-------|--------|
| Licence allows the intended use | |
| Attribution requirements documented | |
| Rate limits / quotas identified | |
| Free tier sufficient for pilot | |
| Tile format compatible with MapLibre GL JS | |
| Terms permit caching (and for how long) | |

**Providers to evaluate:**
1. OpenStreetMap tile servers (are we allowed to use them directly? usually NO for heavy use)
2. Alternative free tile providers (e.g., Stamen, CartoCDN, MapTiler free tier)
3. Self-hosted tile generation from OSM data

**Output:** `docs/source-register/map-tile-sources.md`

---

### Task 0.6 — Place Search / Geocoder Verification

**Action:** Verify geocoder access for the pilot area.

**Test queries:**
- District name → should return correct polygon/point
- Block name → disambiguation if repeated names
- Village name → results with admin hierarchy
- PIN code → correct area
- Coordinates (lat, lng) → reverse geocode to nearest admin unit

**Output:** `docs/source-register/geocoder-evaluation.md`

---

### Task 0.7 — Licence & Terms Inventory

**Action:** Create a consolidated licence inventory for every dependency and data source.

```markdown
## Licence Inventory

| Component | Licence | Attribution | Redistribution | Notes |
|-----------|---------|-------------|----------------|-------|
| MapLibre GL JS | BSD-3-Clause | Yes | Yes | |
| OpenStreetMap data | ODbL | Yes | ShareAlike | |
| [Tile provider] | [?] | [?] | [?] | |
| [Boundary source] | [?] | [?] | [?] | |
| [Population source] | [?] | [?] | [?] | |
| [Health source] | [?] | [?] | [?] | |
```

**Output:** `docs/source-register/licence-inventory.md`

---

### Task 0.8 — Blocker Log

**Action:** Document every blocker or significant risk discovered during this phase.

```markdown
## Blockers

| # | Description | Severity | Mitigation | Status |
|---|-------------|----------|------------|--------|
| 1 | [e.g., No village-level health data for Odisha] | HIGH | [Show district-level, mark as district] | OPEN |
```

**Output:** `docs/source-register/blockers.md`

---

## 📂 Expected File Outputs

```
docs/source-register/
├── pilot-selection.md
├── geography-sources.md
├── population-sources.md
├── health-sources.md
├── map-tile-sources.md
├── geocoder-evaluation.md
├── licence-inventory.md
└── blockers.md

data/fixtures/
├── population-sample.json
└── health-sample.json
```

---

## ✅ Acceptance Criteria (Exit Gate)

All of the following must be true before moving to Phase 1:

- [ ] A specific Odisha pilot district is selected with documented justification
- [ ] At least **one viable place/boundary source** has a sample fixture and documented terms
- [ ] At least **one population dataset** has a sample fixture and documented terms
- [ ] At least **one official health source** has a sample fixture and documented terms — OR an explicit finding that no suitable machine-readable feed exists
- [ ] A compliant map tile provider is identified with attribution requirements
- [ ] A geocoder is tested and results documented
- [ ] All blockers are recorded with severity and mitigation plan
- [ ] Every source has a verification status: `VERIFIED`, `VERIFIED WITH LIMITS`, `MANUAL ONLY`, `UNAVAILABLE`, or `NOT YET TESTED`
- [ ] **No source is labelled "INTEGRATED" when it is merely "NOT YET TESTED"**

---

## 🤖 Agent Instructions

1. **Do NOT write application code** in this phase. This is pure research and documentation.
2. Use `curl`, `wget`, or Python scripts only to test API endpoints and download samples.
3. Save all sample data to `data/fixtures/` with retrieval dates.
4. When testing geocoders, record exact queries, responses, and any rate-limit warnings.
5. If a source requires manual download (e.g., PDF bulletins), document the manual process.
6. Do not assume any API is available just because a website exists.
7. Record every URL you tested, even if it returned errors.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| No stable health API exists for Odisha | Use permitted official downloads/manual refresh; mark domain as MANUAL ONLY |
| Village-level boundaries unavailable | Use block-level boundaries; never pretend district data is village-level |
| Geocoder rate limits too restrictive | Evaluate self-hosted Nominatim or alternative geocoders |
| Census data is only available as PDF | Write a manual ingestion process; document the transformation |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Source register directory contains all 8 documents
- [ ] At least 2 sample fixtures exist in `data/fixtures/`
- [ ] No unresolved HIGH-severity blockers without a documented mitigation plan
- [ ] Phase 0 findings reviewed and approved by project owner

---

*Derived from: Development Plan §4 (Data Sources), §5 (Anti-hallucination), §6 (Stage 0), §16 (Odisha Pilot)*
