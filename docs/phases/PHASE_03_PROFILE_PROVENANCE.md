# Phase 3 — Place Profile & Provenance Engine

> **Duration:** 1 week  
> **Objective:** Build the place profile UI with source cards, timestamps, missing-data states, provenance tracking, cache layer, and report export — so every factual field traces to a validated source.

---

## 🎯 Objective

When a user selects a place (via search or click), the app displays a **multi-panel profile** where each data card shows its source, period, geographic level, last update, and limitations. This phase builds the profile infrastructure; actual data domains are connected in Phases 4 and 5.

---

## 📋 Prerequisites

- **Phase 2 COMPLETE** — map + search + click-to-identify working
- Shared contract types defined (Place, Source, Observation, DataStatus)

---

## 📝 Detailed Tasks

### Task 3.1 — Profile API Endpoint

**Action:** Implement `GET /api/v1/places/{id}/profile`

**Design principle:** Each panel is independently loaded. One provider failure must NOT break the whole profile.

```python
# Response structure
class PlaceProfile(BaseModel):
    place: Place
    hierarchy: AdminHierarchy
    panels: dict[str, PanelResponse]  # keyed by domain
    retrieved_at: datetime

class PanelResponse(BaseModel):
    domain: str                    # "population", "health", "services", etc.
    status: DataStatus             # current | stale | unavailable | etc.
    observations: list[Observation]
    sources: list[SourceSummary]
    last_updated: datetime | None
    coverage_note: str | None      # e.g., "District-level only"
    data_gaps: list[str]           # Explicit list of missing fields
    error: str | None              # If provider failed

class SourceSummary(BaseModel):
    source_id: str
    publisher: str
    name: str
    url: str | None
    licence: str | None
    reference_period: str | None   # "Census 2011" or "2026-W42"
    retrieved_at: datetime
    verification_status: str
```

**Behavior:**
- Request all domain adapters concurrently
- Each adapter returns independently (partial success is OK)
- If a domain adapter fails: `status: "unavailable"`, `error: "Provider timeout"`
- If a domain has no data for this place: `status: "unavailable"`, `data_gaps: ["No village-level population data"]`
- **Never return zero** when the real answer is "unavailable"

---

### Task 3.2 — Provenance / Observation Store

**Action:** Implement the canonical observation record storage.

**For each fact, store:**

| Field | Purpose |
|-------|---------|
| `field_name` | What is being measured (e.g., "total_population") |
| `value` | The actual value |
| `unit` | Unit of measurement (e.g., "persons", "per 1000") |
| `place_id` | Which place this applies to |
| `geometry_id` | Which boundary version was used |
| `source_id` | FK to source register |
| `source_url` | Original URL |
| `publisher` | Who published this |
| `source_record_id` | ID in the upstream system |
| `reference_period_start` | Start of observation period |
| `reference_period_end` | End of observation period |
| `published_at` | When the source published it |
| `retrieved_at` | When we fetched it |
| `valid_until` | Expiry (for alerts/forecasts) |
| `licence` | Under what terms |
| `transformation_version` | Our adapter version |
| `quality_status` | current / stale / unavailable / conflicting |
| `notes` | Free text |

**Storage:** SQLite for now (local-first), with migration path to PostgreSQL.

```python
# services/api/src/garuda_api/db/models.py
class ObservationRecord(Base):
    __tablename__ = "observations"
    
    id = Column(Integer, primary_key=True)
    field_name = Column(String, nullable=False)
    value = Column(String)  # Store as string, parse by type
    unit = Column(String)
    place_id = Column(String, nullable=False, index=True)
    source_id = Column(String, nullable=False)
    source_url = Column(String)
    publisher = Column(String)
    reference_period_start = Column(Date)
    reference_period_end = Column(Date)
    published_at = Column(DateTime(timezone=True))
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    quality_status = Column(String, nullable=False)  # DataStatus enum
    notes = Column(Text)
```

---

### Task 3.3 — Data Status Display States

**Action:** Implement all 7 required display states in the UI.

| Status | UI Treatment | Color | Icon |
|--------|-------------|-------|------|
| **Current** | Show value + source date + valid period | Green | ✅ |
| **Historical** | Show value + past period label: "Census 2011" | Blue | 📅 |
| **Stale** | Show value + prominent "STALE" badge + last known date | Amber | ⚠️ |
| **Unavailable** | "No data available" — NOT zero, NOT blank | Gray | ❌ |
| **Conflicting** | Show all source values side by side with definitions | Orange | ⚡ |
| **Approximate** | Show value + "District-level" / "Estimated" label | Yellow | 📍 |
| **Unverified** | Show value + "Community report — UNVERIFIED" | Red border | 🔍 |

```tsx
// apps/web/src/components/DataStatusBadge.tsx
interface DataStatusBadgeProps {
  status: DataStatus;
  label?: string;   // e.g., "Census 2011"
  staleAge?: string; // e.g., "Last updated 45 days ago"
}
```

> [!CAUTION]
> **NEVER** display "0" or an empty cell when the real status is "unavailable". This is a non-negotiable safety rule for health data.

---

### Task 3.4 — Profile Panel UI Components

**Action:** Build the multi-panel profile view.

```
apps/web/src/components/profile/
├── ProfileView.tsx         # Main profile container (sidebar or modal)
├── ProfilePanel.tsx        # Generic panel wrapper (loading/error/data states)
├── OverviewPanel.tsx       # Place name, hierarchy, coordinates, map context
├── PopulationPanel.tsx     # Population data (placeholder, connected Phase 4)
├── HealthPanel.tsx         # Health data (placeholder, connected Phase 5)
├── ServicesPanel.tsx       # Facilities (placeholder, connected Phase 4)
├── EducationPanel.tsx      # Education indicators (placeholder, connected Phase 4)
├── HistoryPanel.tsx        # Historical/cultural (placeholder, connected Phase 4)
├── SourcesPanel.tsx        # Source register, freshness, gaps
├── ObservationCard.tsx     # Single fact with full provenance
└── SourceCard.tsx          # Source metadata card
```

**ProfilePanel behavior:**
1. **Loading:** Show skeleton/shimmer
2. **Success:** Show observations with provenance
3. **Partial:** Show available data + error notice for failed domains
4. **Unavailable:** Show "No [domain] data available for [place name]"
5. **Error:** Show "Failed to load — Retry" button

**OverviewPanel (always populated from Phase 2 data):**
- Place name + aliases
- Admin hierarchy breadcrumb: State > District > Block > Village
- Coordinates (lat, lng)
- Boundary source + vintage
- Map context thumbnail

---

### Task 3.5 — Source Card Component

**Action:** Every data card must include expandable source metadata.

```tsx
// apps/web/src/components/profile/SourceCard.tsx
<SourceCard
  publisher="Census of India"
  sourceName="Primary Census Abstract 2011"
  sourceUrl="https://censusindia.gov.in/..."
  referenceperiod="2011"
  retrievedAt="2026-10-15T08:30:00Z"
  licence="Government Open Data Licence - India"
  verificationStatus="VERIFIED"
  geographicLevel="district"
  limitations="Village-level data not available for all indicators"
/>
```

**Mandatory source card fields:**
- ✅ Publisher name
- ✅ Source name + URL (clickable)
- ✅ Reference period (NOT "current" unless it genuinely is)
- ✅ Retrieved date
- ✅ Licence
- ✅ Geographic level this data applies to
- ✅ Verification status badge

---

### Task 3.6 — Cache Layer

**Action:** Implement a provenance-aware cache.

```python
# services/api/src/garuda_api/cache/
├── __init__.py
├── cache_manager.py      # TTL-based cache with staleness tracking
└── cache_models.py       # CacheEntry with age/stale metadata
```

**Cache rules:**
- Each cached response includes `cached_at` timestamp
- Stale cache entries are served with `STALE` status badge
- Cache TTL is source-specific (Census data: long; alerts: short)
- Cache entries store the full provenance chain
- **Cache age is always visible** to the user

```python
class CacheEntry(BaseModel):
    key: str
    data: dict
    cached_at: datetime
    ttl_seconds: int
    source_id: str
    is_stale: bool = False
    
    @property
    def age_seconds(self) -> int:
        return (datetime.now(UTC) - self.cached_at).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        return self.age_seconds > self.ttl_seconds
```

---

### Task 3.7 — Report Export

**Action:** Allow users to download a place profile as a portable report.

**Export formats:**
- **JSON** — machine-readable profile with full provenance
- **PDF** (stretch goal) — formatted report with attribution

**Export must include:**
- Place name + hierarchy
- All observations with source citations
- Data gaps listed explicitly
- "Generated on [date] from Garuda (DEMO)" watermark
- Attribution for all sources used
- Disclaimer: "This is an informational report, not an official document"

```
apps/web/src/components/profile/
└── ExportButton.tsx       # Download profile as JSON/PDF
```

---

### Task 3.8 — Observations API Endpoint

**Action:** Implement `GET /api/v1/places/{id}/observations?domain=<domain>`

**Request parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `domain` | string | No | Filter by domain: population, health, etc. |
| `period_start` | date | No | Filter observations by period |
| `period_end` | date | No | Filter observations by period |
| `include_stale` | bool | No | Include stale cached values (default: true) |

**Response:** List of `Observation` objects with full provenance.

---

### Task 3.9 — Source Register API

**Action:** Implement `GET /api/v1/sources`

**Response:** List of all registered sources with their current status.

```json
{
  "sources": [
    {
      "id": "census-india-2011",
      "publisher": "Office of the Registrar General",
      "name": "Census of India 2011",
      "url": "https://censusindia.gov.in/",
      "licence": "Government Open Data Licence - India",
      "access_mode": "download",
      "verification_status": "VERIFIED",
      "last_success": "2026-10-15T08:30:00Z",
      "domains": ["population"],
      "geographic_coverage": ["district", "block"],
      "known_limits": "Village-level data incomplete"
    }
  ]
}
```

> [!NOTE]
> The source register must NEVER expose secrets, API keys, or internal credentials.

---

### Task 3.10 — Tests

**Backend tests:**

```python
# tests/test_profile.py
def test_profile_returns_all_panels():
def test_profile_partial_failure():       # One domain fails, others OK
def test_profile_all_unavailable():       # All domains fail → still returns
def test_profile_no_zero_defaults():      # Unavailable ≠ zero
def test_profile_stale_data_labelled():   # Stale is marked stale

# tests/test_observations.py
def test_observation_has_provenance():    # All required fields present
def test_observation_domain_filter():
def test_observation_period_filter():

# tests/test_cache.py
def test_cache_stores_provenance():
def test_cache_stale_detection():
def test_cache_expiry():

# tests/test_sources.py
def test_source_register_no_secrets():    # No API keys in response
def test_source_register_status():
```

**Frontend tests:**

```typescript
// apps/web/src/__tests__/ProfileView.test.tsx
test('shows loading skeleton while fetching')
test('renders all panels for a place')
test('shows unavailable state, not zero, for missing data')
test('shows stale badge on stale data')
test('shows conflicting values side by side')
test('source card shows all required fields')
test('export button generates JSON with provenance')
```

---

## 📂 Expected File Changes

```
NEW: services/api/src/garuda_api/routes/profile.py
NEW: services/api/src/garuda_api/routes/observations.py
NEW: services/api/src/garuda_api/routes/sources.py
NEW: services/api/src/garuda_api/db/models.py
NEW: services/api/src/garuda_api/db/migrations/
NEW: services/api/src/garuda_api/cache/cache_manager.py
NEW: apps/web/src/components/profile/ (all panel components)
NEW: apps/web/src/components/DataStatusBadge.tsx
NEW: tests/test_profile.py
NEW: tests/test_observations.py
NEW: tests/test_cache.py
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] Selecting a place shows a multi-panel profile view
- [ ] Each panel loads independently (partial success works)
- [ ] Every displayed fact shows source, period, geographic level, and retrieval date
- [ ] "Unavailable" status is shown — **never zero or blank**
- [ ] Stale data displays a prominent "STALE" badge with last known date
- [ ] Source register endpoint returns metadata without secrets
- [ ] Cache layer tracks staleness and provenance
- [ ] Report export includes full attribution and provenance
- [ ] Historical data is NOT labelled "current" or "live"
- [ ] District-level data is labelled as "district-level" even on a village page
- [ ] All tests pass

---

## 🤖 Agent Instructions

1. Build the profile infrastructure FIRST (backend), then wire up the UI.
2. Use placeholder panels for domains not yet connected (Population, Health, etc.).
3. Placeholder panels should show "Data source not yet connected — Phase 4/5" — not fake data.
4. Every observation must have ALL provenance fields populated.
5. Test the "unavailable" state thoroughly — it's a safety-critical feature for health data.
6. Cache layer must record `cached_at` — don't use opaque caching.
7. Source register endpoint is public-facing — triple-check no secrets leak.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Profile API too slow with concurrent adapter calls | Set per-adapter timeouts; return partial results |
| Zero/null confusion in observation values | Enforce at schema level: `null` means unavailable, `0` must be a real observed zero |
| Source card clutters the UI | Make source info expandable/collapsible, not always visible |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] No fabricated data defaults anywhere in the profile
- [ ] Profile works with zero connected data sources (all panels show "unavailable")
- [ ] Source register is complete and honest
- [ ] Phase 3 report documents the profile architecture and known data gaps

---

*Derived from: Development Plan §2 (Place Profile Panels), §5 (Anti-hallucination), §6 (Stage 3), §12 (API Design), §13 (Data Model)*
