# Phase 10 — Pilot & Expansion

> **Duration:** Ongoing  
> **Objective:** Deploy the Odisha pilot, compare against official records, collect feedback, validate data integrity in the real world, and expand gradually — one region, one domain at a time.

---

## 🎯 Objective

Take the hardened application to its first real-world test. Deploy the Odisha pilot (one district + blocks/villages), validate every data point against official records, collect structured feedback, and use findings to prioritize expansion. **This is NOT a public launch** — it's a controlled validation exercise.

---

## 📋 Prerequisites

- **Phase 9 COMPLETE** — all production readiness gates passed
- Deployment target identified (local machine / internal server)
- At least one reviewer/tester besides the developer
- Official records for the pilot area available for comparison

---

## 📝 Detailed Tasks

### Task 10.1 — Pilot Deployment

**Action:** Deploy the application for the pilot district.

**Deployment options (in priority order):**

| Option | Pros | Cons |
|--------|------|------|
| Local machine | Zero cost, full control | Single user |
| Docker Compose on local network | Multi-user testing | Requires Docker |
| Free-tier cloud (if terms allow) | Remote access | May sleep/throttle |

**Pre-deployment checklist:**

- [ ] All Phase 9 gates pass
- [ ] Database populated with pilot area data
- [ ] Source register shows all connected sources with current status
- [ ] Demo label visible: "PILOT — Odisha [District] — Not for public use"
- [ ] Backup taken before deployment
- [ ] Rollback procedure documented and tested

---

### Task 10.2 — Data Validation Against Official Records

**Action:** Systematically compare Garuda's data against official sources.

**Validation matrix:**

| Data Point | Garuda Value | Official Value | Source | Match? | Notes |
|-----------|-------------|---------------|--------|--------|-------|
| District population | | | Census 2011 | | |
| Block population | | | Census 2011 | | |
| Health centres count | | | State directory | | |
| Disease bulletin data | | | NCDC W42-2026 | | |
| School count | | | UDISE+ | | |
| Boundary accuracy | | | Visual check | | |

**Validation rules:**
- Every value in Garuda must trace to the same source as the official record
- Discrepancies must be investigated and documented
- Minor formatting differences are OK; value differences are bugs
- Geographic level must match (don't compare district data vs. block data)

**Output:** `docs/pilot-report/data-validation.md`

---

### Task 10.3 — Pilot Test Scenarios

**Action:** Execute structured test scenarios with the pilot deployment.

```markdown
## Test Scenario 1: Search a Known Place
1. Search for [pilot district name]
2. Verify: correct location on map
3. Verify: admin hierarchy (state → district)
4. Verify: profile loads with population data
5. Verify: source citations are correct

## Test Scenario 2: Click Unknown Area
1. Click on a rural area without a village name
2. Verify: coordinates shown
3. Verify: nearest admin unit identified
4. Verify: no invented village boundary

## Test Scenario 3: Health Data Check
1. Open health panel for pilot district
2. Verify: historical data labelled as historical
3. Verify: no fake "live" alerts
4. Verify: stale data shows stale badge
5. Verify: "unavailable" shows for missing data

## Test Scenario 4: Offline Behavior
1. Save a place
2. Disconnect network
3. Verify: saved place viewable with cached data
4. Verify: offline banner shown
5. Verify: no false claim of live data refreshing

## Test Scenario 5: Export Report
1. Export pilot district profile as HTML
2. Open exported file offline
3. Verify: all data present with source citations
4. Verify: attribution complete
5. Verify: DEMO watermark present

## Test Scenario 6: Source Failure Simulation
1. Disable one data source adapter
2. Verify: other panels still load
3. Verify: failed panel shows "unavailable"
4. Verify: source diagnostics reflects the failure

## Test Scenario 7: Performance on Mobile
1. Open on Android phone (mid-range)
2. Verify: loads in < 5s on 4G
3. Verify: map is responsive
4. Verify: touch controls work
5. Verify: profile panels load without hanging
```

**Output:** `docs/pilot-report/test-scenarios-results.md`

---

### Task 10.4 — Feedback Collection

**Action:** Collect structured feedback from pilot testers.

**Feedback form structure:**

```markdown
## Garuda Pilot Feedback

### Tester Information
- Name:
- Role:
- Device used:
- Browser:
- Date:

### Usability
1. Could you find the place you were looking for? (1-5)
2. Was the map responsive and easy to navigate? (1-5)
3. Was the profile information useful? (1-5)
4. Were data sources clearly cited? (1-5)
5. Any confusing or misleading information?

### Data Quality
1. Did any data seem incorrect? (describe)
2. Were any important data points missing? (describe)
3. Was the distinction between current/historical/stale clear?

### Missing Features
1. What feature would you most want added?
2. What additional data sources would be valuable?

### Issues
1. Any crashes, errors, or broken features?
2. Any accessibility problems?

### Overall
1. Overall satisfaction (1-5):
2. Would you use this tool regularly? Why/why not?
3. Free-form comments:
```

**Output:** `docs/pilot-report/feedback-collected.md`

---

### Task 10.5 — Pilot Report

**Action:** Compile a comprehensive pilot report.

```markdown
## Garuda Pilot Report — [District], Odisha

### Summary
- Pilot period: [start] to [end]
- Testers: [count]
- Total data sources connected: [count]
- Data validation: [pass/fail rate]

### Successes
1. [What worked well]
2. [Data that matched official records]
3. [Features that were useful]

### Gaps
1. [Missing data sources]
2. [Geographic coverage gaps]
3. [Feature requests]

### Data Quality Issues
1. [Any discrepancies found]
2. [Source freshness concerns]
3. [Resolution/geographic level limitations]

### Performance Results
- Mobile load time: [time]
- Desktop load time: [time]
- Map rendering: [notes]

### Recommendations
1. [Next data source to integrate]
2. [UI improvements needed]
3. [Performance optimizations]
4. [Next pilot area recommendation]

### Next Sources to Verify
| Source | Domain | Priority | Effort |
|--------|--------|----------|--------|
| [source1] | health | HIGH | Medium |
| [source2] | services | MEDIUM | Low |
```

**Output:** `docs/pilot-report/pilot-report.md`

---

### Task 10.6 — Expansion Planning

**Action:** Based on pilot findings, plan gradual expansion.

**Expansion rules:**
- ✅ Add new regions only after source/QA gates pass for that region
- ✅ Add new domains only after source verification and adapter testing
- ✅ Each expansion is a mini Phase 0 (feasibility) + mini Phase 4/5 (implementation)
- ❌ Do NOT expand to all of India at once
- ❌ Do NOT assume pilot sources work in other states

**Expansion matrix:**

| Region | Geography Verified | Population | Health | Services | Education | Status |
|--------|-------------------|-----------|--------|----------|-----------|--------|
| [Pilot district] | ✅ | ✅ | ✅ | ⚠️ | ✅ | PILOT |
| [Neighboring district] | ❓ | ❓ | ❓ | ❓ | ❓ | NOT STARTED |
| [Other state] | ❓ | ❓ | ❓ | ❓ | ❓ | NOT STARTED |

---

### Task 10.7 — Continuous Monitoring

**Action:** Set up ongoing monitoring for the deployed pilot.

**Monitor:**
- Source health (are adapters still returning data?)
- Cache staleness (is any data expired without refresh?)
- Error rates (are users hitting errors?)
- Performance (is it degrading over time?)
- Data freshness (are sources still publishing updates?)

**Alerts (internal, not public):**
- Source adapter fails 3 consecutive times → investigate
- All cached data older than TTL → refresh or mark stale
- Error rate > 5% → investigate

---

## ✅ Acceptance Criteria (Exit Gate)

This phase is **ongoing** — there is no single exit gate. Instead, track:

- [ ] Pilot deployed and accessible to testers
- [ ] Data validation completed against official records
- [ ] All test scenarios executed and documented
- [ ] Feedback collected from at least 2 testers
- [ ] Pilot report compiled with successes, gaps, and recommendations
- [ ] No critical data integrity issues discovered (or all resolved)
- [ ] Expansion plan drafted based on pilot findings
- [ ] **No public release** without explicit project owner approval

---

## 🤖 Agent Instructions

1. The pilot is a VALIDATION exercise, not a launch.
2. Every data discrepancy must be investigated, not ignored.
3. Collect feedback systematically — don't rely on informal impressions.
4. The pilot report is a critical deliverable — invest time in it.
5. Expansion decisions are made by the project owner, not the agent.
6. Continue to monitor source health after initial deployment.
7. Any data integrity issue discovered in pilot is a Phase 4/5 bug to fix.

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Pilot data doesn't match official records | Investigate, fix, re-validate — this is the purpose of the pilot |
| Free-tier hosting sleeps/throttles | Use local deployment for pilot; cloud hosting is optional |
| Scope creep: stakeholders want more features | Defer to expansion plan; add only after source/QA gates pass |
| Pilot district selected poorly (sparse data) | Document gaps honestly; consider switching pilot if too many blockers |

---

## ✔️ Definition of Done (Pilot Complete)

- [ ] Pilot report finalized and reviewed
- [ ] All critical data integrity issues resolved
- [ ] Feedback incorporated into backlog
- [ ] Expansion plan approved by project owner
- [ ] Decision made: expand pilot / expand to new region / add new domain

---

*Derived from: Development Plan §6 (Stage 10), §16 (Suggested Odisha Pilot), §15 (Risks)*
