# Phase 8 — Satellite & Environment (Version 2/3)

> **Duration:** 3–8+ weeks  
> **Objective:** Test ISRO/NRSC/Bhuvan access, integrate satellite imagery metadata, Sentinel/NASA fallback, land cover / vegetation / water change analysis — with strict scene metadata (dates, resolution, cloud cover, delay).

---

## 🎯 Objective

Add satellite imagery and environmental analysis capabilities. This is the most complex phase due to data size, licence variations, and the critical need to be honest about what satellite data shows (and doesn't show). **Indian satellite products are preferred**, with documented scientific fallbacks.

---

## 📋 Prerequisites

- **Phase 7 COMPLETE** — weather/disaster integration done
- Source verification for satellite products (separate from Phase 0 — this requires product-level checks)
- Understanding of remote sensing limitations

---

## 📝 Detailed Tasks

### Task 8.1 — ISRO/NRSC/Bhuvan Product Verification

**Action:** Evaluate each Indian satellite product individually.

**Products to evaluate:**

| Product | Provider | Check |
|---------|----------|-------|
| Bhuvan portal data | ISRO/NRSC | API access, terms, resolution, revisit |
| Resourcesat imagery | ISRO/NRSC | Access mode, licence, coverage |
| Cartosat DEM/imagery | ISRO/NRSC | Access, resolution, redistribution |
| INSAT weather imagery | ISRO | Access, latency, resolution |
| IRS land cover products | ISRO/NRSC | Access, methodology, vintage |

**For each product, verify:**

```markdown
## Product: [Name]
- **Provider:** ISRO / NRSC
- **Access mode:** API / portal download / manual request
- **Licence:** 
- **Attribution required:** 
- **Redistribution allowed:** 
- **Resolution:** (spatial, e.g., 5.8m / 23.5m / 56m)
- **Revisit interval:** (e.g., 5 days / 24 days)
- **Processing delay:** (how long after acquisition until available)
- **Coverage:** (India-wide? specific regions?)
- **Cloud cover handling:** 
- **Sample retrieved:** Yes/No (date)
- **Status:** VERIFIED / VERIFIED WITH LIMITS / UNAVAILABLE / NOT YET TESTED
- **Notes:**
```

> [!IMPORTANT]
> "ISRO-first is a sourcing preference, not an assumed endpoint." Verify access to each product individually. Do NOT assume a universal public API or unrestricted high-resolution real-time imagery.

**Output:** `docs/source-register/satellite-isro-sources.md`

---

### Task 8.2 — Fallback Satellite Source Verification

**Action:** Evaluate international satellite sources as documented fallbacks.

**Products to evaluate:**

| Product | Provider | Resolution | Revisit | Licence |
|---------|----------|-----------|---------|---------|
| Sentinel-2 | Copernicus/ESA | 10m | 5 days | Open (with attribution) |
| Sentinel-1 SAR | Copernicus/ESA | 5m | 6 days | Open |
| Landsat 8/9 | USGS/NASA | 30m | 16 days | Public domain |
| MODIS | NASA | 250m-1km | Daily | Public domain |
| VIIRS | NASA/NOAA | 375m | Daily | Public domain |

**Output:** `docs/source-register/satellite-fallback-sources.md`

> [!WARNING]
> Fallback only when source, geography, resolution, and time period are comparable. Don't silently switch from 5m ISRO to 30m Landsat.

---

### Task 8.3 — Satellite Imagery Adapter

**Action:** Build satellite data adapter(s).

```
services/ingestion/src/adapters/satellite/
├── __init__.py
├── base_satellite.py     # Satellite-specific adapter base
├── bhuvan_adapter.py     # Bhuvan/ISRO products
├── sentinel_adapter.py   # Copernicus Sentinel
├── landsat_adapter.py    # USGS Landsat (if needed)
└── scene_metadata.py     # Scene metadata models
```

**Scene metadata model:**

```python
class SatelliteScene(BaseModel):
    """Metadata for a single satellite scene."""
    scene_id: str
    satellite: str         # "Resourcesat-2A" | "Sentinel-2A" | etc.
    sensor: str            # "LISS-IV" | "MSI" | "OLI" | etc.
    acquisition_date: datetime
    cloud_cover_pct: float
    spatial_resolution_m: float
    processing_level: str  # "L1C" | "L2A" | etc.
    coverage_geometry: dict  # GeoJSON footprint
    provider: str
    licence: str
    attribution: str
    download_url: str | None
    thumbnail_url: str | None
    processing_delay_hours: float | None  # Time from acquisition to availability
    
    # Honest metadata
    is_historical: bool    # Not "live" — show acquisition date
    notes: str | None
```

> [!CAUTION]
> **Satellite imagery is NOT live video.** Revisit intervals, processing delay, clouds, and resolution limit what can be inferred. It cannot reliably reveal individual activity.

---

### Task 8.4 — Environmental Analysis Adapters

**Action:** Build adapters for derived environmental products.

**Analysis types (implement one at a time):**

| Analysis | Input | Output | Notes |
|----------|-------|--------|-------|
| Vegetation index (NDVI) | Sentinel-2 bands | NDVI values per pixel | Show date, resolution |
| Water body extent | Sentinel-2 / SAR | Water area in sq km | Show acquisition date |
| Land cover classification | Multi-temporal imagery | Land use categories | Show methodology, vintage |
| Change detection | Two scenes | Before/after comparison | Show both dates clearly |

```python
class EnvironmentalIndicator(Observation):
    """Environmental analysis result."""
    analysis_type: str       # "ndvi" | "water_extent" | "land_cover"
    methodology: str         # Description of how it was derived
    input_scenes: list[str]  # Scene IDs used
    acquisition_dates: list[datetime]
    spatial_resolution_m: float
    confidence_notes: str    # e.g., "Cloud contamination in NE quadrant"
    
    # For change detection
    comparison_date_1: datetime | None
    comparison_date_2: datetime | None
```

---

### Task 8.5 — Satellite/Environment Panel UI

```
apps/web/src/components/profile/satellite/
├── SatellitePanel.tsx           # Main satellite panel
├── SceneGallery.tsx             # Available scenes with metadata
├── SceneMetadataCard.tsx        # Date, resolution, cloud cover
├── ImageryViewer.tsx            # View satellite imagery (if available)
├── ChangeDetection.tsx          # Before/after comparison slider
├── EnvironmentIndicators.tsx    # NDVI, water extent, etc.
├── SatelliteLimitations.tsx     # Honest disclaimer about capabilities
└── ResolutionExplainer.tsx      # Visual showing what resolution means
```

**Satellite panel layout:**

```
┌─────────────────────────────────────────┐
│ 🛰️ Satellite & Environment — [Place]    │
├─────────────────────────────────────────┤
│ ℹ️ Satellite imagery shows surface       │
│ conditions at the time of acquisition,  │
│ not live video. See dates and notes.    │
├─────────────────────────────────────────┤
│ 📸 AVAILABLE SCENES                     │
│ ┌─────────────────────────────────────┐ │
│ │ 🛰️ Resourcesat-2A LISS-IV           │ │
│ │ Date: 2026-10-05 10:30 IST         │ │
│ │ Resolution: 5.8m                    │ │
│ │ Cloud cover: 12%                    │ │
│ │ Processing delay: 48 hours          │ │
│ │ Source: ISRO/NRSC | Licence: [X]   │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ 🛰️ Sentinel-2A MSI (Fallback)       │ │
│ │ Date: 2026-10-08 10:15 UTC         │ │
│ │ Resolution: 10m                     │ │
│ │ Cloud cover: 5%                     │ │
│ │ Source: Copernicus/ESA              │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ 🌿 VEGETATION INDEX (NDVI)              │
│ Period: Oct 2026 | Resolution: 10m     │
│ [Color-coded NDVI map overlay]          │
│ Methodology: [description]             │
├─────────────────────────────────────────┤
│ 🌊 WATER EXTENT                         │
│ Detected area: 12.3 sq km              │
│ Date: 2026-10-05                        │
│ Change from 2025-10: +2.1 sq km (±0.5) │
│ Source scenes: [IDs]                    │
├─────────────────────────────────────────┤
│ 🔄 HISTORICAL COMPARISON                │
│ [Before/After slider]                   │
│ Date 1: 2025-10-05 | Date 2: 2026-10-05│
│ ⚠️ Cloud cover differences may affect   │
│    visual comparison.                   │
└─────────────────────────────────────────┘
```

---

### Task 8.6 — Imagery Map Overlays

**Action:** Allow satellite imagery as map overlays.

```typescript
// Map layer: satellite-imagery
// - Toggle satellite overlay on/off
// - Show acquisition date in corner
// - Adjust opacity slider
// - Don't load by default (performance/bandwidth)
// - Respect tile quotas and caching terms

// Map layer: ndvi-overlay
// - Color-coded vegetation index
// - Legend showing NDVI scale
// - Date stamp
```

**Performance rules:**
- ❌ Don't auto-download satellite imagery on mobile data
- ✅ Let user explicitly request imagery load
- ✅ Show expected download size before loading
- ✅ Cache tiles per provider terms
- ✅ Bound the area loaded (viewport + small buffer only)

---

### Task 8.7 — Tests

```python
# tests/test_satellite.py
def test_scene_has_acquisition_date():      # Always present
def test_scene_has_resolution():            # Always present
def test_scene_has_cloud_cover():           # Always present
def test_scene_has_licence():               # Always present
def test_no_real_time_claim():              # No "live" label on delayed data
def test_processing_delay_shown():          # Honest about delay
def test_isro_preferred():                  # ISRO used when available
def test_fallback_labelled():               # Fallback source clearly marked
def test_resolution_not_overstated():       # 30m data not called "high-res"
def test_change_detection_two_dates():      # Both dates shown

# tests/test_environment.py
def test_ndvi_has_methodology():
def test_water_extent_has_date():
def test_change_has_comparison_dates():
def test_cloud_contamination_noted():

# tests/test_satellite_permissions.py
def test_imagery_licence_checked():         # No unlicensed imagery served
def test_attribution_present():             # Every scene has attribution
def test_redistribution_allowed():          # Only serve what we can redistribute
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] At least **one end-to-end satellite workflow** is permitted and licensed
- [ ] Scene dates, resolution, and cloud cover always shown
- [ ] Processing delay is honestly disclosed
- [ ] **No claim of real-time satellite video**
- [ ] ISRO/NRSC products used where accessible; fallback clearly labelled
- [ ] At least one environmental indicator (NDVI or water extent) working
- [ ] Historical imagery comparison shows both dates
- [ ] All satellite/environment tests pass
- [ ] Licence and attribution verified for every scene served

---

## 🤖 Agent Instructions

1. **Source verification is the majority of this phase's work.** Don't skip it.
2. Start with ONE satellite product end-to-end, not all at once.
3. If Bhuvan/ISRO access is restricted, document the limitation and use Sentinel as fallback.
4. Satellite imagery files can be huge — implement lazy loading and bandwidth controls.
5. Never call satellite imagery "real-time" or "live" — always show acquisition date.
6. Change detection needs TWO scenes — both dates must be shown.
7. Cloud cover matters — note it for every scene.

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Source register updated with all satellite sources (ISRO + fallback)
- [ ] At least one complete pipeline: acquire metadata → display scene → show derived indicator
- [ ] Phase 8 report: connected products, access status, licence terms, resolution capabilities

---

*Derived from: Development Plan §4 (Satellite), §6 (Stage 8), §7 (Version 2/3), §15 (Risks)*
