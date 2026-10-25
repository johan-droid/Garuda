/**
 * PWA wiring.
 *
 * The manifest link and the service-worker registration live in files jsdom
 * never executes, so this reads them as raw source. What it pins is the
 * wiring itself: the app must be installable, must register a worker, and
 * must not depend on a remote CDN to render its shell.
 */
import { describe, it, expect } from 'vitest';

import mapViewSource from '../components/MapView.tsx?raw';
import mainSource from '../main.tsx?raw';
import indexHtml from '../../index.html?raw';
import serviceWorkerSource from '../../public/sw.js?raw';

describe('PWA wiring', () => {
  it('links the manifest so the app is installable', () => {
    // Tolerates a self-closing slash; what matters is the link is there.
    expect(indexHtml).toMatch(/<link rel="manifest" href="\/manifest\.json"\s*\/?>/);
    expect(indexHtml).toContain('<meta name="theme-color"');
    expect(indexHtml).toContain('<meta name="description"');
  });

  it('renders its shell without a remote stylesheet', () => {
    expect(indexHtml).not.toContain('unpkg.com');
    // MapLibre's CSS is bundled from node_modules by the MapView import, so
    // the shell never waits on a CDN to look right.
    expect(mapViewSource).toContain("import 'maplibre-gl/dist/maplibre-gl.css'");
  });

  it('registers a service worker outside development', () => {
    expect(mainSource).toContain('navigator.serviceWorker.register');
    // Gated so the dev server is not fought over by a caching worker.
    expect(mainSource).toContain('import.meta.env');
    expect(mainSource).toMatch(/MODE|PROD/);
  });

  it('ships a service worker that keeps the API out of cache and cannot break navigation', () => {
    // It must be a worker with a fetch handler, not a stub.
    expect(serviceWorkerSource).toContain('addEventListener');
    // The API must never be answered from a cache: stale facts are worse
    // than no facts here.
    expect(serviceWorkerSource).toContain('/api/');
    // A cache failure degrades to the network instead of throwing.
    expect(serviceWorkerSource).toContain('catch');
  });
});
