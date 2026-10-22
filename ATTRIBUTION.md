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

4. **CARTO Basemap Tiles**
   - Publisher: © CARTO.
   - Licence: CC-BY 4.0.
   - Usage: Positron map tiles for explorer view.

5. **Copernicus DEM GLO-30 (3D terrain POC only)**
   - Publisher: European Space Agency / European Union Copernicus programme.
   - Producer: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
   - Terms: Copernicus DEM is free and open; access to the source products requires a Copernicus Data Space Ecosystem account.
   - Tile delivery: Terrarium-encoded WebP tiles published by Mapterhorn (<https://mapterhorn.com/attribution>).
   - Usage: Real elevation for the optional `?globe=1` Cesium 3D view. Not used by the default 2D map.

6. **NASA Global Imagery Browse Services (GIBS)**
   - Publisher: NASA Earth Science Data and Information System (ESDIS).
   - Terms: NASA data are free and open; no key or registration required.
   - Usage: Blue Marble shaded-relief/bathymetry base imagery plus `Reference_Features_15m` and `Reference_Labels_15m` cartographic overlays in the optional `?globe=1` Cesium 3D view.
   - Acknowledgement (required): "We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS)."

## Core Open-Source Libraries
- **FastAPI**: MIT Licence
- **Pydantic**: MIT Licence
- **SQLAlchemy**: MIT Licence
- **MapLibre GL JS**: BSD-3-Clause Licence
- **CesiumJS**: Apache License 2.0 (3D terrain POC only)
- **React**: MIT Licence
- **Vite**: MIT Licence
- **TanStack Query**: MIT Licence
