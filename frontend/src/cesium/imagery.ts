import './env';
import * as Cesium from 'cesium';
import { GIBS_BASE_URL, IMAGERY_LAYERS, type ImageryLayerConfig } from './config';

function createGibsProvider(config: ImageryLayerConfig): Cesium.ImageryProvider {
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
    enablePickFeatures: false,
    credit: config.attribution,
  });
}

/** Adds base layers first, then cartographic overlays, in configured order. */
export function addImageryLayers(viewer: Cesium.Viewer): Cesium.ImageryLayer[] {
  const ordered = [...IMAGERY_LAYERS].sort((a, b) => {
    if (a.role === b.role) return 0;
    return a.role === 'base' ? -1 : 1;
  });

  return ordered.map((config) => viewer.imageryLayers.addImageryProvider(createGibsProvider(config)));
}
