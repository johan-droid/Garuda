# Phase 2 — Map & Place Search

> **Duration:** 1–2 weeks  
> **Objective:** Implement interactive map browsing with MapLibre GL JS, place search via geocoder adapter, supported boundary rendering, coordinate selection, and name disambiguation.

---

## 🎯 Objective

A user can pan/zoom the map, search for a place by name/PIN/coordinates, click on any area (even unnamed), and see which administrative unit it belongs to. The system resolves the administrative hierarchy (state → district → block → village where supported) and shows uncertainty when exact resolution is impossible.

---

## 📋 Prerequisites

- **Phase 1 COMPLETE** — skeleton running, CI green
- **Phase 0 outputs:** verified geocoder, boundary source, tile provider documented
- Boundary fixture files available in `data/fixtures/`

---

## 📝 Detailed Tasks

### Task 2.1 — MapLibre GL JS Integration

**Action:** Replace the placeholder map with a fully functional MapLibre map.

**Requirements:**
- Center on pilot district (Odisha) with appropriate zoom level
- Use the tile provider verified in Phase 0
- Enable pan, zoom, pitch/tilt controls
- Add scale bar and attribution (as required by tile provider licence)
- Responsive layout — works on mobile and desktop viewports
- Touch-friendly controls for Android PWA

```tsx
// apps/web/src/components/MapView.tsx
// Configuration:
// - initialCenter: [pilot_district_lng, pilot_district_lat]
// - initialZoom: appropriate for district view
// - minZoom: 4 (India overview)
// - maxZoom: 18 (street level)
// - style: compliant tile URL from Phase 0
```

**Layer structure (add incrementally):**

| Layer ID | Type | Source | Purpose |
|----------|------|--------|---------|
| `boundaries-state` | line/fill | GeoJSON | State outlines |
| `boundaries-district` | line/fill | GeoJSON | District outlines |
| `boundaries-block` | line/fill | GeoJSON | Block/tehsil outlines |
| `boundaries-village` | line/fill | GeoJSON | Village outlines (where available) |
| `selected-place` | fill/highlight | Dynamic | Currently selected geography |

> [!NOTE]
> Boundary layers should load **only** at appropriate zoom levels to maintain performance. State boundaries at zoom < 8, district at zoom 8–10, block at 10–12, village at 12+.

---

### Task 2.2 — Geocoder Adapter (Backend)

**Action:** Implement the first source adapter — a geocoder that resolves place names to coordinates and admin hierarchy.

```
services/api/src/garuda_api/adapters/
├── base.py              # Abstract SourceAdapter class
├── geocoder/
│   ├── __init__.py
│   ├── nominatim.py     # Nominatim adapter (primary)
│   └── fallback.py      # Fallback strategy
```

**Adapter interface:**

```python
class GeocoderAdapter(SourceAdapter):
    """Resolves place names/coordinates to structured place results."""
    
    async def search(
        self, 
        query: str, 
        country_code: str = "in",
        limit: int = 10,
        viewbox: tuple | None = None,  # Bias toward pilot area
    ) -> list[PlaceSearchResult]:
        ...
    
    async def reverse(
        self,
        lat: float,
        lng: float,
    ) -> PlaceSearchResult | None:
        ...
```

**PlaceSearchResult model:**

```python
class PlaceSearchResult(BaseModel):
    place_id: str               # Internal stable ID
    source_place_id: str        # Geocoder's ID (for reference)
    canonical_name: str
    display_name: str           # Full path: "Village, Block, District, State"
    place_type: PlaceType
    coordinates: tuple[float, float]  # (lat, lng)
    bounding_box: tuple[float, float, float, float] | None
    admin_hierarchy: list[AdminLevel]
    geometry_available: bool
    resolution_confidence: str  # "exact" | "approximate" | "interpolated"
    source_id: str
```

**Mandatory behaviors:**
- ⏱️ Bounded timeout (e.g., 5 seconds)
- 🔄 Retry with exponential backoff
- 📊 Rate-limit compliance (Nominatim: 1 req/sec, User-Agent required)
- 📝 Log provider failures without secrets
- 🔄 Circuit breaker for repeated failures

---

### Task 2.3 — Search API Endpoint

**Action:** Implement `GET /api/v1/places/search?q=<query>`

**Request parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | Yes | Place name, PIN code, or coordinates |
| `limit` | int | No | Max results (default: 10, max: 50) |
| `type` | string | No | Filter: state, district, block, village |

**Response:**

```json
{
  "results": [
    {
      "place_id": "od-ganjam-001",
      "canonical_name": "Ganjam",
      "display_name": "Ganjam District, Odisha, India",
      "place_type": "district",
      "coordinates": [19.38, 84.88],
      "admin_hierarchy": [
        {"level": "state", "name": "Odisha", "id": "od"},
        {"level": "district", "name": "Ganjam", "id": "od-ganjam"}
      ],
      "geometry_available": true,
      "resolution_confidence": "exact"
    }
  ],
  "query": "Ganjam",
  "source": {
    "provider": "nominatim",
    "retrieved_at": "2026-10-20T10:00:00Z"
  },
  "disambiguation_note": null
}
```

**Disambiguation:**
- If multiple places share a name, return all matches ranked by relevance
- Include parent geography in `display_name` for disambiguation
- Add `disambiguation_note` when relevant (e.g., "Multiple villages named 'X' exist in Odisha")

---

### Task 2.4 — Search UI Component

**Action:** Build the search bar with autocomplete and disambiguation.

```
apps/web/src/components/
├── SearchBar.tsx          # Search input with debounce & autocomplete
├── SearchResults.tsx      # Dropdown with ranked results
├── PlaceCard.tsx          # Individual result with hierarchy display
└── DisambiguationNote.tsx # "Did you mean..." panel
```

**Search behavior:**
1. User types → debounce 300ms → call `/api/v1/places/search`
2. Show loading spinner during request
3. Display results with place type icon + admin hierarchy
4. On select: fly map to location, highlight boundary, open profile (Phase 3)
5. On error: show "Search temporarily unavailable" — NOT a blank result

**Coordinate input:**
- Accept `lat, lng` format (e.g., "19.38, 84.88")
- Accept DMS format (e.g., "19°22'48"N 84°52'48"E")
- Perform reverse geocode to find nearest admin unit

---

### Task 2.5 — Click-to-Identify Interaction

**Action:** Enable clicking anywhere on the map to identify the place.

**Behavior:**
1. User clicks on the map
2. If click hits a loaded boundary polygon → select that place
3. If click is on an area without loaded boundaries → reverse geocode the coordinates
4. If no admin unit found → show: "Coordinates: (lat, lng) · No administrative unit resolved"
5. Show the **full hierarchy** when overlapping boundaries exist

```tsx
// Map click handler
map.on('click', async (e) => {
  const { lng, lat } = e.lngLat;
  
  // 1. Check loaded boundary layers first (client-side)
  const features = map.queryRenderedFeatures(e.point, {
    layers: ['boundaries-village', 'boundaries-block', 'boundaries-district']
  });
  
  if (features.length > 0) {
    // Use the finest-grained boundary hit
    selectPlace(features[0].properties);
  } else {
    // 2. Reverse geocode via API
    const result = await reverseGeocode(lat, lng);
    if (result) {
      selectPlace(result);
    } else {
      showCoordinatesOnly(lat, lng);
    }
  }
});
```

> [!IMPORTANT]
> If no village boundary exists, do NOT invent one from a geocoder label. Show coordinates and nearest known admin unit.

---

### Task 2.6 — Boundary Rendering & Management

**Action:** Load and render verified boundary data on the map.

**Data flow:**
1. Backend serves boundaries from fixture/database via `GET /api/v1/boundaries/{level}?bbox=...`
2. Frontend requests boundaries appropriate for current zoom level
3. Render as transparent fill + colored outline
4. Selected boundary gets highlighted fill

**Performance rules:**
- Only request boundaries visible in current viewport (bbox filter)
- Use appropriate simplification for zoom level
- Set max feature count per request (e.g., 500)
- Progressive loading: state → district → block → village as zoom increases

**Boundary version tracking:**

```python
class BoundaryVersion(BaseModel):
    place_id: str
    geometry: dict  # GeoJSON geometry
    source: str
    version: str
    date: date
    crs: str  # e.g., "EPSG:4326"
    licence: str
    processing_notes: str | None = None
```

> [!WARNING]
> Do NOT use point-in-polygon results across different boundary versions without recording the version.

---

### Task 2.7 — Admin Hierarchy Resolution

**Action:** Implement the hierarchy resolver service.

```python
# services/api/src/garuda_api/services/hierarchy_service.py

class HierarchyService:
    """Resolves the full administrative hierarchy for a place."""
    
    async def resolve(self, place_id: str) -> AdminHierarchy:
        """
        Returns the chain: state → district → subdistrict → village
        with metadata about each level.
        """
        ...
    
    async def resolve_from_coordinates(
        self, lat: float, lng: float
    ) -> AdminHierarchy:
        """
        Point-in-polygon against loaded boundaries.
        Returns hierarchy with confidence level.
        """
        ...
```

**AdminHierarchy model:**

```python
class AdminLevel(BaseModel):
    level: str                    # "state" | "district" | "block" | "village"
    name: str
    place_id: str
    geometry_source: str | None   # Which boundary dataset
    boundary_version: str | None
    confidence: str               # "polygon_match" | "geocoder" | "approximate"

class AdminHierarchy(BaseModel):
    levels: list[AdminLevel]
    resolved_at: datetime
    finest_level: str
    notes: str | None = None      # e.g., "Village boundary unavailable"
```

---

### Task 2.8 — Tests

**Action:** Write comprehensive tests for this phase.

**Backend tests:**

```python
# tests/test_geocoder.py
def test_search_valid_place():          # Known pilot district
def test_search_empty_query():          # 400 error
def test_search_no_results():           # Empty results, not error
def test_search_disambiguation():       # Multiple matches
def test_search_timeout():              # Geocoder timeout → graceful error
def test_search_rate_limit():           # 429 → appropriate response
def test_reverse_geocode_in_boundary(): # Point inside known polygon
def test_reverse_geocode_outside():     # Point outside all boundaries
def test_search_coordinates():          # "19.38, 84.88" → reverse geocode

# tests/test_hierarchy.py
def test_hierarchy_from_village():      # Full chain
def test_hierarchy_from_district():     # Partial chain
def test_hierarchy_missing_village():   # Shows block, not fake village
def test_hierarchy_boundary_version():  # Version recorded
```

**Frontend tests:**

```typescript
// apps/web/src/__tests__/SearchBar.test.tsx
test('debounces search input by 300ms')
test('shows loading spinner during search')
test('displays disambiguation note for ambiguous results')
test('shows error message when search fails')
test('handles coordinate input format')

// apps/web/src/__tests__/MapView.test.tsx
test('renders map centered on pilot area')
test('shows boundaries at appropriate zoom levels')
test('click on boundary selects place')
test('click outside boundaries shows coordinates')
```

---

## 📂 Expected File Changes

```
MODIFIED: apps/web/src/components/MapView.tsx
NEW: apps/web/src/components/SearchBar.tsx
NEW: apps/web/src/components/SearchResults.tsx
NEW: apps/web/src/components/PlaceCard.tsx
NEW: apps/web/src/hooks/useSearch.ts
NEW: apps/web/src/hooks/useMap.ts

NEW: services/api/src/garuda_api/routes/places.py
NEW: services/api/src/garuda_api/adapters/geocoder/nominatim.py
NEW: services/api/src/garuda_api/adapters/geocoder/fallback.py
NEW: services/api/src/garuda_api/services/hierarchy_service.py
NEW: services/api/src/garuda_api/services/boundary_service.py

NEW: tests/test_geocoder.py
NEW: tests/test_hierarchy.py
NEW: apps/web/src/__tests__/SearchBar.test.tsx
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] Search by place name returns ranked results for the pilot area
- [ ] Search by PIN code returns correct location
- [ ] Search by coordinates (lat, lng) performs reverse geocode
- [ ] Ambiguous names show disambiguation with parent geography
- [ ] Click on boundary polygon selects that place and shows hierarchy
- [ ] Click on unnamed area shows coordinates + nearest admin unit
- [ ] Map loads boundary layers at appropriate zoom levels
- [ ] Geocoder timeout/failure shows graceful error, not crash
- [ ] Rate limits are respected (Nominatim: 1 req/sec with User-Agent)
- [ ] Boundary version is recorded for every point-in-polygon match
- [ ] **No invented village boundaries** when data doesn't exist
- [ ] All tests pass

---

## 🤖 Agent Instructions

1. Implement geocoder adapter FIRST, then wire up the frontend.
2. Use the geocoder source verified in Phase 0 — do not switch providers without documenting why.
3. The Nominatim adapter MUST include a proper User-Agent header and respect rate limits.
4. Do NOT cache geocoder results beyond what the provider's terms allow.
5. Test with real queries against the pilot area (document all test queries).
6. When boundary data is large, implement bbox filtering on the server side.
7. Never call a geocoder label "boundary data" — they are different things.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Nominatim rate limits slow down development | Self-host Nominatim for dev, or use careful request batching |
| Pilot area has sparse OSM coverage | Document gaps, show coordinates for unresolvable areas |
| Village-level boundaries missing | Show block-level boundaries, clearly label as "block level" |
| Large GeoJSON files slow the map | Simplify geometry per zoom level, use bbox queries |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Geocoder adapter tested with pilot area queries
- [ ] Search → select → map highlight works end-to-end
- [ ] Click anywhere on map resolves to finest available admin level
- [ ] No unresolvable errors remain in test suite
- [ ] Phase 2 report documents all geocoder queries tested and results

---

*Derived from: Development Plan §2 (Core Interactions), §6 (Stage 2), §12 (API Design), §13 (Geospatial Model)*
