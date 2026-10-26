import './env';
import * as Cesium from 'cesium';
import {
  GIBS_BASE_URL,
  IMAGERY_LAYERS,
  temporalLabel,
  wmtsTimeDimension,
  type ImageryLayerConfig,
  type LocalMosaicManifest,
} from './config';

function createGibsProvider(config: ImageryLayerConfig): Cesium.ImageryProvider {
  // A static layer sends no `time` dimension at all. Sending an empty one would
  // be a request GIBS cannot serve, and omitting it is what makes "no date"
  // an explicit choice rather than a default.
  const time = wmtsTimeDimension(config);
  return new Cesium.WebMapTileServiceImageryProvider({
    url: GIBS_BASE_URL,
    layer: config.layer,
    style: config.style,
    format: config.format,
    tileMatrixSetID: config.tileMatrixSetID,
    // GIBS `GoogleMapsCompatible_LevelN` sets are a standard 1x1 power-of-two
    // pyramid of 256 px tiles, matching Cesium's WebMercatorTilingScheme.
    tilingScheme: new Cesium.WebMercatorTilingScheme(),
    tileWidth: config.tileSize,
    tileHeight: config.tileSize,
    maximumLevel: config.maximumLevel,
    ...(time ? { time } : {}),
    enablePickFeatures: false,
    credit: config.attribution,
  });
}

/**
 * What the UI may tell a reader about when the visible imagery was captured.
 *
 * Returns the label for the topmost layer that has an opinion, so the globe
 * states a real date when the imagery has one and says "static composite"
 * rather than showing nothing or inventing a date.
 */
export function imageryTemporalLabel(): string {
  const withOpinion = [...IMAGERY_LAYERS].reverse().find((l) => l.temporal_coverage.kind === 'dated');
  const layer = withOpinion ?? IMAGERY_LAYERS[0];
  return temporalLabel(layer);
}

/**
 * Locally generated Sentinel-2 XYZ tiles (built by `tools/imagery`). The
 * manifest constrains the provider to the mosaic's own rectangle and level
 * range, so Cesium never requests a tile the pipeline did not produce.
 */
function createMosaicProvider(
  mosaic: LocalMosaicManifest,
): Cesium.UrlTemplateImageryProvider {
  const [west, south, east, north] = mosaic.mosaic.bbox_wgs84;
  const levels = Object.keys(mosaic.tiles_per_level)
    .map(Number)
    .filter((z) => Number.isFinite(z));
  return new Cesium.UrlTemplateImageryProvider({
    url: `/imagery/${mosaic.region}/{z}/{y}/{x}.png`,
    rectangle: Cesium.Rectangle.fromDegrees(west, south, east, north),
    minimumLevel: Math.min(...levels),
    maximumLevel: Math.max(...levels),
    enablePickFeatures: false,
    credit: mosaic.attribution_display,
  });
}

/** Runtime shape-check for the pipeline manifest; null means "no mosaic". */
export function parseMosaicManifest(json: unknown): LocalMosaicManifest | null {
  if (typeof json !== 'object' || json === null) return null;
  const m = json as Record<string, unknown>;
  const mosaic = m.mosaic as Record<string, unknown> | undefined;
  const bbox = mosaic?.bbox_wgs84;
  const bboxOk =
    Array.isArray(bbox) &&
    bbox.length === 4 &&
    bbox.every((v) => typeof v === 'number' && Number.isFinite(v));
  const levels = m.tiles_per_level;
  const levelsOk =
    typeof levels === 'object' &&
    levels !== null &&
    Object.keys(levels).length > 0 &&
    Object.entries(levels as Record<string, unknown>).every(
      ([key, value]) =>
        /^\d+$/.test(key) &&
        typeof (value as { count?: unknown } | null)?.count === 'number',
    );
  if (
    typeof m.region === 'string' &&
    /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(m.region) &&
    typeof m.attribution_display === 'string' &&
    typeof mosaic?.ground_res_m === 'number' &&
    bboxOk &&
    levelsOk
  ) {
    return json as LocalMosaicManifest;
  }
  return null;
}

/** Adds a RainViewer radar layer for the given coordinates. */
export function addRainViewerLayer(
  viewer: Cesium.Viewer,
  lng: number,
  lat: number,
): Cesium.ImageryLayer {
  const now = Date.now();
  const iso3 = 'IN'; // India (default CAMERAS.india region)
  // Use the provided coordinates to position the radar layer center;
  // RainViewer global tiles are indexed by location, so we embed the
  // center point as a query parameter so the server returns the correct tile.
  const url = `https://tiles.rainviewer.com/v2/radar/${iso3}/Reflectivity/${now}/?lon=${lng}&lat=${lat}`;
  const rainProvider = new Cesium.WebMapTileServiceImageryProvider({
    url,
    layer: 'Raster',
    style: 'default',
    format: 'image/png',
    tileMatrixSetID: 'GoogleMapsCompatible_LevelN',
    tileWidth: 256,
    tileHeight: 256,
    maximumLevel: 13,
    minimumLevel: 0,
    credit: 'Weather radar: RainViewer',
  });
  return viewer.imageryLayers.addImageryProvider(rainProvider);
}

/** Adds base layers first, then cartographic overlays, in configured order. */
export function addImageryLayers(viewer: Cesium.Viewer): Cesium.ImageryLayer[] {
  const ordered = [...IMAGERY_LAYERS].sort((a, b) => {
    if (a.role === b.role) return 0;
    return a.role === 'base' ? -1 : 1;
  });

  return ordered.map((config) => viewer.imageryLayers.addImageryProvider(createGibsProvider(config)));
}

/**
 * Adds the generated mosaic directly above the base imagery and below the
 * cartographic overlays. Returns the layer so callers can remove it when a
 * newer manifest arrives or the viewer unmounts.
 */
export function addMosaicLayer(
  viewer: Cesium.Viewer,
  mosaic: LocalMosaicManifest,
): Cesium.ImageryLayer {
  const baseCount = IMAGERY_LAYERS.filter((layer) => layer.role === 'base').length;
  return viewer.imageryLayers.addImageryProvider(createMosaicProvider(mosaic), baseCount);
}
