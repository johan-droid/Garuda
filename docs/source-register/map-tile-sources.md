# Map Provider & Tile Source Verification

## Tile Provider Evaluation

| Provider | Licence / Terms | Free Tier Limits | MapLibre Compatible | Status |
|----------|-----------------|------------------|---------------------|--------|
| **OpenStreetMap Standard Carto** | Free for low-volume browsing only; heavy bulk prohibited by Tile Usage Policy | Strict caching and header rules; commercial/bulk apps prohibited | Yes (Raster XYZ) | VERIFIED WITH LIMITS (dev only) |
| **CARTO Raster Basemaps (Positron/Dark Matter)** | Free for non-commercial / open-source; requires attribution | Caching allowed; attribution required | Yes (Raster XYZ) | VERIFIED |
| **Self-Hosted PMTiles / Protomaps** | Open-source (BSD), zero external server spend | 100% offline, served from static storage or local disk | Yes (Vector + Raster) | VERIFIED (Target for Phase 6) |

## Selected Approach
For local development and Phase 1-2, use CARTO Positron or Protomaps raster/vector basemaps with clear "© OpenStreetMap contributors, © CARTO" attribution.
