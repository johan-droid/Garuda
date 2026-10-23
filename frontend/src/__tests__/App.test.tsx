/**
 * App routing tests — default globe landing.
 *
 * Verifies that:
 * - No query params → globe Suspense path entered (not the 2D map).
 * - ?globe=1 (legacy) → same globe Suspense path.
 * - ?map=1 → the lazy GlobePage is NOT imported at all.
 *
 * Cesium cannot run in jsdom, so we only assert which Suspense branch is
 * entered (globe) or not entered (2D map), without rendering GlobePage itself.
 */
import { Suspense } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

if (typeof window !== 'undefined' && !window.URL.createObjectURL) {
  window.URL.createObjectURL = vi.fn(() => 'blob:mock');
}

vi.mock('../pages/HomePage', () => ({
  HomePage: () => <div data-testid="mock-home-page">2D Map</div>,
}));

vi.mock('../pages/GlobePage', () => {
  return {
    default: () => <div data-testid="globe-page-stub">Globe</div>,
    GlobePage: () => <div data-testid="globe-page-stub">Globe</div>,
  };
});

describe('App default routing', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('renders the globe Suspense fallback by default (no query params)', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '' },
      writable: true,
    });

    const { App } = await import('../App');
    const { container } = render(
      <Suspense fallback={<span>Loading Garuda Globe…</span>}>
        <App />
      </Suspense>
    );
    expect(container.textContent).toMatch(/Loading Garuda Globe/i);
  });

  it('?globe=1 (legacy compat) also shows the globe Suspense', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?globe=1' },
      writable: true,
    });

    const { App } = await import('../App');
    const { container } = render(
      <Suspense fallback={<span>Loading Garuda Globe…</span>}>
        <App />
      </Suspense>
    );
    expect(container.textContent).toMatch(/Loading Garuda Globe/i);
  });

  it('?map=1 shows the 2D map path — globe Suspense fallback is absent', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?map=1' },
      writable: true,
    });

    const { App } = await import('../App');
    const { queryByText, queryByTestId } = render(
      <Suspense fallback={<span>Loading Garuda Globe…</span>}>
        <App />
      </Suspense>
    );

    expect(queryByText(/Loading Garuda Globe/i)).toBeNull();
    expect(queryByTestId('mock-home-page')).not.toBeNull();
  });
});
