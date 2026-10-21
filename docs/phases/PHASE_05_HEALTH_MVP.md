# Phase 5 — Health MVP

> **Duration:** 2–4 weeks  
> **Objective:** Integrate official health bulletins/indicators, implement historical vs. current distinction, facility display, authority-linked prevention guidance — with robust handling of stale, unavailable, and conflicting health data.

---

## 🎯 Objective

Health is the **priority domain**. This phase builds the most safety-critical feature of the platform: displaying public health information with extreme care for accuracy, timeliness, and appropriate labelling. An outbreak card requires a **dated statement from a competent public-health authority** — no exceptions.

---

## 📋 Prerequisites

- **Phase 4 COMPLETE** — at least population adapter working with provenance
- **Phase 0 outputs:** health sources verified (or documented as unavailable)
- Profile panel infrastructure from Phase 3 ready
- Understanding of the health safety rules from the plan document (§5)

---

## 📝 Detailed Tasks

### Task 5.1 — Health Data Classification Framework

**Action:** Before writing any code, define the strict classification of health information.

Every health data point must be classified into exactly **one** of these categories:

| Category | Definition | Display Rules |
|----------|-----------|---------------|
| **Official Alert** | Dated statement/dataset from a competent public-health authority | Show issuer, issue date, valid period, affected geography, status |
| **Historical Cases** | Past counts/statistics from official records | Label with period: "Jan–Mar 2024"; NEVER dress up as "current" |
| **Routine Surveillance** | Ongoing monitoring data (e.g., IDSP weekly reports) | Show reporting week, geographic level, data lag |
| **Forecast/Modelled Risk** | Predictions or model outputs | Label as "projected/estimated"; show methodology source |
| **General Prevention** | Authoritative health guidance | Link to WHO/MoHFW/NCDC; show guidance date |
| **Community Report** | Unverified public reports (future) | "UNVERIFIED" badge; never auto-convert to official alert |

> [!CAUTION]
> These categories must NEVER be mixed or blurred. A historical case count cannot be presented as a current alert. A model prediction cannot be presented as confirmed cases.

---

### Task 5.2 — Health Data Adapter

**Action:** Implement health domain adapters based on Phase 0 findings.

```
services/ingestion/src/adapters/health/
├── __init__.py
├── base_health.py        # Health-specific adapter base class
├── ncdc_bulletin.py      # NCDC weekly disease outbreak reports
├── mohfw_indicators.py   # Ministry of Health indicators
├── state_health.py       # Odisha state health department data
└── manual_ingestion.py   # For PDF bulletins that need manual processing
```

**Health adapter base class (stricter than generic adapter):**

```python
class HealthAdapter(SourceAdapter):
    """Base for health domain adapters. Enforces safety rules."""
    
    domain = "health"
    
    async def fetch(self, place_id: str, **kwargs) -> list[HealthObservation]:
        raw = await self._fetch_raw(place_id)
        validated = [self._validate_health_obs(r) for r in raw]
        return [v for v in validated if v is not None]
    
    def _validate_health_obs(self, obs: dict) -> HealthObservation | None:
        """Enforce health-specific validation rules."""
        # MUST have: source authority, date, geographic level
        # MUST classify: alert vs historical vs surveillance
        # MUST NOT: return zero for missing data
        # MUST NOT: label historical as current
        ...

class HealthObservation(Observation):
    """Extended observation for health domain."""
    health_category: HealthCategory  # alert | historical | surveillance | etc.
    issuing_authority: str
    valid_from: datetime | None
    valid_until: datetime | None
    affected_geography_level: str    # state | district | block | village
    severity: str | None             # As defined by the source, not invented
    disease_code: str | None         # ICD-10 or equivalent
    prevention_link: str | None      # URL to authoritative guidance
    prevention_link_date: date | None
```

---

### Task 5.3 — NCDC Bulletin Adapter

**Action:** Process NCDC (National Centre for Disease Control) weekly outbreak reports.

**Reality check:** NCDC bulletins are often **PDFs**, not APIs. The adapter must handle:

1. **If a machine-readable feed exists:** Parse it with schema validation
2. **If only PDFs exist:** Document the manual ingestion process
3. **If the source is unavailable:** Mark as `UNAVAILABLE` and document alternatives

```python
class NCDCBulletinAdapter(HealthAdapter):
    source_id = "ncdc-weekly-bulletin"
    publisher = "National Centre for Disease Control, India"
    
    async def fetch(self, place_id: str, **kwargs) -> list[HealthObservation]:
        # Step 1: Check if we have a cached/ingested bulletin
        # Step 2: If available, return matching observations for place
        # Step 3: If unavailable, return empty list (NOT fake data)
        ...
    
    async def ingest_bulletin(
        self, 
        bulletin_date: date,
        data: dict,  # Structured data from manual PDF extraction
        extraction_method: str,
        extracted_by: str,
    ) -> list[HealthObservation]:
        """Manual ingestion path for PDF bulletins."""
        ...
```

---

### Task 5.4 — Health Indicators Adapter

**Action:** Connect to official health indicator sources.

**Indicators to target (based on availability):**

| Indicator | Source | Geographic Level |
|-----------|--------|-----------------|
| Disease outbreak status | NCDC/IDSP | District/state |
| Vaccination coverage | NHM/HMIS | District |
| Infant mortality rate | SRS/Census | District/state |
| Maternal mortality | SRS | State |
| Hospital bed availability | NHM | District |
| Water-borne disease reports | State health dept | District |

**For each indicator, record:**
- Definition and methodology
- Numerator and denominator (where applicable)
- Unit of measurement
- Reference period
- Geographic coverage level
- Update frequency and typical lag

---

### Task 5.5 — Alerts API Endpoint

**Action:** Implement `GET /api/v1/places/{id}/alerts`

```python
class Alert(BaseModel):
    id: str
    issuer: str                      # "NCDC" / "Odisha State Health Dept"
    category: str                    # disease_outbreak / advisory / warning
    source_record_id: str
    source_url: str | None
    title: str
    description: str
    issue_time: datetime             # When the authority issued it
    valid_from: datetime | None
    valid_until: datetime | None     # Alerts EXPIRE
    source_severity: str | None      # Severity as defined by source
    affected_geometry_level: str     # state | district | block
    affected_place_ids: list[str]
    status: str                      # active | expired | superseded
    url: str | None                  # Link to original

class AlertsResponse(BaseModel):
    active_alerts: list[Alert]       # Currently valid
    recent_expired: list[Alert]      # Recently expired (last 30 days)
    source_status: str               # "connected" | "stale" | "unavailable"
    last_checked: datetime
    note: str | None                 # e.g., "No active alerts from connected sources"
```

**Alert rules:**
- ✅ Alerts have expiry times — show whether they are active or expired
- ✅ Show the issuing authority and issue date prominently
- ❌ Never create an alert from unofficial sources
- ❌ Never invent emergency phone numbers
- ❌ Historical case counts are NOT alerts
- ❌ If no active alert exists, say "No active alerts" — NOT "No disease"

---

### Task 5.6 — Health Panel UI

**Action:** Build the health panel with strict category separation.

```
apps/web/src/components/profile/health/
├── HealthPanel.tsx             # Main health panel container
├── ActiveAlertsSection.tsx     # Official alerts (top of panel)
├── HealthIndicatorsSection.tsx # Surveillance/indicator data
├── HistoricalSection.tsx       # Past records clearly labelled
├── FacilitiesSection.tsx       # Nearby health facilities
├── PreventionSection.tsx       # Authoritative guidance links
├── AlertCard.tsx               # Single alert display
├── HealthIndicatorCard.tsx     # Single indicator with provenance
└── AlertExpiryBadge.tsx        # Active / Expired / Superseded
```

**Health panel layout:**

```
┌─────────────────────────────────────────┐
│ 🏥 Health — [Place Name]                │
├─────────────────────────────────────────┤
│ ⚠️ ACTIVE ALERTS                        │
│ ┌─────────────────────────────────────┐ │
│ │ [Alert Card — if any active alerts] │ │
│ │ Issuer: NCDC | Issued: 2026-10-15  │ │
│ │ Valid until: 2026-10-22             │ │
│ │ Affected: Ganjam District          │ │
│ └─────────────────────────────────────┘ │
│ (or "No active alerts from connected    │
│  sources. Last checked: [date]")        │
├─────────────────────────────────────────┤
│ 📊 HEALTH INDICATORS                    │
│ • Indicator 1: value (Source, Period)   │
│ • Indicator 2: value (Source, Period)   │
│   [STALE - last updated 60 days ago]   │
│ • Indicator 3: UNAVAILABLE             │
├─────────────────────────────────────────┤
│ 📅 HISTORICAL RECORDS                   │
│ • Disease X: 45 cases (Jan-Mar 2024)   │
│   Source: NCDC Bulletin W12-2024       │
│   ⚠️ HISTORICAL — Not current status  │
├─────────────────────────────────────────┤
│ 🏨 NEARBY HEALTH FACILITIES            │
│ • PHC Name — 3.2 km (source, date)    │
│   ⚠️ Listing ≠ operational status      │
├─────────────────────────────────────────┤
│ 🛡️ PREVENTION GUIDANCE                  │
│ • [Link to WHO guidance] (dated)       │
│ • [Link to MoHFW advisory] (dated)    │
│ ℹ️ This is not medical advice.          │
│    Consult a healthcare professional.  │
└─────────────────────────────────────────┘
```

> [!CAUTION]
> **No individual diagnosis or treatment instructions.** The map is not a substitute for medical care. Include this disclaimer prominently.

---

### Task 5.7 — Prevention Guidance Links

**Action:** Link precautions to authoritative sources only.

**Allowed sources for prevention guidance:**
- WHO (World Health Organization)
- MoHFW (Ministry of Health and Family Welfare, India)
- NCDC (National Centre for Disease Control)
- Relevant state health authority

**Rules:**
- Always show the guidance publication date
- Link directly to the source — don't paraphrase medical advice
- If guidance is outdated (> 1 year), show a "Last updated: [date]" warning
- Do NOT invent emergency phone numbers — either use verified numbers or don't show any

---

### Task 5.8 — Health Facility Map Layer

**Action:** Add verified health facilities to the map as an optional layer.

```typescript
// Map layer: health-facilities
// - Icon by facility type (PHC, CHC, District Hospital)
// - Popup shows: name, type, address, source, date
// - Disclaimer: "Listing from [source]. Does not confirm current status."
// - Only shown if dataset/licence is verified (per Phase 0)
```

---

### Task 5.9 — LLM Guardrails (If AI Summaries Are Used)

**Action:** If any LLM summarization is used for health data, implement these guardrails:

```python
class HealthSummaryGuardrails:
    """Validates AI-generated health summaries."""
    
    def validate_summary(
        self, 
        summary: str, 
        source_records: list[Observation]
    ) -> ValidationResult:
        """
        1. Every factual sentence must cite a record ID/URL
        2. If evidence is absent, text must say "not found in connected sources"
        3. Reject citations that don't resolve to actual records
        4. No treatment recommendations
        5. No individual diagnosis
        6. Use deterministic templates for alerts (not free-form LLM text)
        """
        ...
```

> [!IMPORTANT]
> For high-stakes health alerts, use **deterministic templates**, not free-form LLM text. Summaries are optional and non-authoritative.

---

### Task 5.10 — Tests (Safety-Critical)

**These tests are non-negotiable. The health system must not ship without them.**

```python
# tests/test_health_safety.py — CRITICAL TESTS

# --- Data integrity ---
def test_no_fake_outbreak_data():
    """No fabricated outbreak pins or statistics in UI or API."""

def test_unavailable_not_zero():
    """Missing health data returns 'unavailable', NEVER zero."""

def test_no_live_surveillance_claim_without_live_feed():
    """Cannot claim 'live surveillance' unless a live feed is verified."""

# --- Temporal accuracy ---
def test_historical_not_labelled_current():
    """2024 case counts are not displayed as current status."""

def test_alert_expiry():
    """Expired alerts show 'EXPIRED' badge, not active status."""

def test_stale_data_marked():
    """Data older than expected update cycle shows STALE badge."""

# --- Geographic accuracy ---
def test_district_data_not_village_labelled():
    """District-level health data stays labelled district-level."""

# --- Category separation ---
def test_alert_vs_historical_separation():
    """Official alerts and historical records are in separate sections."""

def test_no_community_report_as_official():
    """Unverified reports cannot become official alerts."""

# --- Safety ---
def test_no_individual_diagnosis():
    """No treatment or diagnosis text in the health panel."""

def test_no_invented_phone_numbers():
    """Emergency numbers are either verified or not shown."""

def test_prevention_links_authoritative():
    """Prevention links point to WHO/MoHFW/NCDC/state authority only."""

# --- Resilience ---
def test_health_provider_timeout():
    """Timeout → 'temporarily unavailable', not crash."""

def test_conflicting_health_values():
    """Conflicting sources shown side by side, not silently averaged."""

def test_malformed_health_data_rejected():
    """Bad data from source is rejected, not passed through."""

# --- Fallback ---
def test_no_incompatible_fallback():
    """Health data from incompatible sources is not silently substituted."""
```

---

## 📂 Expected File Changes

```
NEW: services/ingestion/src/adapters/health/base_health.py
NEW: services/ingestion/src/adapters/health/ncdc_bulletin.py
NEW: services/ingestion/src/adapters/health/mohfw_indicators.py
NEW: services/ingestion/src/adapters/health/state_health.py
NEW: services/api/src/garuda_api/routes/alerts.py
NEW: services/api/src/garuda_api/models/alert.py
NEW: services/api/src/garuda_api/models/health.py
NEW: apps/web/src/components/profile/health/ (all components)
NEW: tests/test_health_safety.py
NEW: tests/test_health_adapter.py
NEW: tests/test_alerts.py
NEW: data/fixtures/health-bulletin-sample.json
```

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] Official bulletins/indicators displayed with full provenance
- [ ] Historical records are **clearly separated** from current status
- [ ] Alerts have expiry times and show `ACTIVE` / `EXPIRED` status
- [ ] **Stale/unavailable/conflicting tests all pass**
- [ ] No claim of "live surveillance" without a verified live feed
- [ ] District-level health data is labelled "district-level" even on village pages
- [ ] Prevention links point to WHO/MoHFW/NCDC/state authority only
- [ ] Health disclaimer ("This is not medical advice") is visible
- [ ] No fabricated outbreak data anywhere in the system
- [ ] No individual diagnosis or treatment instructions
- [ ] No invented emergency phone numbers
- [ ] All 15+ safety tests pass
- [ ] Facilities listed with operational-status disclaimer

---

## 🤖 Agent Instructions

1. **This is safety-critical code.** Take extra care with health data display.
2. Write ALL safety tests FIRST (test-driven development for health).
3. If no machine-readable health feed exists, document this explicitly — do NOT fabricate an API.
4. For PDF bulletin ingestion, write a separate manual ingestion script with clear instructions.
5. The health panel must work correctly even when ALL health sources are unavailable.
6. Never average conflicting health values — show them separately.
7. Test with: valid data, stale data, conflicting data, missing data, malformed data, and timeout.
8. **Every test failure in test_health_safety.py is a release blocker.**

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| No stable health API exists | Use manual ingestion of PDF bulletins; clearly document the process |
| Health data is state-level only | Show at state level, clearly labelled; don't pretend it's village data |
| Outdated prevention guidance | Show guidance date; add "last reviewed" warning |
| Conflicting case counts from different sources | Show both values with source citations — never silently average |

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] All safety tests pass (zero failures allowed)
- [ ] Health panel tested with: real data, stale data, no data, conflicting data
- [ ] Prevention links verified as authoritative and dated
- [ ] Phase 5 report documents: connected health sources, data coverage, safety test results

---

*Derived from: Development Plan §2 (Health Panel), §5 (Health Safety + Anti-hallucination), §6 (Stage 5), §12 (Alerts API)*
