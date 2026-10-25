/**
 * The reader journey: find a place, read its profile, take the report away.
 *
 * Driven against the real backend and the real Vite dev server - only the map
 * style is intercepted, because that is the one thing that would otherwise make
 * the suite depend on a third-party tile host.
 */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

import { mockMapStyle } from './helpers';

test.beforeEach(async ({ page }) => {
  await mockMapStyle(page);
});

test('searches a place, opens its profile, and exports the report', async ({ page }) => {
  // The default landing is the Cesium globe; the search, profile and export UI
  // lives on the 2D map, which is what `?map=1` selects.
  await page.goto('/?map=1');

  // The search field is the entry point, and it carries an accessible name
  // (added with the a11y work) - which is what this locator relies on.
  const search = page.getByLabel(/search place, district, block, or alias/i);
  await search.fill('khordha');

  // Results are rendered as clickable rows; the first is Khordha district.
  const results = page.locator('.search-result-item');
  await expect(results.first()).toBeVisible();
  await results.first().click();

  // The profile is the point of the search: the place name becomes a heading
  // rather than a search result.
  await expect(page.locator('.place-name')).toHaveText('Khordha');

  // The provenance table is what makes a figure auditable, so assert it is
  // reachable before exporting.
  await page.getByRole('button', { name: /view provenance/i }).click();
  await expect(page.getByRole('dialog')).toContainText('Evidence & Data Provenance');
  await page.getByRole('button', { name: /close evidence panel/i }).click();

  // Export produces a Markdown file named for the place and the date.
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /export report/i }).click(),
  ]);

  expect(download.suggestedFilename()).toMatch(
    /^garuda-report-IN-OD-29-\d{4}-\d{2}-\d{2}\.md$/,
  );

  // The file must be a report about the place that was searched for, not an
  // empty artefact.
  const path = await download.path();
  expect(path).toBeTruthy();
  const report = readFileSync(path as string, 'utf8');
  expect(report).toContain('Khordha');
  expect(report.length).toBeGreaterThan(200);
});
