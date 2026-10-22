/**
 * Typed configuration boundary for the Cesium 3D-terrain POC.
 *
 * Everything here is public, credential-free, open data. No secrets belong in
 * this file: any value bundled into the browser is public. A future premium
 * provider must obtain its token from a backend broker, not from `VITE_*` env
 * vars, because those are shipped to the client.
 */

export interface TerrariumTerrainSource {
  kind: 'terrarium';
  id: string;
  label: string;
  /** `{z}`/`{x}`/`{y}` slippy-map placeholders (y grows southward). */
  urlTemplate: string;
  /** Native edge length of one source tile, in pixels. */
  tileSize: number;
  /** Deepest level the host actually serves. Beyond this we stop refining. */
  maximumLevel: number;
  /** Heightmap vertices per tile requested from Cesium (must divide tileSize). */
  heightmapResolution: number;
  attribution: string;
}

export interface EllipsoidTerrainSource {
  kind: 'ellipsoid';
  id: string;
  label: string;
}

export type TerrainSource = TerrariumTerrainSource | EllipsoidTerrainSource;

/**
 * Default open terrain: Mapterhorn publishes Copernicus GLO-30 as Terrarium
 * RGB WebP tiles, no key, no account. Verified z0–z12 (z13+ returns 404).
 */
export const OPEN_TERRAIN_SOURCE: TerrariumTerrainSource = {
  kind: 'terrarium',
  id: 'mapterhorn-copernicus-glo30',
  label: 'Mapterhorn · Copernicus GLO-30 (30 m)',
  urlTemplate: 'https://tiles.mapterhorn.com/{z}/{x}/{y}.webp',
  tileSize: 512,
  maximumLevel: 12,
  // 512 -> 128 is an exact 4:1 box filter: no edge clamping, no seams.
  // ponytail: deliberate geometry cap; raise to 256 if relief looks blocky on
  // high-end GPUs, or self-host quantized-mesh to get full 30 m detail.
  heightmapResolution: 128,
  attribution:
    'Terrain: Copernicus GLO-30 © DLR e.V. 2010-2014, © Airbus Defence and Space GmbH 2014-2018, ' +
    'provided under COPERNICUS by the European Union and ESA; all rights reserved. ' +
    'Tiles published by Mapterhorn.',
};

/** Used only when the open terrain source cannot be constructed at all. */
export const ELLIPSOID_FALLBACK: EllipsoidTerrainSource = {
  kind: 'ellipsoid',
  id: 'ellipsoid',
  label: 'Ellipsoid only (no elevation)',
};

export const GIBS_BASE_URL = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/wmts.cgi';

export const GIBS_ACKNOWLEDGEMENT =
  "We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse " +
  "Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).";

export interface ImageryLayerConfig {
  id: string;
  label: string;
  /** `base` layers go under `overlay` layers. */
  role: 'base' | 'overlay';
  layer: string;
  style: string;
  format: string;
  tileMatrixSetID: string;
  /** Deepest level published for this layer in EPSG:3857 WMTS. */
  maximumLevel: number;
  tileSize: number;
  attribution: string;
}

/**
 * NASA GIBS, EPSG:3857 `GoogleMapsCompatible_LevelN` matrix sets: 256 px tiles
 * on a standard 1x1 power-of-two pyramid, which matches Cesium's
 * WebMercatorTilingScheme. The EPSG:4326 sets are deliberately not used: their
 * levels are 2x1, 3x2, 5x3, ... and do not align with any Cesium tiling scheme.
 * All layers here are time-static, so no date dimension is sent.
 */
export const IMAGERY_LAYERS: ImageryLayerConfig[] = [
  {
    id: 'gibs-blue-marble',
    label: 'NASA Blue Marble (shaded relief + bathymetry)',
    role: 'base',
    layer: 'BlueMarble_ShadedRelief_Bathymetry',
    style: 'default',
    format: 'image/jpeg',
    tileMatrixSetID: 'GoogleMapsCompatible_Level8',
    maximumLevel: 8,
    tileSize: 256,
    attribution: 'Imagery: NASA Blue Marble / GIBS (NASA EOSDIS).',
  },
  {
    id: 'gibs-reference-features',
    label: 'GIBS reference features (roads, borders, water)',
    role: 'overlay',
    layer: 'Reference_Features_15m',
    style: 'default',
    format: 'image/png',
    tileMatrixSetID: 'GoogleMapsCompatible_Level13',
    maximumLevel: 13,
    tileSize: 256,
    attribution: 'Cartography overlay: NASA GIBS Reference Features.',
  },
  {
    id: 'gibs-reference-labels',
    label: 'GIBS reference labels (place names)',
    role: 'overlay',
    layer: 'Reference_Labels_15m',
    style: 'default',
    format: 'image/png',
    tileMatrixSetID: 'GoogleMapsCompatible_Level13',
    maximumLevel: 13,
    tileSize: 256,
    attribution: 'Cartography overlay: NASA GIBS Reference Labels.',
  },
];

export const CESIUM_ATTRIBUTION = 'CesiumJS © CesiumGS, Inc. — Apache License 2.0';

export const CAMERAS = {
  earth: { longitude: 78.9629, latitude: 20.5937, height: 16_000_000 },
  india: { longitude: 82.5, latitude: 22.5, height: 3_200_000 },
  odisha: { longitude: 85.4, latitude: 20.2, height: 420_000 },
} as const;

/**
 * Garuda pilot boundaries expose `canonical_name`, not the `name`/`level`
 * fields declared by `BoundaryProperties`. The POC reads the real shape from
 * `LiveBoundaryProperties` in types/contracts.
 */
