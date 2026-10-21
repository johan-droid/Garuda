# Phase 0 & Project Blocker Log

| # | Description | Severity | Impact | Mitigation Plan | Status |
|---|-------------|----------|--------|-----------------|--------|
| **B-01** | Census 2021 was deferred; latest official census is 2011 | MEDIUM | Population figures are over a decade old | Strictly flag data as `vintage: 2011` and `quality_status: historical`. Zero invented projections. | MITIGATED |
| **B-02** | Village-level boundary polygons are not published as open vector data | MEDIUM | Cannot display exact polygon outlines for every rural village | Display point centroids with nearest block/district boundary; explicit `geometry_available: false`. | MITIGATED |
| **B-03** | Public health APIs lack real-time village feeds | LOW | Real-time health data unavailable at micro-level | Aggregate at district level with explicit hierarchy badge (`affected_geography_level: district`). | MITIGATED |
