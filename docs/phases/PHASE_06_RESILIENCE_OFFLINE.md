# Phase 6 — Resilience & Offline

> **Duration:** 1–2 weeks  
> **Objective:** Implement robust caching, source diagnostics, saved places, report export, retry/backoff strategies, and PWA shell — so the app degrades gracefully under network failures and works offline for cached content.

---

## 🎯 Objective

Make the application resilient to provider outages, network failures, and offline use. Users can save places, view cached profiles, export reports, and understand exactly what is fresh, stale, or unavailable. The PWA shell caches itself for instant load.

---

## 📋 Prerequisites

- **Phase 5 COMPLETE** — health data integrated, safety tests passing
- Cache layer from Phase 3 exists (enhance it here)
- Profile panels and data adapters working

---

## 📝 Detailed Tasks

### Task 6.1 — Enhanced Cache with Staleness Tracking

**Action:** Upgrade the cache layer to support granular staleness per source.

```python
# services/api/src/garuda_api/cache/enhanced_cache.py

class EnhancedCache:
    """Provenance-aware cache with per-source TTL and staleness."""
    
    def get(self, key: str) -> CacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        entry.is_stale = entry.age_seconds > entry.ttl_seconds
        return entry  # Return stale data with stale flag
    
    def get_or_fetch(
        self, 
        key: str, 
        fetcher: Callable,
        ttl: int,
        stale_while_revalidate: bool = True,
    ) -> tuple[Any, CacheMetadata]:
        """
        1. If fresh cache exists → return it
        2. If stale cache exists AND fetcher succeeds → update cache, return fresh
        3. If stale cache exists AND fetcher fails → return stale with STALE badge
        4. If no cache AND fetcher fails → return UNAVAILABLE
        """
        ...

class CacheMetadata(BaseModel):
    hit: bool
    age_seconds: int
    is_stale: bool
    source_id: str
    cached_at: datetime
    ttl_seconds: int
```

**Source-specific TTLs:**

| Source Type | TTL | Stale Threshold |
|------------|-----|-----------------|
| Census data | 30 days | 90 days |
| Health bulletins | 1 hour | 24 hours |
| Alerts | 5 minutes | 30 minutes |
| Facility listings | 7 days | 30 days |
| Geocoder results | 24 hours | 7 days |
| Map tiles | Per provider terms | N/A |

---

### Task 6.2 — Source Diagnostics Dashboard

**Action:** Build a source health monitoring page.

```
apps/web/src/pages/SourceDiagnostics.tsx
```

**Display for each source:**

| Field | Example |
|-------|---------|
| Source name | "NCDC Weekly Bulletin" |
| Status | 🟢 Connected / 🟡 Stale / 🔴 Unavailable |
| Last successful fetch | "2026-10-19T14:30:00Z" |
| Last attempt | "2026-10-20T08:00:00Z" |
| Error (if any) | "Timeout after 5000ms" |
| Records served | 142 |
| Cache age | "6 hours old" |
| Next refresh | "In 18 hours" |

**Backend endpoint:** `GET /api/v1/sources/diagnostics`

```python
class SourceDiagnostic(BaseModel):
    source_id: str
    name: str
    status: str           # "connected" | "stale" | "unavailable" | "error"
    last_success: datetime | None
    last_attempt: datetime | None
    last_error: str | None
    records_cached: int
    cache_age_seconds: int | None
    next_refresh: datetime | None
    rate_limit_remaining: int | None
```

> [!NOTE]
> Source diagnostics must NEVER expose API keys, credentials, or internal infrastructure details.

---

### Task 6.3 — Retry, Backoff & Circuit Breaker

**Action:** Implement resilient HTTP client for all adapters.

```python
# services/api/src/garuda_api/http/resilient_client.py

class ResilientClient:
    """HTTP client with retry, backoff, rate-limit compliance, and circuit breaker."""
    
    def __init__(
        self,
        base_url: str,
        max_retries: int = 3,
        backoff_factor: float = 0.5,       # 0.5s, 1s, 2s
        timeout: float = 5.0,             # Bounded timeout
        max_response_size: int = 10_000_000,  # 10MB limit
        circuit_breaker_threshold: int = 5,   # Open after 5 consecutive failures
        circuit_breaker_reset: int = 60,      # Try again after 60s
    ):
        ...
    
    async def get(self, path: str, **kwargs) -> Response:
        """
        1. Check circuit breaker → if open, return cached/unavailable
        2. Make request with timeout
        3. If 429 → respect Retry-After header, backoff
        4. If 5xx → retry with exponential backoff
        5. If success → validate response size, reset circuit breaker
        6. Log failures WITHOUT secrets or personal data
        """
        ...
```

**Behaviors to test:**
- Timeout after N seconds → return cached or unavailable
- 429 with Retry-After → wait and retry
- 5xx → exponential backoff (max 3 retries)
- Circuit breaker opens after 5 consecutive failures
- Circuit breaker half-opens after 60 seconds
- Response size bounded (reject 100MB responses)

---

### Task 6.4 — Saved Places (Frontend)

**Action:** Allow users to bookmark places for quick access.

```typescript
// apps/web/src/stores/savedPlaces.ts
// Uses localStorage / IndexedDB

interface SavedPlace {
  placeId: string;
  canonicalName: string;
  displayName: string;  // Full hierarchy path
  placeType: string;
  coordinates: [number, number];
  savedAt: string;      // ISO 8601
  lastViewed: string;
  cachedProfile?: PlaceProfile;  // Optional cached data
}

// Features:
// - Save current place with one click
// - List saved places (sorted by last viewed)
// - Quick-navigate to saved place
// - Remove from saved
// - Cached profile available offline
```

**UI component:**

```
apps/web/src/components/SavedPlaces.tsx
├── SaveButton.tsx          # Heart/bookmark icon on profile
├── SavedPlacesList.tsx     # Sidebar/drawer with saved places
└── SavedPlaceCard.tsx      # Individual saved place entry
```

---

### Task 6.5 — Report Export (Enhanced)

**Action:** Enhance the export from Phase 3 with offline-capable reports.

**Export formats:**
1. **JSON** — complete profile with provenance metadata
2. **HTML** — self-contained single-page report (works offline)
3. **CSV** — observations table with source columns (for analysis tools)

**HTML report template:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Garuda Report — [Place Name]</title>
  <style>/* Embedded styles */</style>
</head>
<body>
  <header>
    <h1>[Place Name] — Place Profile Report</h1>
    <p>Generated: [date] | Source: Garuda (DEMO)</p>
    <p>⚠️ This is an informational report, not an official document.</p>
  </header>
  
  <!-- Panels with inline source citations -->
  <!-- Data gaps section -->
  <!-- Full attribution list -->
  <!-- Licence notices -->
</body>
</html>
```

**Rules:**
- Export must work **offline** (HTML is self-contained)
- Include ALL source attributions
- Include ALL data gaps
- Include "DEMO" watermark on demo builds
- Include generation timestamp

---

### Task 6.6 — PWA Service Worker

**Action:** Configure the service worker for offline shell and data caching.

```typescript
// apps/web/vite.config.ts — vite-plugin-pwa configuration

{
  registerType: 'prompt',  // Ask user before updating
  workbox: {
    // Cache app shell (HTML, CSS, JS, fonts)
    globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
    
    // Runtime caching strategies
    runtimeCaching: [
      {
        urlPattern: /^https:\/\/.*\.tile\..*/,  // Map tiles
        handler: 'CacheFirst',
        options: { 
          cacheName: 'map-tiles',
          expiration: { maxEntries: 1000, maxAgeSeconds: 86400 }
        }
      },
      {
        urlPattern: /\/api\/v1\//,  // API responses
        handler: 'NetworkFirst',
        options: { 
          cacheName: 'api-cache',
          networkTimeoutSeconds: 5,
        }
      }
    ]
  }
}
```

**Offline behavior:**
- ✅ App shell loads instantly (cached)
- ✅ Saved places with cached profiles viewable offline
- ✅ Exported reports work offline
- ✅ Map tiles cached for recently viewed areas
- ❌ **No implication that live alerts refresh without network**
- ❌ No countrywide map package (unrealistic for free)

**Offline indicator:**

```tsx
// apps/web/src/components/OfflineIndicator.tsx
// Shows a persistent banner when offline:
// "📡 You are offline. Showing cached data. Last synced: [time]"
// "⚠️ Health alerts may not be current. Connect to refresh."
```

---

### Task 6.7 — Provider Outage Handling

**Action:** Ensure each provider failure is isolated and doesn't cascade.

```python
# services/api/src/garuda_api/services/profile_service.py

class ProfileService:
    async def get_profile(self, place_id: str) -> PlaceProfile:
        """
        Fetch all domain panels concurrently.
        Individual failures are caught and reported per-panel.
        """
        results = await asyncio.gather(
            self._fetch_panel("population", place_id),
            self._fetch_panel("health", place_id),
            self._fetch_panel("services", place_id),
            self._fetch_panel("education", place_id),
            self._fetch_panel("history", place_id),
            return_exceptions=True,
        )
        
        panels = {}
        for domain, result in zip(DOMAINS, results):
            if isinstance(result, Exception):
                panels[domain] = PanelResponse(
                    domain=domain,
                    status=DataStatus.UNAVAILABLE,
                    observations=[],
                    sources=[],
                    error=f"Provider error: {type(result).__name__}",
                )
            else:
                panels[domain] = result
        
        return PlaceProfile(place=..., panels=panels)
```

---

### Task 6.8 — Tests

```python
# tests/test_resilience.py
def test_single_provider_outage():        # Other panels still load
def test_all_providers_down():            # Profile still renders (all unavailable)
def test_timeout_returns_cached():        # Stale cache served
def test_cache_age_visible():             # UI shows cache age
def test_circuit_breaker_opens():         # After N failures
def test_circuit_breaker_half_open():     # Retries after cooldown
def test_retry_backoff():                 # Exponential backoff works
def test_rate_limit_respected():          # 429 + Retry-After honoured
def test_response_size_bounded():         # Rejects huge responses

# tests/test_offline.py
def test_saved_place_available_offline():
def test_exported_report_self_contained():
def test_offline_banner_shown():
def test_no_live_alert_claim_offline():   # No implication of refresh
def test_pwa_shell_cached():
```

---

## 📂 Expected File Changes

```
MODIFIED: services/api/src/garuda_api/cache/cache_manager.py → enhanced_cache.py
NEW: services/api/src/garuda_api/http/resilient_client.py
NEW: services/api/src/garuda_api/routes/diagnostics.py
NEW: apps/web/src/pages/SourceDiagnostics.tsx
NEW: apps/web/src/components/SavedPlaces.tsx
NEW: apps/web/src/components/OfflineIndicator.tsx
NEW: apps/web/src/stores/savedPlaces.ts
MODIFIED: apps/web/vite.config.ts (PWA config)
MODIFIED: apps/web/src/components/profile/ExportButton.tsx
NEW: tests/test_resilience.py
NEW: tests/test_offline.py
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] Single provider outage doesn't break other panels
- [ ] All providers down → profile still renders with "unavailable" status
- [ ] Stale cache served with visible age when provider is unreachable
- [ ] Circuit breaker opens after repeated failures and resets
- [ ] Retry with backoff respects Retry-After headers
- [ ] Saved places work offline with cached profiles
- [ ] Exported HTML report is self-contained and works offline
- [ ] PWA shell caches and loads instantly
- [ ] Offline banner shown when disconnected
- [ ] **Offline mode does NOT imply live alerts are refreshing**
- [ ] Source diagnostics page shows all provider statuses
- [ ] All resilience tests pass

---

## 🤖 Agent Instructions

1. Enhance the existing cache, don't replace it entirely.
2. Test offline behavior by starting the app, then disabling the network.
3. The PWA service worker must NOT cache API responses indefinitely — use TTLs.
4. Saved places storage should use IndexedDB for larger cached profiles.
5. Export templates must include licence attributions for every data source.
6. The offline indicator must be honest: "Data may be stale" — not silent.
7. Do NOT background-download satellite data over mobile connections.

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Outage test suite passes (provider down, timeout, rate limit)
- [ ] Offline experience tested (save place, disconnect, view cached profile)
- [ ] Export reports validated as self-contained
- [ ] Phase 6 report documents: caching strategy, offline capabilities, known limitations

---

*Derived from: Development Plan §6 (Stage 6), §8 (Offline), §9 (Zero-cost), §14 (Production Readiness)*
