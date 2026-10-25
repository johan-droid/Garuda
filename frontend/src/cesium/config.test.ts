/**
 * GIBS layers and the date a globe can honestly state.
 *
 * The globe renders NASA GIBS imagery, and the question this pins is what the
 * UI may claim about *when* it was captured. The honesty rule is that a date
 * is stated only when the layer has one:
 *
 *   - A layer with a real acquisition date states it, and that date reaches the
 *     WMTS `time` dimension.
 *   - A time-static layer says it is static, rather than being given a
 *     fabricated date or inheriting today's.
 *
 * The second is the load-bearing case. Blue Marble and the reference overlays
 * are composite products with no single acquisition date, so the previous
 * config said "no date dimension is sent" - honest, but it left the UI unable
 * to say *why* there was no date. `temporal_coverage` makes that explicit
 * instead of silent.
 */
import { describe, expect, it } from 'vitest';

import {
  IMAGERY_LAYERS,
  temporalLabel,
  wmtsTimeDimension,
  type ImageryLayerConfig,
} from './config';
import { imageryTemporalLabel } from './imagery';

function layerWith(coverage: ImageryLayerConfig['temporal_coverage']): ImageryLayerConfig {
  return { ...IMAGERY_LAYERS[0], temporal_coverage: coverage };
}

describe('a layer with a real acquisition date', () => {
  it('states the date', () => {
    const dated = layerWith({ kind: 'dated', date: '2026-02-05' });

    expect(temporalLabel(dated)).toBe('Captured 2026-02-05');
  });

  it('sends that date as the WMTS time dimension', () => {
    const dated = layerWith({ kind: 'dated', date: '2026-02-05' });

    expect(wmtsTimeDimension(dated)).toBe('2026-02-05');
  });
});

describe('a time-static layer', () => {
  it('says it is static rather than showing a date', () => {
    const staticLayer = layerWith({ kind: 'static' });

    expect(temporalLabel(staticLayer)).toBe('Static composite (no single acquisition date)');
    expect(temporalLabel(staticLayer)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it('sends no time dimension at all', () => {
    // Absent, not empty: an empty `time` is a request GIBS cannot serve.
    const staticLayer = layerWith({ kind: 'static' });

    expect(wmtsTimeDimension(staticLayer)).toBeNull();
  });
});

describe('the shipped GIBS layers', () => {
  it('every layer takes an explicit position on time', () => {
    // Silence is not allowed: a layer with no temporal_coverage is what let
    // the UI imply a date the imagery never had.
    expect(IMAGERY_LAYERS.length).toBeGreaterThan(0);
    for (const layer of IMAGERY_LAYERS) {
      expect(layer.temporal_coverage, `layer ${layer.id}`).toBeDefined();
      expect(['dated', 'static'], `layer ${layer.id}`).toContain(
        layer.temporal_coverage.kind,
      );
    }
  });

  it('are all static, because they are composites', () => {
    // Blue Marble and the reference overlays have no single acquisition date.
    // This pins the real-world answer rather than a hypothetical one.
    for (const layer of IMAGERY_LAYERS) {
      expect(layer.temporal_coverage.kind, `layer ${layer.id}`).toBe('static');
      expect(wmtsTimeDimension(layer)).toBeNull();
    }
  });

  it('the globe says static rather than inventing a date', () => {
    expect(imageryTemporalLabel()).toBe('Static composite (no single acquisition date)');
  });

  it('would state a date if a dated layer were added', () => {
    // The label follows the topmost dated layer, so adding a real daily layer
    // later changes what the UI claims without touching this logic.
    const dated = layerWith({ kind: 'dated', date: '2026-02-05' });
    expect(temporalLabel(dated)).toContain('2026-02-05');
  });
});
