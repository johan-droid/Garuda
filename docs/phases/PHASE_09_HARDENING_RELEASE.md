# Phase 9 — Hardening & Release Preparation

> **Duration:** 1–3 weeks  
> **Objective:** Security audit, dependency review, privacy checks, performance optimization, accessibility, backup/restore, attribution compliance, documentation, and packaging — all critical gates from the production readiness checklist.

---

## 🎯 Objective

Prepare the application for its first controlled deployment. This is not a public launch — it's ensuring that every item on the production readiness checklist passes. The application must be safe, performant, accessible, and honestly documented.

---

## 📋 Prerequisites

- **Phase 8 COMPLETE** (or the agreed subset of satellite features)
- All prior phase tests passing
- Source register and licence inventory up to date

---

## 📝 Detailed Tasks

### Task 9.1 — Security Audit

**Action:** Comprehensive security review.

**Checklist:**

| Check | Status | Notes |
|-------|--------|-------|
| No secrets in Git history | | Run `git log --all -p \| grep -i "api_key\|secret\|password"` |
| No secrets in client bundle | | Inspect built JS bundle |
| No secrets in source register responses | | Test `/api/v1/sources` |
| Input validation on all API endpoints | | Pydantic models, query param validation |
| Response size bounded | | Max payload limits |
| SQL injection protected | | Parameterized queries, ORM |
| XSS protected | | React auto-escapes; review `dangerouslySetInnerHTML` |
| HTTPS enforced (for public deployments) | | HSTS header |
| CORS configured correctly | | Only allow intended origins |
| Rate limiting on API endpoints | | Prevent abuse |
| Dependency vulnerability scan | | `npm audit`, `pip-audit` or `safety check` |
| Least privilege principle | | File permissions, DB access |
| Safe logging (no PII, no secrets) | | Review all log statements |
| `.env` not committed | | `.gitignore` check |
| Error messages don't leak internals | | No stack traces in production responses |

```bash
# Security scan commands
npm audit --audit-level=high
pip-audit
ruff check --select S  # Bandit-equivalent security rules
```

---

### Task 9.2 — Dependency & Licence Review

**Action:** Audit every dependency's licence and security.

```markdown
## Dependency Inventory

### Python Dependencies
| Package | Version | Licence | Security | Notes |
|---------|---------|---------|----------|-------|
| fastapi | 0.115.x | MIT | ✅ | |
| pydantic | 2.9.x | MIT | ✅ | |
| httpx | 0.27.x | BSD-3 | ✅ | |
| uvicorn | 0.30.x | BSD-3 | ✅ | |
| ... | ... | ... | ... | |

### JavaScript Dependencies
| Package | Version | Licence | Security | Notes |
|---------|---------|---------|----------|-------|
| react | 18.x | MIT | ✅ | |
| maplibre-gl | 4.x | BSD-3 | ✅ | |
| @tanstack/react-query | 5.x | MIT | ✅ | |
| zod | 3.x | MIT | ✅ | |
| ... | ... | ... | ... | |
```

**Check:**
- ❌ No GPL-incompatible combinations (if project is MIT/Apache)
- ❌ No deprecated packages with known vulnerabilities
- ✅ All licences permit the intended use
- ✅ Attribution requirements documented in `ATTRIBUTION.md`

---

### Task 9.3 — Privacy Review

**Action:** Verify privacy-safe data handling.

**Checklist:**

| Check | Status |
|-------|--------|
| No personal health data exposed | |
| No individual-identifiable information | |
| Location permission explained before requesting | |
| Manual search/coordinate entry available (no forced GPS) | |
| Small population counts suppressed/aggregated (re-identification risk) | |
| No user tracking without consent | |
| Analytics (if any) are privacy-respecting | |
| Community reports (if implemented) have privacy-safe text | |
| Logs don't contain user IPs or personal data | |

---

### Task 9.4 — Performance Optimization

**Action:** Test and optimize for target devices.

**Target devices:**
- Representative Android phone (mid-range, 3-4 year old)
- Modest Windows laptop
- Modest Linux laptop

**Performance checklist:**

| Metric | Target | Test Method |
|--------|--------|-------------|
| Initial page load | < 3s on 4G | Lighthouse |
| Time to interactive | < 5s on 4G | Lighthouse |
| Map first paint | < 2s | Manual test |
| Bundle size (gzipped) | < 500KB | Build output |
| API response time (p95) | < 2s | Load test |
| Memory usage (map + profile) | < 200MB | DevTools |
| Boundary layer loading | Bounded (max 500 features per zoom) | Manual test |

**Optimization targets:**
- Lazy-load non-critical panels
- Code-split route-level components
- Compress and simplify boundary GeoJSON per zoom level
- Use HTTP cache headers appropriately
- Lazy-load satellite imagery (never auto-download on mobile)

```bash
# Performance testing commands
npx lighthouse http://localhost:5173 --output=json --output-path=./perf-report.json
npm run build -- --report  # Bundle size analysis
```

---

### Task 9.5 — Accessibility Audit

**Action:** Ensure the application is accessible.

**Checklist:**

| Check | Status | Notes |
|-------|--------|-------|
| Keyboard navigation works for all interactive elements | | Tab order, Enter/Space activation |
| Touch support for all map interactions | | Mobile touch events |
| Sufficient color contrast (WCAG AA) | | Verify with contrast checker |
| All interactive elements have labels | | `aria-label`, `alt` text |
| `prefers-reduced-motion` respected | | Disable animations |
| Screen reader reads data cards correctly | | Test with NVDA/VoiceOver |
| Search is a viable alternative to map-only navigation | | All map functions accessible via search |
| Focus indicators visible | | Custom focus styles |
| Font sizes readable (min 14px body) | | |
| Error messages announced to screen readers | | `aria-live` regions |

```bash
# Accessibility testing
npx axe-cli http://localhost:5173
```

---

### Task 9.6 — Backup & Restore

**Action:** Implement and test backup/restore for the database.

```bash
# Backup commands (to document)
# SQLite backup
cp garuda.db garuda.db.backup.$(date +%Y%m%d)

# PostgreSQL backup (if used)
pg_dump garuda_db > garuda_backup_$(date +%Y%m%d).sql

# Restore test
# Must verify:
# 1. Fresh restore works
# 2. All observations survive
# 3. Source register intact
# 4. Cache rebuilt correctly
```

**Test:**
- [ ] Create backup → wipe DB → restore → verify all data present
- [ ] Document backup/restore in `docs/OPERATIONS.md`

---

### Task 9.7 — Attribution & Legal Compliance

**Action:** Finalize `ATTRIBUTION.md` with all required attributions.

```markdown
# Attribution

## Map Data
- © OpenStreetMap contributors (ODbL)
- Map tiles: [provider] ([licence])
- Map renderer: MapLibre GL JS (BSD-3-Clause)

## Data Sources
- Census of India 2011 — Office of Registrar General (GODL-India)
- [Each source with full attribution text as required by their licence]

## Satellite Imagery
- [ISRO/NRSC product] — [licence and attribution]
- Contains Copernicus Sentinel data [year] (processed by [us])

## Software Dependencies
- [Key dependencies with licence]

## Disclaimer
This is an informational tool. Data sourced from public records.
Not a substitute for official government publications or medical advice.
```

---

### Task 9.8 — Operations Documentation

**Action:** Write comprehensive operations docs.

```
docs/
├── SETUP.md          # Updated with all phases
├── OPERATIONS.md     # NEW: Ops runbook
├── CONTRIBUTING.md   # How to add/disable adapters
└── KNOWN_LIMITS.md   # NEW: Known limitations
```

**OPERATIONS.md must cover:**
- Health endpoint monitoring
- Log locations and format
- Source diagnostics interpretation
- Backup/restore procedure
- Rollback instructions
- How to disable a broken adapter
- Incident response steps

**KNOWN_LIMITS.md must cover:**
- Data freshness limitations per source
- Geographic coverage gaps
- Feature limitations by platform (mobile vs. desktop)
- Offline capability boundaries
- Performance constraints

---

### Task 9.9 — Final Test Suite

**Action:** Run the complete test suite and ensure everything passes.

```bash
# Backend tests
cd services/api && pytest --tb=short -v

# Frontend tests
cd apps/web && npm run test -- --run

# Type checks
cd services/api && mypy src/
cd apps/web && npx tsc --noEmit

# Lint
cd services/api && ruff check .
cd apps/web && npm run lint

# Security
npm audit
pip-audit

# E2E tests (if Playwright configured)
npx playwright test
```

**No test failures are acceptable for release.**

---

### Task 9.10 — Production Readiness Checklist (From Plan Document)

| Area | Gate | Status |
|------|------|--------|
| **Data integrity** | Every dataset has source register, traceable sample, period/geography, no silent zero defaults | |
| **Licensing** | Map style, tiles, boundaries, imagery, datasets, libraries reviewed individually; attribution confirmed | |
| **Health safety** | Official dated alerts; historical not labelled current; prevention links authoritative; no individual diagnosis | |
| **Resilience** | Timeout/retry/backoff, rate-limit, cache/stale, partial-profile, provider-outage tested | |
| **Security** | No secrets in repo/client; validation; safe logs; dependency checks; least privilege; HTTPS | |
| **Performance** | Tested on representative Android phone and modest Windows/Linux laptop; bounded layer loading | |
| **Accessibility** | Keyboard/touch, contrast, labels, reduced motion, search alternative to map-only | |
| **Offline** | Saved reports work offline; no implication that live alerts refresh without network | |
| **Operations** | Health endpoint, logs, source diagnostics, backup/restore test, rollback notes | |
| **Documentation** | Install/run/update, add/disable adapter, attribution, known limitations, source freshness documented | |
| **Release** | No public release until critical gates pass; demo clearly labelled as demo | |

> [!CAUTION]
> **No public release until ALL critical gates pass.** Early demos must be clearly labelled as "DEMO — Not for public use."

---

## ✅ Acceptance Criteria (Exit Gate)

- [ ] All security checks pass (no secrets, no vulnerabilities)
- [ ] All dependencies have reviewed licences
- [ ] Privacy checklist complete
- [ ] Performance targets met on representative devices
- [ ] Accessibility audit passes (keyboard, contrast, labels)
- [ ] Backup/restore tested successfully
- [ ] `ATTRIBUTION.md` complete and accurate
- [ ] `OPERATIONS.md` documented
- [ ] `KNOWN_LIMITS.md` documented
- [ ] ALL tests pass (backend, frontend, type checks, lint, security)
- [ ] Production readiness checklist (§14) ALL items addressed
- [ ] **No committed secrets** in entire Git history
- [ ] Demo label present on all demo builds

---

## 🤖 Agent Instructions

1. Run EVERY security check and report exact results.
2. The dependency audit must cover EVERY package, not just top-level.
3. Performance testing must be done with realistic data, not empty fixtures.
4. Accessibility testing requires keyboard-only navigation — verify yourself.
5. Backup/restore must be tested end-to-end, not just documented.
6. Attribution must match what each licence REQUIRES, not just a generic credit.
7. Do NOT mark any gate as "pass" unless the actual test ran and succeeded.

---

## ✔️ Definition of Done

- [ ] All acceptance criteria met
- [ ] Production readiness checklist fully addressed
- [ ] Complete test suite passes with zero failures
- [ ] Phase 9 report documents: security findings, performance results, accessibility results, known limitations

---

*Derived from: Development Plan §6 (Stage 9), §10 (Security/Privacy), §14 (Production Readiness Checklist)*
