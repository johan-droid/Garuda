# Phase 4 — Population, Services, Education & History/Culture

> **Duration:** 2–4 weeks  
> **Objective:** Integrate one verified dataset per data domain (population, public services, education, history/culture), normalizing IDs and boundary versions, with every value traced to its source.

---

## 🎯 Objective

Connect real, verified data sources to the profile panels built in Phase 3. Each domain is implemented as an independent **source adapter** that fetches, validates, normalizes, and stores observations with full provenance. Work one domain at a time — do NOT attempt all four simultaneously.

---

## 📋 Prerequisites

- **Phase 3 COMPLETE** — profile UI, provenance store, cache, source register all working
- **Phase 0 outputs:** verified sources for each domain with sample fixtures
- Source register populated with verified sources and their terms

---

## 📝 Detailed Tasks

### Task 4.1 — Adapter Architecture

**Action:** Establish the pattern that all domain adapters follow.

```python
# services/ingestion/src/adapters/base.py

class SourceAdapter(ABC):
    """Base class for all data source adapters."""
    
    source_id: str          # Unique ID in source register
    domain: str             # "population" | "health" | "services" | etc.
    publisher: str
    licence: str
    attribution: str
    
    @abstractmethod
    async def fetch(
        self, place_id: str, **kwargs
    ) -> list[Observation]:
        """Fetch observations for a place. Must handle:
        - Timeouts (bounded)
        - Rate limits (respect Retry-After)
        - Schema validation (reject malformed data)
        - Missing data (return empty list, not fake data)
        """
        ...
    
    @abstractmethod
    async def health_check(self) -> AdapterHealth:
        """Check if the source is reachable and responding."""
        ...
    
    def validate_observation(self, obs: Observation) -> bool:
        """Ensure all provenance fields are populated."""
        required = ['field_name', 'place_id', 'source_id', 
                     'retrieved_at', 'quality_status']
        return all(getattr(obs, f) is not None for f in required)
```

**Every adapter MUST:**
1. Validate response schema before accepting data
2. Record retrieval timestamp
3. Map source-specific place IDs to internal place IDs
4. Record which boundary version was used for mapping
5. Handle timeout, 429, 5xx gracefully
6. Return `[]` for missing data, not fabricated defaults

---

### Task 4.2 — Population Domain Adapter

**Action:** Connect the Census/population source verified in Phase 0.

**Adapter file:** `services/ingestion/src/adapters/population/census_india.py`

**Data to extract (minimum):**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `total_population` | int | Census 2011 | Show census year |
| `male_population` | int | Census 2011 | |
| `female_population` | int | Census 2011 | |
| `total_households` | int | Census 2011 | |
| `area_sq_km` | float | Census 2011 | If available |
| `density_per_sq_km` | float | Derived | Document calculation |
| `literacy_rate` | float | Census 2011 | |

**Critical rules:**
- ⚠️ Show census year prominently: "Population: 1,234,567 (Census 2011)"
- ❌ Never imply this is a live population count
- ❌ Never perform undisclosed interpolation/projection
- ✅ If a village figure is unavailable, show the block/district figure clearly labelled as such
- ✅ Record the geographic level: "This is district-level data"

**ID mapping:**
- Census uses its own location codes (e.g., state code + district code)
- Map these to internal `place_id` using a documented lookup table
- Store both IDs in the observation record

**Ingestion flow:**

```
Census CSV/API → validate schema → map place IDs → 
create Observation records → store in DB → update cache
```

---

### Task 4.3 — Population Panel UI

**Action:** Wire the population adapter to the `PopulationPanel` component.

```tsx
// apps/web/src/components/profile/PopulationPanel.tsx

// Display:
// - Total population with census year
// - Demographics breakdown (if available)
// - Density (with area source)
// - Literacy rate
// - Each value has an expandable SourceCard
// - "Census 2011" badge — NOT "Current Population"
// - Data gaps: "Village-level demographics not available"
```

---

### Task 4.4 — Public Services Domain Adapter

**Action:** Connect a verified facility/services source.

**Adapter file:** `services/ingestion/src/adapters/services/facilities.py`

**Data to extract (minimum):**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| Health centres | list | Facility registry | A listing ≠ operational proof |
| Schools | list | UDISE+ or equivalent | A listing ≠ quality indicator |
| Post offices | list | India Post data | If available |
| Water/sanitation | indicators | SBMG or equivalent | If available |

**Critical rules:**
- ⚠️ "A listing does not prove a service is operational today"
- Show the data source date for every facility
- If facility has coordinates, show on map; if not, list only
- Do NOT assume all listed facilities are currently functioning

---

### Task 4.5 — Services Panel UI

**Action:** Wire the services adapter to the `ServicesPanel` component.

```tsx
// Display:
// - Facility list grouped by type (health centres, schools, etc.)
// - Each facility: name, type, address (if available), source
// - Map pins for geolocated facilities (different icon per type)
// - Count summary: "3 health centres (source: [X], date: [Y])"
// - Disclaimer: "Listing does not confirm current operational status"
```

---

### Task 4.6 — Education Domain Adapter

**Action:** Connect a verified education source.

**Adapter file:** `services/ingestion/src/adapters/education/udise.py`

**Data to extract (minimum):**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| School count | int | UDISE+ | By type: primary, secondary |
| Enrollment | int | UDISE+ | If available |
| Student-teacher ratio | float | UDISE+ | If available |
| Schemes applicable | list | Ministry of Education | Policy, not implementation proof |

**Critical rules:**
- ⚠️ "A national policy is not proof of local implementation"
- Distinguish between policy existence and evidence of local delivery
- Show reference year for all statistics
- Do NOT interpolate or project education figures

---

### Task 4.7 — Education Panel UI

```tsx
// Display:
// - School statistics by level (primary, upper primary, secondary)
// - Key indicators with source year
// - Applicable government schemes (with caveat about local implementation)
// - Source cards for each data point
```

---

### Task 4.8 — History/Culture Domain Adapter

**Action:** Connect verified historical/cultural sources.

**Adapter file:** `services/ingestion/src/adapters/history/heritage.py`

**Data to extract (minimum):**

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| Historical context | text | ASI, district publications | Cite specific claims |
| Languages spoken | list | Census 2011 | |
| Heritage sites | list | ASI | If any in the area |
| Notable features | text | State publications | |

**Critical rules:**
- ⚠️ "Cite claims; avoid stereotypes"
- Every historical claim must have a specific citation
- Use community sources as leads, NOT as sole authority for high-impact facts
- Language data comes from Census (show reference year)

---

### Task 4.9 — History/Culture Panel UI

```tsx
// Display:
// - Historical narrative with inline citations
// - Languages spoken (with Census year)
// - Heritage sites (with ASI registration numbers if available)
// - "Sources" section listing all citations
// - Clearly labelled: "Historical information — see sources below"
```

---

### Task 4.10 — Place ID Normalization Service

**Action:** Build a service to map IDs across different data sources.

```python
# services/api/src/garuda_api/services/id_mapping.py

class PlaceIdMapper:
    """Maps between different source-specific place identifiers."""
    
    def map_census_code_to_place_id(
        self, state_code: str, district_code: str, 
        block_code: str | None = None, village_code: str | None = None
    ) -> str | None:
        ...
    
    def map_place_id_to_census_code(self, place_id: str) -> dict | None:
        ...
    
    def get_boundary_version(self, place_id: str) -> str | None:
        """Return which boundary version this ID was mapped against."""
        ...
```

> [!WARNING]
> Do NOT use point-in-polygon results across different boundary versions without recording the version.

---

### Task 4.11 — Ingestion Pipeline

**Action:** Build the batch ingestion pipeline for offline data loading.

```
services/ingestion/
├── src/
│   ├── pipeline.py        # Orchestrates all adapters
│   ├── adapters/
│   │   ├── population/census_india.py
│   │   ├── services/facilities.py
│   │   ├── education/udise.py
│   │   └── history/heritage.py
│   ├── transformers/
│   │   ├── id_mapper.py   # Place ID normalization
│   │   └── validator.py   # Schema + provenance validation
│   └── loaders/
│       └── db_loader.py   # Write validated observations to DB
├── scripts/
│   ├── ingest_population.py   # CLI script for population data
│   ├── ingest_services.py
│   └── ingest_education.py
└── tests/
    ├── test_census_adapter.py
    ├── test_facilities_adapter.py
    └── test_id_mapper.py
```

**IngestionRun record:**

```python
class IngestionRun(BaseModel):
    adapter_name: str
    adapter_version: str
    started_at: datetime
    completed_at: datetime | None
    records_fetched: int
    records_accepted: int
    records_rejected: int
    schema_version: str
    error_summary: str | None
```

---

### Task 4.12 — Tests

**Per-adapter tests (repeat for each domain):**

```python
# tests/test_census_adapter.py
def test_fetch_valid_district():           # Known pilot district
def test_fetch_missing_village():          # No village data → empty list
def test_no_zero_default():               # Missing ≠ 0
def test_source_fields_populated():       # All provenance fields present
def test_id_mapping():                    # Census code → internal ID
def test_boundary_version_recorded():     # Version tracking
def test_timeout_handling():              # Bounded timeout
def test_malformed_response():            # Schema validation catches bad data
def test_stale_detection():               # Old data marked stale

# tests/test_id_mapper.py
def test_census_code_roundtrip():
def test_cross_version_warning():         # Different boundary versions flagged
```

**Integration tests:**

```python
# tests/test_profile_integration.py
def test_profile_with_population_data():
def test_profile_population_unavailable():
def test_profile_partial_domains():        # Population OK, services unavailable
def test_district_data_not_labelled_village():
```

---

## 📂 Expected File Changes

```
NEW: services/ingestion/src/adapters/population/census_india.py
NEW: services/ingestion/src/adapters/services/facilities.py
NEW: services/ingestion/src/adapters/education/udise.py
NEW: services/ingestion/src/adapters/history/heritage.py
NEW: services/ingestion/src/pipeline.py
NEW: services/ingestion/scripts/ingest_*.py
NEW: services/api/src/garuda_api/services/id_mapping.py
MODIFIED: apps/web/src/components/profile/PopulationPanel.tsx
MODIFIED: apps/web/src/components/profile/ServicesPanel.tsx
MODIFIED: apps/web/src/components/profile/EducationPanel.tsx
MODIFIED: apps/web/src/components/profile/HistoryPanel.tsx
NEW: data/fixtures/census-sample.json (if not already from Phase 0)
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] At least **one verified dataset per domain** is connected and serving data
- [ ] Pilot area values are **traced to sources** — every observation has full provenance
- [ ] **Licence and attribution** are visible for every data source
- [ ] Census data shows reference year (e.g., "Census 2011") — NOT "current"
- [ ] Missing village data shows district/block data **labelled as such**
- [ ] Facility listings include disclaimer about operational status
- [ ] Education schemes distinguish policy from local implementation evidence
- [ ] History/culture claims have specific citations
- [ ] **No fabricated defaults** (zero, blank, or invented values)
- [ ] ID mapping records boundary version used
- [ ] Ingestion pipeline logs accepted/rejected counts
- [ ] All adapter tests pass (valid, missing, malformed, timeout, stale)

---

## 🤖 Agent Instructions

1. **Implement ONE domain at a time.** Complete population adapter + tests before starting services.
2. Use the exact sources verified in Phase 0. If a source changed, re-verify and update the source register.
3. For Census data in CSV format, write a proper parser — don't hack it.
4. Every fixture must have a retrieval date and licence note.
5. When Census data is at district level but the user clicked a village, show the data with "District-level" badge.
6. Do NOT import large datasets wholesale — use the pilot district subset only.
7. Report which sources you actually connected vs. which remain as placeholders.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Census data only available as PDF tables | Write manual parser; document the transformation |
| Facility registry API is unreliable | Use downloaded snapshot with date; mark as "last checked" |
| Place ID mapping has gaps | Document unmapped codes; show "ID not resolved" |
| Historical claims are contested | Show all cited sources; don't pick one narrative |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Each adapter has its own test suite (5+ tests minimum)
- [ ] Source register updated with all connected sources
- [ ] Ingestion scripts documented in `docs/SETUP.md`
- [ ] Phase 4 report lists: connected sources, data coverage, known gaps

---

*Derived from: Development Plan §2 (Place Profile Panels), §4 (Data Sources), §5 (Anti-hallucination), §6 (Stage 4)*
