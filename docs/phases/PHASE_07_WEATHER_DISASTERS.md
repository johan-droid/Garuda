# Phase 7 — Weather & Disasters (Version 2)

> **Duration:** 2–4 weeks  
> **Objective:** Verify and integrate IMD weather products and NDMA/NDRF disaster alerts with proper validity windows, forecast vs. observation labels, issuer attribution, and fallback strategies.

---

## 🎯 Objective

Add weather observations/forecasts and official disaster alerts to the platform. These domains require careful temporal handling — forecasts expire, alerts have validity windows, and observations must not be confused with predictions. This is a **Version 2** feature.

---

## 📋 Prerequisites

- **Phase 6 COMPLETE** — resilience, caching, offline all working
- Fresh source verification for weather/disaster providers (may differ from Phase 0)
- Understanding of temporal data: observation vs. forecast vs. alert

---

## 📝 Detailed Tasks

### Task 7.1 — IMD Source Verification

**Action:** Verify access to India Meteorological Department products.

**Products to evaluate:**

| Product | Type | Check |
|---------|------|-------|
| Current weather observations | Observation | API/feed availability, terms, attribution |
| Weather forecasts (1-5 day) | Forecast | Model source, coverage, update frequency |
| Rainfall data | Observation | Station vs. gridded, resolution, lag |
| Cyclone warnings | Alert | Feed format, validity handling, geometry |
| Heat/cold wave alerts | Alert | Feed format, issuer, valid-from/valid-until |

**For each product:**
- Verify API/download access and terms
- Confirm rate limits and quotas
- Document attribution requirements
- Test with a sample request for the pilot area
- Record update frequency and data lag
- Note: forecast vs. observation distinction

**Fallback sources to evaluate (if IMD is unavailable):**
- Open-Meteo (open-source weather API)
- NOAA/NASA public weather data
- Other documented open weather feeds

> [!WARNING]
> Fallback only for comparable metrics and periods. Don't mix IMD observations with a different model's forecasts without clear labelling.

**Output:** `docs/source-register/weather-sources.md`

---

### Task 7.2 — NDMA/Disaster Source Verification

**Action:** Verify access to disaster alert feeds.

**Sources to evaluate:**

| Source | Type | Check |
|--------|------|-------|
| NDMA (National Disaster Management Authority) | Alerts | Feed/API, format, terms |
| NDRF (National Disaster Response Force) | Reports | Access, format |
| State disaster authority (Odisha) | Alerts | OSDMA access, format |
| IMD severe weather warnings | Alerts | Part of IMD products |
| CWC (Central Water Commission) flood data | Observations | Access, format |

**Output:** `docs/source-register/disaster-sources.md`

---

### Task 7.3 — Weather Adapter

**Action:** Build weather source adapter(s).

```
services/ingestion/src/adapters/weather/
├── __init__.py
├── base_weather.py      # Weather-specific adapter base
├── imd_adapter.py       # India Meteorological Department
└── fallback_weather.py  # Open-Meteo or equivalent fallback
```

**Weather observation model:**

```python
class WeatherObservation(Observation):
    """Extended observation for weather data."""
    observation_type: str    # "observation" | "forecast" | "nowcast"
    station_id: str | None   # Weather station identifier
    station_name: str | None
    station_distance_km: float | None  # Distance from queried place
    model_name: str | None   # For forecasts: which model
    forecast_hour: int | None # Hours ahead (for forecasts)
    valid_at: datetime        # When this value applies
    
    # Specific weather fields
    temperature_c: float | None
    humidity_pct: float | None
    rainfall_mm: float | None
    wind_speed_kmh: float | None
    wind_direction: str | None
    conditions: str | None    # "Partly Cloudy", "Rain", etc.
    
    # Coverage metadata
    spatial_resolution: str | None  # "station" | "0.25deg grid" | etc.
    temporal_resolution: str | None # "hourly" | "daily" | "3-hourly"
```

**Critical rules:**
- ✅ Label "forecast" vs. "observation" prominently
- ✅ Show weather station name and distance from queried location
- ✅ Show model name for forecast data
- ❌ Don't present grid-model data as station observation
- ❌ Don't label forecast as "current weather"

---

### Task 7.4 — Disaster Alert Adapter

**Action:** Build disaster alert adapter(s).

```python
class DisasterAlert(Alert):
    """Extended alert for disaster warnings."""
    disaster_type: str         # "cyclone" | "flood" | "earthquake" | "heat_wave" | etc.
    issuing_authority: str     # "IMD" | "NDMA" | "OSDMA"
    issue_time: datetime       # When authority issued the warning
    valid_from: datetime
    valid_until: datetime      # CRITICAL: alerts expire
    severity_source: str       # Severity as defined BY the source
    affected_area_description: str
    affected_geometry: dict | None  # GeoJSON if available
    instructions: str | None   # Official instructions (not invented)
    superseded_by: str | None  # ID of newer alert that replaces this
```

**Alert lifecycle:**

```
ISSUED → ACTIVE → UPDATED/SUPERSEDED → EXPIRED
```

**Display rules:**
- ✅ Active alerts shown prominently with countdown to expiry
- ✅ Expired alerts show "EXPIRED" badge and are de-emphasized
- ✅ Superseded alerts linked to the replacing alert
- ✅ Issuer and issue time always visible
- ❌ Never fake live labels — if the feed is stale, say so
- ❌ Never create alerts from non-authoritative sources

---

### Task 7.5 — Weather Panel UI

```
apps/web/src/components/profile/weather/
├── WeatherPanel.tsx           # Main weather panel
├── CurrentConditions.tsx      # Latest observation
├── ForecastSection.tsx        # Multi-day forecast
├── RainfallChart.tsx          # Rainfall time series (ECharts)
├── WeatherStationNote.tsx     # Station name + distance
├── ForecastDisclaimer.tsx     # "This is a forecast, not observation"
└── WeatherSourceCard.tsx      # Source + model attribution
```

**Weather panel layout:**

```
┌─────────────────────────────────────────┐
│ ☀️ Weather — [Place Name]               │
├─────────────────────────────────────────┤
│ 📍 Nearest station: [Name] (12 km)     │
│ 🕐 Observed at: 2026-10-20 14:30 IST   │
│                                         │
│ 🌡️ Temperature: 32°C                    │
│ 💧 Humidity: 78%                        │
│ 🌧️ Rainfall (24h): 12mm                │
│ 💨 Wind: 15 km/h NW                    │
│                                         │
│ Source: IMD | Retrieved: [timestamp]    │
├─────────────────────────────────────────┤
│ 📅 FORECAST (3-day)                     │
│ ⚠️ Forecast — not observation           │
│ Model: [name] | Issued: [date/time]    │
│                                         │
│ Tomorrow: 30°C / 24°C, Light Rain     │
│ Day 2:    31°C / 25°C, Partly Cloudy  │
│ Day 3:    29°C / 23°C, Heavy Rain ⚠️  │
├─────────────────────────────────────────┤
│ 📊 RAINFALL HISTORY                     │
│ [ECharts time-series chart]             │
│ Only when dated observations exist.     │
└─────────────────────────────────────────┘
```

---

### Task 7.6 — Disaster Alert Map Layer

**Action:** Add disaster alerts as a map overlay.

```typescript
// Map layers for active disaster alerts
// - Color-coded by severity (source-defined severity)
// - Polygon/circle showing affected area
// - Click → alert card with details
// - Auto-removed when expired (with configurable delay)
// - Stale feed indicator if source is unresponsive
```

**Alert card on map click:**
```
┌─────────────────────────────────────┐
│ ⚠️ CYCLONE WARNING                  │
│ Issued by: IMD                      │
│ Issued: 2026-10-20 06:00 IST       │
│ Valid until: 2026-10-22 18:00 IST   │
│ Status: ACTIVE (expires in 2d 4h)  │
│ Severity: Orange (IMD definition)   │
│ Area: Coastal Odisha               │
│                                     │
│ Instructions: [official text]       │
│ Source: [URL to original]           │
└─────────────────────────────────────┘
```

---

### Task 7.7 — Forecast Chart Component

**Action:** Build time-series chart for weather data using Apache ECharts.

**Rules for charting:**
- ✅ Only chart when dated observations exist
- ✅ Show clear demarcation between observation and forecast data
- ✅ X-axis: dates with timezone
- ✅ Y-axis: units labelled
- ✅ Hover tooltip shows source + timestamp
- ❌ Don't chart made-up data to fill gaps
- ❌ Don't extrapolate beyond available data

---

### Task 7.8 — Tests

```python
# tests/test_weather.py
def test_weather_observation_vs_forecast():  # Correctly classified
def test_weather_station_distance():         # Shown to user
def test_weather_model_attribution():        # Forecast model named
def test_weather_stale_data():               # Old weather marked stale
def test_weather_unavailable():              # No fake weather

# tests/test_disaster_alerts.py
def test_alert_has_expiry():                 # valid_until is set
def test_alert_expires_correctly():          # Status changes to EXPIRED
def test_alert_superseded():                 # Old alert linked to new
def test_alert_issuer_shown():               # Authority always visible
def test_alert_no_fake_live():               # Stale feed → honest label
def test_no_unauthorized_alert():            # Only from verified authorities
def test_alert_validity_window():            # Shows countdown

# tests/test_weather_resilience.py
def test_weather_provider_timeout():
def test_weather_fallback_labelled():        # Fallback source clearly marked
def test_no_incompatible_fallback():         # Different model ≠ silent substitute
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] Weather data displays with "observation" vs. "forecast" labels
- [ ] Weather station name and distance shown
- [ ] Forecast model is attributed
- [ ] Disaster alerts have issuer, issue time, and validity period
- [ ] **Alerts expire correctly** and show EXPIRED badge after `valid_until`
- [ ] Stale weather feed shows honest stale indicator
- [ ] **No fake live labels** on delayed or cached data
- [ ] Forecast chart separates observation from prediction
- [ ] Fallback weather source clearly labelled when used
- [ ] All weather/disaster tests pass

---

## 🤖 Agent Instructions

1. **Verify sources FIRST** — create `docs/source-register/weather-sources.md` before coding.
2. Weather data is time-sensitive — use timezone-aware timestamps everywhere.
3. The IMD adapter may need to handle non-standard data formats — document what you find.
4. If IMD is unavailable, use Open-Meteo as documented fallback (not silent substitute).
5. Disaster alerts must EXPIRE. Test this explicitly.
6. Forecast charts must clearly mark where observation ends and forecast begins.

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Weather + disaster sources documented in source register
- [ ] Alerts expire correctly in automated tests
- [ ] Forecast vs. observation clearly distinguished in UI
- [ ] Phase 7 report documents: connected weather sources, alert lifecycle, fallback strategy

---

*Derived from: Development Plan §4 (Weather/Disasters), §6 (Stage 7), §7 (Version 2)*
