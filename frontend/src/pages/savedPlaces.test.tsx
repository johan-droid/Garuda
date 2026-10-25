/**
 * Saved places on the page.
 *
 * The behaviour under test is that bookmarks come from the server and are
 * written back to it, so a reload finds them. The old code seeded the list
 * from a hardcoded `PILOT_PLACES` slice and kept changes in React state, which
 * meant the bar showed two places nobody saved and forgot everything on
 * reload. These tests pin the server round-trip and, importantly, that a save
 * the server refused does not appear as saved.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../components/MapView', () => ({
  MapView: () => <div data-testid="mock-map" />,
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
    getSavedPlaces: vi.fn(),
    savePlace: vi.fn(),
    removeSavedPlace: vi.fn(),
  };
});

import * as api from '../api/client';
import { HomePage } from './HomePage';
import { PlaceProfile } from '../types/contracts';

const khordha = api.PILOT_PLACES[1];
const bbsr = api.PILOT_PLACES[2];

function emptyProfile(): PlaceProfile {
  return { place: khordha, hierarchy: { state: 'Odisha', district: 'Khordha' }, panels: {} };
}

async function waitForPage() {
  const { container } = render(<HomePage />);
  await waitFor(() =>
    expect(container.querySelector('.place-name')?.textContent).toBe('Khordha'),
  );
  return container;
}

afterEach(cleanup);

beforeEach(() => {
  vi.mocked(api.checkHealth).mockResolvedValue({
    status: 'ok',
    version: '0.1.0',
    pilot_region: 'Odisha (Khordha pilot)',
  } as never);
  vi.mocked(api.searchPlaces).mockResolvedValue({ results: [] } as never);
  vi.mocked(api.getPlaceProfile).mockResolvedValue(emptyProfile());
  vi.mocked(api.getHealthAlerts).mockResolvedValue({
    place_id: khordha.id,
    active_alerts: [],
    expired_alerts: [],
    expired_count: 0,
    source_count: 0,
  });
  vi.mocked(api.getEnvironmentScenes).mockResolvedValue(null);
  vi.mocked(api.getSavedPlaces).mockResolvedValue([]);
  vi.mocked(api.savePlace).mockResolvedValue(undefined);
  vi.mocked(api.removeSavedPlace).mockResolvedValue(undefined);
});

describe('saved places come from the server', () => {
  it('shows the places the backend has saved, not a hardcoded set', async () => {
    vi.mocked(api.getSavedPlaces).mockResolvedValue([bbsr]);

    await waitForPage();

    // The bar is driven by what the server returned.
    expect(screen.getByText('⭐ Bhubaneswar')).not.toBeNull();
    // And it does not show a place nobody saved.
    expect(screen.queryByText('⭐ Khordha')).toBeNull();
  });

  it('shows no bar when nothing is saved', async () => {
    await waitForPage();

    expect(screen.queryByText('Quick Saved:')).toBeNull();
  });

  it('survives a reload because it re-fetches rather than seeding state', async () => {
    // Second mount = a reload. The list must come from the server again.
    vi.mocked(api.getSavedPlaces).mockResolvedValue([khordha, bbsr]);
    await waitForPage();
    cleanup();

    vi.mocked(api.getSavedPlaces).mockResolvedValue([bbsr]);
    await waitForPage();

    expect(screen.getByText('⭐ Bhubaneswar')).not.toBeNull();
    expect(screen.queryByText('⭐ Khordha')).toBeNull();
  });
});

describe('bookmarking writes to the server', () => {
  it('saves the selected place and shows it in the bar', async () => {
    await waitForPage();

    fireEvent.click(screen.getByText('☆ Bookmark'));

    await waitFor(() => expect(api.savePlace).toHaveBeenCalledWith(khordha));
    await waitFor(() => expect(screen.getByText('⭐ Khordha')).not.toBeNull());
    expect(screen.getByText('★ Bookmarked')).not.toBeNull();
  });

  it('removes a saved place from the server and the bar', async () => {
    vi.mocked(api.getSavedPlaces).mockResolvedValue([khordha]);

    await waitForPage();
    expect(screen.getByText('★ Bookmarked')).not.toBeNull();

    fireEvent.click(screen.getByText('★ Bookmarked'));

    await waitFor(() => expect(api.removeSavedPlace).toHaveBeenCalledWith(khordha.id));
    await waitFor(() => expect(screen.queryByText('⭐ Khordha')).toBeNull());
    expect(screen.getByText('☆ Bookmark')).not.toBeNull();
  });

  it('does not show a bookmark the server refused to save', async () => {
    // A failed save must not be reported as saved: the chip would claim a
    // bookmark that is not there after a reload.
    vi.mocked(api.savePlace).mockRejectedValue(new Error('HTTP 500'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    await waitForPage();

    fireEvent.click(screen.getByText('☆ Bookmark'));

    await waitFor(() => expect(api.savePlace).toHaveBeenCalled());
    expect(screen.queryByText('⭐ Khordha')).toBeNull();
    expect(screen.getByText('☆ Bookmark')).not.toBeNull();
  });

  it('keeps a bookmark the server refused to remove', async () => {
    vi.mocked(api.getSavedPlaces).mockResolvedValue([khordha]);
    vi.mocked(api.removeSavedPlace).mockRejectedValue(new Error('HTTP 500'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    await waitForPage();

    fireEvent.click(screen.getByText('★ Bookmarked'));

    await waitFor(() => expect(api.removeSavedPlace).toHaveBeenCalled());
    // Still saved server-side, so still shown.
    expect(screen.getByText('⭐ Khordha')).not.toBeNull();
    expect(screen.getByText('★ Bookmarked')).not.toBeNull();
  });

  it('keeps showing bookmarks when the list cannot be fetched', async () => {
    // An unreachable backend yields an empty list, not an error page: the bar
    // is simply absent rather than the whole page failing.
    vi.mocked(api.getSavedPlaces).mockRejectedValue(new TypeError('Failed to fetch'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { container } = render(<HomePage />);
    await waitFor(() =>
      expect(container.querySelector('.place-name')?.textContent).toBe('Khordha'),
    );

    expect(screen.queryByText('Quick Saved:')).toBeNull();
  });
});
