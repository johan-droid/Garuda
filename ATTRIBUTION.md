# Data Source and Library Attributions

Garuda is built strictly on open data, public records, and permissive open-source software.

## Open Data Sources
1. **Census of India 2011 (Primary Census Abstract)**
   - Publisher: Office of the Registrar General & Census Commissioner, India (ORGI), Ministry of Home Affairs.
   - Terms: Government Open Data License - India (GODL).
   - Usage: Baseline population, sex ratio, and literacy indicators.

2. **Ministry of Health and Family Welfare (MoHFW) / National Health Mission (NHM) Odisha**
   - Publisher: MoHFW, Govt. of India / Health & Family Welfare Dept, Govt. of Odisha.
   - Terms: Government Open Data License - India (GODL).
   - Usage: Public health indicators and facility counts.

3. **OpenStreetMap Data & Cartography**
   - Publisher: © OpenStreetMap contributors.
   - Licence: Open Data Commons Open Database License (ODbL) 1.0.
   - Usage: Cartographic basemaps and place geographic centroids.

4. **OpenFreeMap Basemap (default MapLibre view)**
   - Publisher: OpenFreeMap (<https://openfreemap.org>), public keyless instance.
   - Data: OpenMapTiles schema built from OpenStreetMap (ODbL 1.0); Natural Earth raster shading (public domain).
   - Terms: free public service, no account or API key; attribution required and rendered in the map's attribution control.
   - Attribution (rendered): "OpenFreeMap © OpenMapTiles Data from OpenStreetMap".
   - Change note: replaced CARTO raster tiles in October 2026 because CARTO's unkeyed endpoints now return "API KEY REQUIRED" watermark tiles, which would have required a credential.
   - `ponytail:` the public instance has no SLA; self-host the OpenFreeMap style if availability becomes critical.

5. **Copernicus DEM GLO-30 (3D terrain POC only)**
   - Publisher: European Space Agency / European Union Copernicus programme.
   - Producer: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
   - Terms: Copernicus DEM is free and open. The AWS Open Data mirror (`copernicus-dem-30m`) is anonymously readable without an account; the Copernicus Data Space mirror does require registration, so it is not used.
   - Product notes: GLO-30 is a **surface** model (DSM, includes vegetation/buildings), 30 m posting, heights in metres on the EGM2008 geoid.
   - Tile delivery: Terrarium-encoded WebP tiles published by Mapterhorn (<https://mapterhorn.com/attribution>); heights decoded as `(R*256 + G + B/256) - 32768`.
   - Usage: Real elevation for the optional `?globe=1` Cesium 3D view. Not used by the default 2D map.

6. **NASA Global Imagery Browse Services (GIBS)**
   - Publisher: NASA Earth Science Data and Information System (ESDIS).
   - Terms: NASA data are free and open; no key or registration required.
   - Usage: Blue Marble shaded-relief/bathymetry base imagery plus `Reference_Features_15m` and `Reference_Labels_15m` cartographic overlays in the optional `?globe=1` Cesium 3D view.
   - Acknowledgement (required): "We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS)."

7. **Sentinel-2 L2A (generated true-colour mosaic, optional globe imagery)**
   - Publisher: European Commission / European Space Agency, Copernicus programme.
   - Source access: Sentinel-2 L2A Cloud-Optimised GeoTIFFs served anonymously from the AWS Open Data Sentinel-2 COG dataset (`sentinel-cogs.s3.us-west-2.amazonaws.com`), discovered via the Earth Search v1 STAC API (`https://earth-search.aws.element84.com/v1`). No account, key, or token is used at any stage.
   - Terms: free, full and open access under the Sentinel Data Legal Notice; reproduction, distribution, communication to the public, and adaptation are permitted **with attribution**. Mosaics are modified products.
   - Attribution (required): "Contains modified Copernicus Sentinel data {years}." The manifest at `frontend/public/imagery/<region>/manifest.json` records the exact years per generated mosaic.
   - Usage: locally generated bounded-region true-colour XYZ tiles shown above the GIBS base layer in the `?globe=1` view. Never fabricated; cloud/shadow/no-data pixels are transparent and counted in the manifest.
   - Pipeline: `tools/imagery/` (rasterio + numpy, MIT/BSD-family licences). See `docs/imagery-pipeline.md`.

## Core Open-Source Libraries
- **FastAPI**: MIT Licence
- **Pydantic**: MIT Licence
- **SQLAlchemy**: MIT Licence
- **MapLibre GL JS**: BSD-3-Clause Licence
- **CesiumJS**: Apache License 2.0 (3D terrain POC only)
- **React**: MIT Licence
- **Vite**: MIT Licence
- **TanStack Query**: MIT Licence
