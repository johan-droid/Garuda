# Map Provider & Tile Source Verification

## Tile Provider Evaluation

| Provider | Licence / Terms | Free Tier Limits | MapLibre Compatible | Status |
|----------|-----------------|------------------|---------------------|--------|
| **OpenFreeMap public instance** | OpenMapTiles schema from OpenStreetMap (ODbL 1.0) + Natural Earth (public domain); free public service, no account/key | No documented key; attribution required; no SLA | Yes (Vector style URL) | **SELECTED** (verified 2026-10-23) |
| **OpenStreetMap Standard tiles** | OSMF Tile Usage Policy; low-volume browsing only | Heavy/bulk use prohibited; requires identifying User-Agent | Yes (Raster XYZ) | VERIFIED WITH LIMITS (fallback only) |
| **CARTO Raster Basemaps (Positron/Dark Matter)** | Free for non-commercial / open-source; attribution | Unkeyed `basemaps.cartocdn.com` requests now return "API KEY REQUIRED" watermark tiles | Yes (Raster XYZ) | **REJECTED** (credential required, verified 2026-10-23) |
| **Self-Hosted PMTiles / Protomaps** | Open-source (BSD), zero external server spend | 100% offline, served from static storage or local disk | Yes (Vector + Raster) | VERIFIED (target for Phase 6) |

## Selected Approach

The default MapLibre view loads `https://tiles.openfreemap.org/styles/dark`
directly. The style is keyless and unauthenticated; MapLibre renders its own
attribution: "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".

CARTO was the previous default. Its unkeyed raster endpoints now return
watermarked "API KEY REQUIRED" tiles, so keeping it would violate the
zero-credential requirement. No API key, account, or token is used.

`ponytail:` OpenFreeMap's public instance has no SLA. Self-hosting the style
(or switching to the self-hosted PMTiles target) removes that dependency when
availability matters.
