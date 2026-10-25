/**
 * The map journey: click the map and get an honest answer about coverage.
 *
 * The rule under test is the one the pilot rests on - a point outside the
 * supported boundaries must be *said to be* outside them, with the nearest
 * supported place named and its distance given, rather than silently shown a
 * profile that does not describe the clicked point.
 *
 * The reverse-geocode response is pinned (see `helpers.ts`) so the assertion is
 * about the app's handling. The map style is intercepted because the real one
 * comes from a third-party tile host. The click itself is real: it lands on the
 * centre of the map viewport, which is the centre MapView was given.
 */
import { expect, test } from '@playwright/test';

import { OUTSIDE_COVERAGE, mockMapStyle, mockReverseGeocode } from './helpers';

test('clicking the map outside coverage states that plainly', async ({ page }) => {
  await mockMapStyle(page);
  await mockReverseGeocode(page, OUTSIDE_COVERAGE);

  await page.goto('/?map=1');

  // MapLibre only raises click handlers once its style has loaded, so wait for
  // the canvas rather than racing it.
  const map = page.locator('.maplibre-viewport');
  await expect(map).toBeVisible();
  await page.waitForSelector('.maplibregl-canvas', { timeout: 30_000 });

  // Click the centre of the viewport, which is the point MapView is centred on.
  const box = await map.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);

  // The notice is a `role="status"`, so a screen reader announces it without
  // being focused - which is what makes it a notice rather than a silent no-op.
  const notice = page.locator('.coverage-notice[role="status"]');
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("outside Garuda's supported boundaries");
  await expect(notice).toContainText('141 km');
  await expect(notice).toContainText('Puri');

  // The assertion that matters: the app did NOT resolve the pin. The nearest
  // place in the mocked answer is Puri, so a place heading reading Puri would
  // mean the app showed statistics that do not describe the clicked point. The
  // heading must still be the place the app started on.
  await expect(page.locator('.place-name')).toHaveText('Khordha');
});
