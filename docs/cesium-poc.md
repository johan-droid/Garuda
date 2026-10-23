# Cesium 3D-terrain POC

Opt-in 3D globe with real elevation, added beside the default MapLibre map.

- Entry point: `/?globe=1` (the default `/` is still MapLibre).
- Scope: isolated spike. It does not modify the backend, the database, `MapView.tsx` or `HomePage.tsx`.
- Basemap note (2026-10-23): the default MapLibre view now uses OpenFreeMap's keyless
  dark style instead of CARTO, whose unkeyed tiles render "API KEY REQUIRED" watermarks.
  This is the one intentional change outside the globe, required by the zero-credential rule.

## How it runs

```bash
cd frontend
npm install
npm run dev          # then open http://localhost:5173/?globe=1
npm run build        # tsc --noEmit && vite build
```

Backend is optional. With it running (`127.0.0.1:8000`), boundaries and profiles come
from the live API. Without it, the POC shows an explicit "backend unavailable" state
and **renders no fixture data** — no mock boundaries, no generated profiles.

## Data path

```
Garuda backend (/api/v1/places/boundaries, /places/{id}/profile, /places/reverse)
        │  provenance-aware client functions (live vs. fallback, never silent)
        ▼
GlobePage ── boundary list, profile panels, provenance badges
        │
        ▼
CesiumGlobe ── Viewer (no Cesium ion)
        ├── terrain: Mapterhorn → Copernicus GLO-30, Terrarium WebP, z0–z12
        │     CustomHeightmapTerrainProvider + WebMercatorTilingScheme
        └── imagery: NASA GIBS EPSG:3857 WMTS
              BlueMarble_ShadedRelief_Bathymetry   (base, GoogleMapsCompatible_Level8)
              local Sentinel-2 mosaic              (overlay, z11–z14, same-origin, optional)
              Reference_Features_15m               (overlay, Level13)
              Reference_Labels_15m                 (overlay, Level13)
```

## Providers (verified 2026-10-22 / 2026-10-23)

| Provider | Role | Access | Licence / attribution | Limits |
|---|---|---|---|---|
| Mapterhorn | terrain | `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp`, no key | Copernicus GLO-30 full, free and open licence; see `ATTRIBUTION.md` | global 30 m, z0–z12, 404 on ocean/no-data tiles |
| NASA GIBS | imagery + cartography | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi`, no key | NASA EOSDIS, free and open; acknowledgement required | BlueMarble ≤ ~611 m/px (level 8); reference overlays to level 13 |
| Sentinel-2 L2A (local) | imagery overlay | `tools/imagery` reads `earth-search.aws.element84.com` + `sentinel-cogs` anonymously; tiles served same-origin | Sentinel Data Legal Notice; "Contains modified Copernicus Sentinel data {years}" | bounded region only, z11–z14; ~10 m source detail |
| OpenFreeMap (default 2D map) | vector basemap | `https://tiles.openfreemap.org/styles/dark`, no key | OSM ODbL + OpenMapTiles; attribution rendered | public instance, no SLA |

### Why Mapterhorn rather than raw Copernicus DEM

Copernicus DEM GLO-30 source COGs **are** anonymously readable from the AWS Open Data
mirror (`copernicus-dem-30m.s3.amazonaws.com`, verified 2026-10-23) — no account is
needed there. The real blocker is delivery: Cesium needs heightmap tiles or
quantized-mesh, so adopting it directly means downloading, mosaicking, converting, and
hosting our own terrain tiles. Mapterhorn already publishes the same GLO-30 data as
keyless Terrarium WebP, so it remains the working provider. (GLO-30 is a DSM, 30 m
posting, EGM2008 heights; do not confuse its native detail with the 128 px heightmaps
Cesium requests.)

### Why EPSG:3857 GIBS instead of EPSG:4326

The EPSG:4326 WMTS matrix sets are `2x1, 3x2, 5x3, 10x5, …` — not a power-of-two
pyramid, so they cannot be addressed with any Cesium tiling scheme (requests land out
of range and return HTTP 400). The `GoogleMapsCompatible_LevelN` sets are standard
power-of-two mercator and match `WebMercatorTilingScheme` exactly.

### Terrain decoding

- Terrarium: `height_m = (R * 256 + G + B / 256) - 32768`.
- Source tiles are 512 px webp; heightmaps are downsampled 4:1 to 128 px with an exact
  box filter (no edge clamping, so neighbouring tiles stay seamless).
- Row order and Y origin already match Cesium (both north-first), so no flip is applied.
- Refinement is capped at level 12 (the deepest level the host serves) by overriding
  `getLevelMaximumGeometricError`.
- A 404 from the tile host means "no elevation data here" and is filled with sea level;
  that is not treated as a provider failure. HTTP 5xx and network errors are, and they
  surface the red "Terrain unavailable" banner while the flat ellipsoid stays visible.

## Configuration boundary

`frontend/src/cesium/config.ts` holds every provider URL, matrix set, level cap,
heightmap resolution, camera target and attribution string.

- No secrets: everything there ships to the browser.
- A future premium provider must broker its token through the backend. Do **not** put a
  credential in a `VITE_*` variable — those are public by construction.

## Known limitations

- **Imagery resolution**: outside the generated mosaic the base is NASA GIBS Blue
  Marble at ≤ ~611 m/px, so the global/district view is soft. Inside the bounded
  Odisha region the local Sentinel-2 mosaic provides ~10 m native detail (z14 renders
  at ~8.95 m ground, a mild upsample). EOX Sentinel-2 cloudless was rejected:
  CC BY-NC-SA, so not suitable.
- **Bounded mosaic**: only the configured bbox is high-resolution. It is one
  acquisition-dominated composite, not a cloud-free national mosaic; see
  `docs/imagery-pipeline.md` for masks, gaps, and scene dates.
- **Polar distortion**: mercator terrain is stretched near ±85° when the whole Earth is
  in view. Acceptable for an India-centric POC; a geographic-reprojected or self-hosted
  quantized-mesh tileset removes it.
- **Community tile host**: Mapterhorn has no SLA. Production should self-host tiles
  converted from Copernicus GLO-30/90.
- **Transient GIBS 5xx**: a small fraction (<1%) of overlay tiles return HTTP 500 and
  are retried/backfilled by Cesium on the next render.
- **Bundle weight**: Cesium is a lazy chunk plus ~7.7 MB of static assets under
  `frontend/public/cesium/` (generated, gitignored).
- **Pre-existing contract drift** (not fixed here): `BoundaryProperties` in
  `types/contracts.ts` declares `name`/`level`, while the backend emits
  `canonical_name`/`place_type`. The POC reads the real shape via
  `LiveBoundaryProperties`; `MapView.tsx` still filters on `level`.

## Verification

```bash
cd frontend && npx tsc --noEmit && npm run build
```

Browser checks used during development (Playwright, headless GPU = AMD Radeon via ANGLE):

| Check | Result |
|---|---|
| Terrain height, Tibet plateau (85.0 E, 32.0 N) | 4618 m |
| Terrain height, Everest (86.925 E, 27.988 N) | 8401 m |
| Terrain height, Khordha (85.4 E, 20.2 N) | 72 m |
| Terrain height, Bay of Bengal (88.0 E, 15.0 N) | 0 m |
| Cesium ion requests | 0 |
| Terrain tile requests | 228 × 200, 16 × 404 (ocean void), 0 real failures |
| Imagery requests | 1784 × 200, 13 transient 500 |
| Frame rate during camera fly | ~45 fps at 1600×950 |
| Backend stopped | "Backend unavailable · no boundaries shown", 0 boundary rows, no fixture names |
| Sentinel-2 mosaic at 26 km camera height | 4 imagery layers (base + mosaic + 2 overlays); z11–z12 tiles HTTP 200; seams visually continuous |
| Mosaic manifest removed | viewer still renders GIBS base immediately; sidebar says mosaic unavailable and how to rebuild |
| Cesium ion / token requests | 0 |
| Default `/` route (2026-10-23) | MapLibre canvas present, Cesium globals absent; OpenFreeMap dark style, keyless, attribution rendered |

## Rollback

Delete `frontend/src/cesium/`, `frontend/src/components/CesiumGlobe.tsx`,
`frontend/src/pages/GlobePage.tsx`, `frontend/src/styles/cesium.css`, this document, the
`LiveBoundaryProperties`/`LiveBoundaryCollection` types, the three provenance functions in
`api/client.ts`, the `?globe=1` branch in `App.tsx`, the `cesiumAssets` plugin and the
`cesium` dependency in `package.json`, plus the `frontend/public/cesium/` ignore rule.
Nothing on the default MapLibre path depends on any of it.
