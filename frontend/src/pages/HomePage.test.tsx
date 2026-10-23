/**
 * Tests for the three places where the UI must not claim more than the backend
 * knows: the notice shown for a pin outside the supported boundaries, the
 * "not available" card when a profile cannot be loaded, and the per-panel
 * status badges.
 *
 * HomePage is rendered for real; only the network client and the WebGL map are
 * replaced, so the assertions cover the behaviour a user actually sees.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
import { HomePage } from './HomePage';
import { Observation, PlaceProfile } from '../types/contracts';

const khordha = api.PILOT_PLACES[1];
const delhi = {
  ...api.PILOT_PLACES[0],
  id: 'IN-DL',
  canonical_name: 'Delhi',
  coordinates: [28.6139, 77.209] as [number, number],
};

function observation(field: string, value: number | string): Observation {
  return {
    field_name: field,
    value,
    place_id: khordha.id,
    source_id: 'src-census-2011',
    quality_status: 'historical',
    retrieved_at: '2026-10-21T00:00:00Z',
    reference_period_end: '2011-12-31',
  };
}

function profile(panels: PlaceProfile['panels']): PlaceProfile {
  return {
    place: khordha,
    hierarchy: { state: 'Odisha', district: 'Khordha' },
    panels,
  };
}

/** Empty profile: enough for the page to render without a "not available" card. */
function emptyProfile(): PlaceProfile {
  return profile({});
}

function renderPage() {
  return render(<HomePage />);
}

/** Wait until the initial profile has loaded, so the header shows the place. */
async function waitForPlace(container: HTMLElement, name: string) {
  await waitFor(() => expect(container.querySelector('.place-name')?.textContent).toBe(name));
}

function outOfCoverage(note: string | null) {
  return {
    data: {
      place: delhi,
      inside_coverage: false,
      distance_km: 1214.5,
      coverage_note: note,
    },
    live: true,
  };
}

// Testing Library only auto-cleans when its globals are enabled, and this
// config keeps them off, so unmount explicitly between tests.
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
});

describe('coverage notice', () => {
  it('shows the backend caveat for a pin outside the pilot and keeps the current place', async () => {
    const note =
      'Pin is 1,215 km outside the pilot boundaries. Garuda has no data for this point.';
    vi.mocked(api.reverseGeocodeWithProvenance).mockResolvedValue(outOfCoverage(note));

    const { container } = renderPage();
    await waitForPlace(container, 'Khordha');

    fireEvent.click(screen.getByText('mock-map'));

    const notice = await screen.findByRole('status');
    expect(notice.className).toContain('coverage-notice');
    expect(notice.textContent).toBe(note);
    // The out-of-coverage pin must not become the selected place.
    expect(container.querySelector('.place-name')?.textContent).toBe('Khordha');
  });

  it('falls back to the clicked coordinates when the backend sends no note', async () => {
    vi.mocked(api.reverseGeocodeWithProvenance).mockResolvedValue(outOfCoverage(null));

    const { container } = renderPage();
    await waitForPlace(container, 'Khordha');

    fireEvent.click(screen.getByText('mock-map'));

    const notice = await screen.findByRole('status');
    expect(notice.textContent).toBe(
      "28.614, 77.209 is outside Garuda's supported boundaries.",
    );
  });
});

describe('not-available card', () => {
  it('states that nothing is generated when the profile cannot be loaded', async () => {
    vi.mocked(api.getPlaceProfile).mockRejectedValue(new Error('404'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    const { container } = renderPage();

    await waitFor(() => {
      const card = container.querySelector('.card.card-unavailable');
      expect(card).not.toBeNull();
    });
    const card = container.querySelector('.card.card-unavailable') as HTMLElement;
    expect(card.querySelector('.card-title')?.textContent).toContain(
      'PLACE INTELLIGENCE — NOT AVAILABLE',
    );
    expect(card.textContent).toContain('Nothing is generated to fill the gap.');
    expect(card.querySelector('.badge')?.textContent).toBe('UNAVAILABLE');
    // No invented figures may stand in for the missing profile.
    expect(card.textContent).not.toMatch(/\d{2,}/);
  });
});

describe('panel status badges', () => {
  it('labels each panel from its own status, with the reference year when present', async () => {
    vi.mocked(api.getPlaceProfile).mockResolvedValue(
      profile({
        demographics: {
          domain: 'demographics',
          status: 'historical',
          observations: [observation('total_population', 2246341)],
        },
        services: { domain: 'services', status: 'unavailable', data_gaps: ['No UDISE+ data'] },
        environment: { domain: 'environment', status: 'approximate' },
      }),
    );

    renderPage();

    const historical = await screen.findByText('Historical (2011)');
    expect(historical.className).toBe('badge badge-hist');

    const unavailable = screen.getByText('Unavailable');
    expect(unavailable.className).toBe('badge badge-unavail');

    const approximate = screen.getByText('Approximate');
    expect(approximate.className).toBe('badge badge-hist');

    // A panel with no reference period must not gain a year it does not have.
    expect(screen.queryByText('Unavailable (2011)')).toBeNull();
  });
});

describe('sentinel-2 scene metadata & weather formatting', () => {
  it('renders satellite scene metadata when environment scene is available', async () => {
    vi.mocked(api.getPlaceProfile).mockResolvedValue(
      profile({
        environment: { domain: 'environment', status: 'current', observations: [] },
      }),
    );
    vi.mocked(api.getEnvironmentScenes).mockResolvedValue({
      place: khordha,
      field_name: 'latest_sentinel2_scene',
      status: 'current',
      observation: {
        field_name: 'latest_sentinel2_scene',
        value: 'S2B_45QUC_20260205_0_L2A',
        place_id: khordha.id,
        source_id: 'src-esa-sentinel-stac',
        quality_status: 'current',
        retrieved_at: '2026-10-23T00:00:00Z',
        satellite_mission: 'Sentinel-2 (ESA/Copernicus)',
        resolution_meters: 10,
        cloud_cover_percentage: 0.29,
        scene_timestamp: '2026-02-05T05:02:58Z',
      },
    });

    renderPage();

    const title = await screen.findByText('🛰️ Sentinel-2 Satellite Scene Metadata');
    expect(title).not.toBeNull();
    expect(screen.getByText('Sentinel-2 (ESA/Copernicus)')).not.toBeNull();
    expect(screen.getByText('0.29%')).not.toBeNull();
    expect(screen.getByText('10m')).not.toBeNull();
  });

  it('renders clean N/A without orphan degree celsius when temperature is unavailable', async () => {
    vi.mocked(api.getPlaceProfile).mockResolvedValue(
      profile({
        weather_disasters: {
          domain: 'weather_disasters',
          status: 'current',
          observations: [],
        },
      }),
    );

    renderPage();

    const tempLabel = await screen.findByText('Temperature');
    const cell = tempLabel.closest('.metric-cell');
    expect(cell).not.toBeNull();
    // It should render "N/A" and NOT "N/A °C"
    expect(cell?.textContent).toContain('N/A');
    expect(cell?.textContent).not.toContain('N/A °C');
  });
});
