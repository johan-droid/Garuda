# Cesium 3D-terrain POC

Opt-in 3D globe with real elevation, added beside the default MapLibre map.

- Entry point: `/?globe=1` (the default `/` is unchanged and still MapLibre).
- Scope: isolated spike. It does not modify the backend, the database, `MapView.tsx` or `HomePage.tsx`.

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
              Reference_Features_15m               (overlay, Level13)
              Reference_Labels_15m                 (overlay, Level13)
```

## Providers (verified 2026-10-22)

| Provider | Role | Access | Licence / attribution | Limits |
|---|---|---|---|---|
| Mapterhorn | terrain | `https://tiles.mapterhorn.com/{z}/{x}/{y}.webp`, no key | Copernicus GLO-30 full, free and open licence; see `ATTRIBUTION.md` | global 30 m, z0–z12, 404 on ocean/no-data tiles |
| NASA GIBS | imagery + cartography | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi`, no key | NASA EOSDIS, free and open; acknowledgement required | BlueMarble ≤ ~611 m/px (level 8); reference overlays to level 13 |

Copernicus DEM GLO-90 was investigated and rejected as the default: there is no hosted
Cesium terrain endpoint, the source products need a Copernicus Data Space account, and
delivery requires converting DTED/GeoTIFF to quantized-mesh and hosting it yourself.

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

- **Imagery resolution**: GIBS tops out around 611 m/px for the base layer, so the
  district-level view is blurry even though terrain detail is 30 m. Higher-resolution
  open satellite mosaics checked (e.g. EOX Sentinel-2 cloudless) are CC BY-NC-SA and
  therefore not suitable.
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
| Default `/` route | MapLibre canvas present, Cesium globals absent, no console errors |

## Rollback

Delete `frontend/src/cesium/`, `frontend/src/components/CesiumGlobe.tsx`,
`frontend/src/pages/GlobePage.tsx`, `frontend/src/styles/cesium.css`, this document, the
`LiveBoundaryProperties`/`LiveBoundaryCollection` types, the three provenance functions in
`api/client.ts`, the `?globe=1` branch in `App.tsx`, the `cesiumAssets` plugin and the
`cesium` dependency in `package.json`, plus the `frontend/public/cesium/` ignore rule.
Nothing on the default MapLibre path depends on any of it.
