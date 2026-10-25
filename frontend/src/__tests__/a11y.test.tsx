/**
 * Accessibility assertions over the rendered UI.
 *
 * The rule this encodes is that the page must be usable without a pointer:
 * every control has an accessible name, a keyboard user can reach the primary
 * controls, and motion is suppressed for a reader who has asked for that.
 *
 * Two findings are load-bearing rather than cosmetic:
 *
 *   - `axe` runs over the *real* rendered page, so a missing label is a test
 *     failure rather than a review comment. The search input and the modal
 *     close button both shipped without an accessible name - a reader who
 *     tabs to them hears "edit text" and "button" with no idea what they do.
 *   - `prefers-reduced-motion` is asserted against the stylesheet source,
 *     because jsdom cannot observe a media query taking effect.
 *
 * Named `.test.tsx` rather than the brief's `.ts`: this file renders React, and
 * every other React-rendering test in this repo is `.tsx` (`App.test.tsx`,
 * `HomePage.test.tsx`). The vitest glob picks up both.
 *
 * Keyboard reachability is asserted from the tabbable element set rather than
 * by simulating Tab: jsdom does not implement focus traversal, so a simulated
 * Tab would be a test of my own code instead of the page.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axe from 'axe-core';

vi.mock('../components/MapView', () => ({
  // MapLibre needs WebGL and a real canvas. The test only needs the click
  // callback the page wires into the map.
  MapView: ({ onPlaceClick }: { onPlaceClick?: (lat: number, lng: number) => void }) => (
    <button type="button" onClick={() => onPlaceClick?.(28.6139, 77.209)}>
      mock-map
    </button>
  ),
}));

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    checkHealth: vi.fn(),
    searchPlaces: vi.fn(),
    getPlaceProfile: vi.fn(),
    getHealthAlerts: vi.fn(),
    getEnvironmentScenes: vi.fn(),
    reverseGeocodeWithProvenance: vi.fn(),
    getSourceDiagnostics: vi.fn(),
  };
});

import * as api from '../api/client';
import { HomePage } from '../pages/HomePage';
import type { PlaceProfile, SearchResponse } from '../types/contracts';

import indexCss from '../styles/index.css?raw';

const khordha = api.PILOT_PLACES[1];

function emptySearchResults(query = ''): SearchResponse {
  return { query, results: [], total: 0, limit: 20, offset: 0 };
}

function emptyProfile(): PlaceProfile {
  return {
    place: khordha,
    hierarchy: { state: 'Odisha', district: 'Khordha' },
    panels: {},
  };
}

/** Render the page the way a reader gets it, with only network and WebGL stubbed. */
async function renderPage(profile: PlaceProfile = emptyProfile()) {
  vi.mocked(api.checkHealth).mockResolvedValue({
    status: 'ok',
    checks: {},
  } as unknown as Awaited<ReturnType<typeof api.checkHealth>>);
  vi.mocked(api.getPlaceProfile).mockResolvedValue(profile);
  vi.mocked(api.searchPlaces).mockResolvedValue(emptySearchResults());

  const rendered = render(<HomePage />);
  await screen.findByPlaceholderText(/search place/i);
  return rendered;
}

/** WCAG A and AA, which is what a public-sector UI is held to. */
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/**
 * `color-contrast` is disabled: jsdom does not apply stylesheet rules, so it
 * returns the initial `canvastext` for every element and axe's rule throws
 * (`_isIconLigature`) instead of reporting. Contrast is audited by
 * `contrast.test.ts`, which computes it from the values the stylesheet declares.
 */
const RULES = { rules: { 'color-contrast': { enabled: false } } };

function violationsOf(result: axe.AxeResults) {
  return result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.map((n) => n.target.join(' ')),
  }));
}

afterEach(cleanup);

describe('the page has no WCAG A/AA violations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('on the default rendered page', async () => {
    const { container } = await renderPage();
    const result = await axe.run(container, { runOnly: WCAG_TAGS });

    expect(violationsOf(result)).toEqual([]);
  });

  it('when a profile cannot be loaded, so the error state is accessible too', async () => {
    vi.mocked(api.checkHealth).mockResolvedValue({
      status: 'unavailable',
      checks: {},
    } as unknown as Awaited<ReturnType<typeof api.checkHealth>>);
    vi.mocked(api.getPlaceProfile).mockRejectedValue(new Error('backend down'));

    const { container } = render(<HomePage />);
    await screen.findByText(/PLACE INTELLIGENCE — NOT AVAILABLE/i);

    const result = await axe.run(container, { runOnly: WCAG_TAGS, ...RULES });
    expect(violationsOf(result)).toEqual([]);
  });

  it('when the provenance modal is open, so its table and close control are checked', async () => {
    await renderPage();
    fireEvent.click(screen.getByRole('button', { name: /diagnostics/i }));

    const dialog = await screen.findByRole('dialog');
    const result = await axe.run(dialog, { runOnly: WCAG_TAGS, ...RULES });
    expect(violationsOf(result)).toEqual([]);
  });
});

describe('every control has an accessible name', () => {
  it('the search input is labelled, so it is not announced as a bare edit box', async () => {
    await renderPage();

    // A placeholder is not a label: it disappears on the first keystroke.
    expect(screen.getByRole('textbox', { name: /search place/i })).toBeTruthy();
  });

  it('the modal close button is named, so it is not just "button"', async () => {
    await renderPage();
    fireEvent.click(screen.getByRole('button', { name: /diagnostics/i }));

    // The button's visible content is a glyph, which is not a name.
    expect(screen.getByRole('button', { name: 'Close diagnostics panel' })).toBeTruthy();
  });
});

describe('keyboard use', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('puts the search input in the tabbable set', async () => {
    await renderPage();

    // jsdom does not implement focus traversal, so this asserts what a real
    // browser does with the markup: the field is reachable, and nothing has
    // pulled it out of the tab order.
    const search = screen.getByPlaceholderText(/search place/i);
    expect(search.getAttribute('tabindex')).not.toBe('-1');

    const tabbable = Array.from(
      document.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    );
    expect(tabbable).toContain(search);
  });

  it('focuses and searches from the keyboard, without a pointer', async () => {
    vi.mocked(api.searchPlaces).mockResolvedValue(emptySearchResults('khordha'));
    await renderPage();

    const search = screen.getByPlaceholderText(/search place/i);
    search.focus();
    expect(document.activeElement).toBe(search);

    fireEvent.change(search, { target: { value: 'khordha' } });

    await waitFor(() => expect(api.searchPlaces).toHaveBeenCalledWith('khordha'));
    expect((search as HTMLInputElement).value).toBe('khordha');
  });
});

describe('reduced motion', () => {
  it('declares a prefers-reduced-motion block that turns animation off', () => {
    expect(indexCss).toContain('prefers-reduced-motion');
    // The rule must actually disable motion, not merely name the query.
    expect(indexCss).toMatch(/prefers-reduced-motion:\s*reduce[\s\S]*?animation:\s*none/);
  });
});
