import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests for the two reader journeys the pilot is about:
 *
 *   1. search a place -> open its profile -> export the report
 *   2. click the map -> get an honest coverage notice when the point is outside
 *      the supported boundaries
 *
 * Run with `npm run test:e2e` from `frontend/`. Both servers are started for
 * you; the backend also creates and seeds its database, and both steps are
 * idempotent so a re-run starts clean.
 *
 * The map needs a style document from a tile host. That is intercepted in the
 * test (see `e2e/helpers.ts`) so the suite depends on no third party and does
 * not break when a free tile host changes its terms.
 */
export default defineConfig({
  testDir: './e2e',
  // A map click plus a profile fan-out to several providers is slow; the default
  // 5s per assertion is not enough on a cold start.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  // Re-running a failed suite should not also report the passes it already had.
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    // Deliberately not 5173, which is the dev server and the published container
    // port. Reusing whatever is already on 5173 would make the suite pass or
    // fail depending on what else happens to be running - including a stale
    // container serving an older bundle.
    baseURL: 'http://127.0.0.1:5199',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      // `create_app()` does not create tables, so the schema is made here.
      // `init_db` is `create_all` and `seed_pilot` writes with `session.merge`,
      // so both are safe to run on every start.
      command: [
        '.venv/bin/python -m app.db.init_db',
        '.venv/bin/python backend/seed_pilot.py',
        '.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000',
      ].join(' && '),
      cwd: '..',
      env: { PYTHONPATH: 'backend' },
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
    {
      // `--host 127.0.0.1` because Vite otherwise binds to `localhost`, which
      // resolves to `::1` here; the readiness check against 127.0.0.1 then never
      // connects and the suite times out waiting for a server that is running.
      command: 'npm run dev -- --port 5199 --strictPort --host 127.0.0.1',
      url: 'http://127.0.0.1:5199',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
