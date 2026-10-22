import './env';
import * as Cesium from 'cesium';
import type { TerrainSource, TerrariumTerrainSource } from './config';

/**
 * Decodes Terrarium RGB into metres: `(r * 256 + g + b / 256) - 32768`.
 * Box-filters `srcSize` -> `dstSize` in the same pass (integer ratio only),
 * which keeps adjacent tiles seamless because no edge pixel is clamped.
 */
export function decodeTerrariumHeights(
  rgba: Uint8ClampedArray,
  srcSize: number,
  dstSize: number,
): Float32Array {
  const ratio = srcSize / dstSize;
  if (!Number.isInteger(ratio) || ratio < 1) {
    throw new Error(`heightmap resolution ${dstSize} must evenly divide tile size ${srcSize}`);
  }

  const heights = new Float32Array(dstSize * dstSize);
  const samples = ratio * ratio;

  for (let y = 0; y < dstSize; y++) {
    for (let x = 0; x < dstSize; x++) {
      let sum = 0;
      for (let dy = 0; dy < ratio; dy++) {
        const rowStart = (y * ratio + dy) * srcSize;
        for (let dx = 0; dx < ratio; dx++) {
          const p = (rowStart + x * ratio + dx) * 4;
          sum += rgba[p] * 256 + rgba[p + 1] + rgba[p + 2] / 256 - 32768;
        }
      }
      heights[y * dstSize + x] = sum / samples;
    }
  }

  return heights;
}

/**
 * Cesium keeps refining until the tile's geometric error drops below the
 * screen-space threshold. The host only publishes up to `maximumLevel`, so
 * report a huge error at that level to stop the quadtree requesting 404s.
 */
class CappedHeightmapTerrainProvider extends Cesium.CustomHeightmapTerrainProvider {
  private readonly maxLevel: number;

  constructor(
    options: ConstructorParameters<typeof Cesium.CustomHeightmapTerrainProvider>[0],
    maxLevel: number,
  ) {
    super(options);
    this.maxLevel = maxLevel;
  }

  getLevelMaximumGeometricError(level: number): number {
    if (level >= this.maxLevel) {
      return 1e12;
    }
    return super.getLevelMaximumGeometricError(level);
  }
}

function createTerrariumProvider(source: TerrariumTerrainSource): Cesium.TerrainProvider {
  const canvas = document.createElement('canvas');
  canvas.width = source.tileSize;
  canvas.height = source.tileSize;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) {
    throw new Error('2D canvas context unavailable; cannot decode terrain tiles');
  }

  const callback = async (x: number, y: number, level: number): Promise<Float32Array> => {
    const url = source.urlTemplate
      .replace('{z}', String(level))
      .replace('{x}', String(x))
      .replace('{y}', String(y));

    const response = await fetch(url);
    if (response.status === 404) {
      // Mapterhorn returns 404 for tiles with no elevation data (open ocean and
      // a few Arctic voids). Sea level is the honest fill; failing the whole
      // terrain provider over an empty ocean tile would blank the globe.
      // ponytail: 404 == "no data", not "== ocean" in theory; revisit if a real
      // land coverage gap ever appears.
      return new Float32Array(source.heightmapResolution * source.heightmapResolution);
    }
    if (!response.ok) {
      throw new Error(`terrain tile ${level}/${x}/${y} -> HTTP ${response.status}`);
    }

    const bitmap = await createImageBitmap(await response.blob());
    context.clearRect(0, 0, source.tileSize, source.tileSize);
    context.drawImage(bitmap, 0, 0);
    bitmap.close();

    const { data } = context.getImageData(0, 0, source.tileSize, source.tileSize);
    return decodeTerrariumHeights(data, source.tileSize, source.heightmapResolution);
  };

  return new CappedHeightmapTerrainProvider(
    {
      // 512 px source tiles, 128 px heightmaps (4:1 box filter).
      width: source.heightmapResolution,
      height: source.heightmapResolution,
      // Mapterhorn is slippy-map (y grows south); Cesium's WebMercatorTilingScheme
      // uses the same origin, so no y flip is needed.
      tilingScheme: new Cesium.WebMercatorTilingScheme(),
      credit: source.attribution,
      callback,
    },
    source.maximumLevel,
  );
}

export interface TerrainSetup {
  provider: Cesium.TerrainProvider;
  /** False when we deliberately fell back to a bare ellipsoid. */
  hasElevation: boolean;
  /** Only terrain providers raise tile errors; ellipsoid has none. */
  errorEvent: Cesium.Event | undefined;
}

export function createTerrain(source: TerrainSource): TerrainSetup {
  if (source.kind === 'terrarium') {
    const provider = createTerrariumProvider(source);
    return {
      provider,
      hasElevation: true,
      errorEvent: (provider as Cesium.CustomHeightmapTerrainProvider).errorEvent,
    };
  }

  return {
    provider: new Cesium.EllipsoidTerrainProvider(),
    hasElevation: false,
    errorEvent: undefined,
  };
}
