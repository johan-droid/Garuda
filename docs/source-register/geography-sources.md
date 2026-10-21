# Boundary & Geography Source Register

## Source 1: Survey of India Open Data / Administrative Boundaries
- **Publisher:** Survey of India, Department of Science & Technology, Government of India
- **URL:** https://surveyofindia.gov.in
- **Licence/Terms:** National Open Data License (GODL) / Government Open Data License - India
- **Attribution Required:** "Administrative boundaries based on Survey of India / Census of India publications"
- **Access Mode:** download
- **Format:** GeoJSON / Shapefile
- **Coverage:** National, State, District
- **Vintage/Version:** 2011 Census admin boundaries / 2019 SOI revision
- **Status:** VERIFIED
- **Notes:** High-level district boundary for Khordha verified. Village-level polygons are unavailable from central API and require point centroid fallback.

## Source 2: OpenStreetMap Administrative Boundaries & Settlements
- **Publisher:** OpenStreetMap Contributors
- **URL:** https://www.openstreetmap.org
- **Licence/Terms:** Open Data Commons Open Database License (ODbL) 1.0
- **Attribution Required:** "© OpenStreetMap contributors, ODbL"
- **Access Mode:** API / download (Overpass / Nominatim)
- **Rate Limits:** Standard public Overpass: 2 requests/sec max; nominatim.openstreetmap.org: 1 req/sec max with User-Agent
- **Format:** GeoJSON, OSM XML
- **Coverage:** Towns, major villages, road network, points of interest
- **Vintage/Version:** Continuously updated (current year)
- **Status:** VERIFIED WITH LIMITS
- **Notes:** Adequate for place names, road alignments, and major physical features; must not be used as legal boundary authority.
