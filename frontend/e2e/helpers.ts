import type { Page } from '@playwright/test';

/**
 * Shared E2E setup: intercept the two external dependencies so the suite is
 * deterministic and depends on no third party.
 */

/** The map style MapView loads from a public tile host. */
export const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark';

/**
 * A valid style document with no sources. MapLibre needs a style before it
 * considers itself loaded and attaches click handlers, but the tests never read
 * a tile - so a solid background is enough and the suite needs no tile host.
 */
export const MINIMAL_STYLE = {
  version: 8,
  sources: {},
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#0a0e17' },
    },
  ],
};

/** Serve the minimal style instead of the real one. */
export async function mockMapStyle(page: Page): Promise<void> {
  await page.route(MAP_STYLE_URL, (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(MINIMAL_STYLE) }),
  );
}

/**
 * Pin the reverse-geocode response.
 *
 * The point of the coverage-notice journey is the app's *handling* of an
 * out-of-coverage answer, not the geography that produces one - so the response
 * is fixed here rather than depending on where the map happens to be centred.
 * The real endpoint is covered by the backend route tests.
 */
export async function mockReverseGeocode(
  page: Page,
  response: Record<string, unknown>,
): Promise<void> {
  await page.route('**/api/v1/places/reverse**', (route) =>
    route.fulfill({
      contentType: 'application/json',
      status: 200,
      body: JSON.stringify(response),
    }),
  );
}

/**
 * A response saying the clicked point is outside the supported boundaries.
 *
 * The nearest place is deliberately *not* the place the app starts on (Khordha),
 * so the test can tell "showed the notice and changed nothing" apart from
 * "silently re-resolved the pin to the nearest boundary and showed that".
 */
export const OUTSIDE_COVERAGE = {
  place: {
    id: 'IN-OD-21',
    canonical_name: 'Puri',
    aliases: [],
    place_type: 'district',
    parent_id: 'IN-OD',
    coordinates: [19.8135, 85.8312],
    geometry_available: true,
    resolution_method: 'boundary_lookup',
  },
  match_type: 'nearest',
  distance_km: 141,
  inside_coverage: false,
  coverage_note:
    "This point is outside Garuda's supported boundaries. The nearest supported boundary, Puri, is 141 km away and its statistics do not describe this point.",
};
