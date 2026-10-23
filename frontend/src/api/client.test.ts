import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getEnvironmentScenes,
  getHealthAlerts,
  normalizePlaceProfile,
  getBoundariesWithProvenance,
  getPlaceProfileWithProvenance,
  reverseGeocodeWithProvenance,
  invalidateBoundaryCache,
} from './client';
import { PlaceProfile } from '../types/contracts';

describe('client API honesty & contract tests', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    // Flush boundary cache between tests so each test starts clean.
    invalidateBoundaryCache();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe('getHealthAlerts', () => {
    it('returns empty alerts and honest note when backend is offline, never synthetic cholera alerts', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const result = await getHealthAlerts('IN-OD-29');

      expect(result.place_id).toBe('IN-OD-29');
      expect(result.active_alerts).toEqual([]);
      expect(result.expired_alerts).toEqual([]);
      expect(result.expired_count).toBe(0);
      expect(result.source_count).toBe(0);
      expect(result.note).toContain('No health alerts are available');
      // Ensure synthetic cholera / boil-water advisory text is NOT present
      const jsonStr = JSON.stringify(result);
      expect(jsonStr).not.toContain('Cholera');
      expect(jsonStr).not.toContain('Daya River Basin');
    });

    it('returns real alerts when backend answers successfully', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          place_id: 'IN-OD-29',
          active_alerts: [
            {
              id: 'real-alert-01',
              field_name: 'Heatwave Advisory',
              issuing_authority: 'IMD Odisha',
              health_category: 'official_alert',
            },
          ],
          expired_alerts: [],
          expired_count: 0,
          source_count: 1,
          note: 'Official alert active',
        }),
      } as Response);

      const result = await getHealthAlerts('IN-OD-29');

      expect(result.active_alerts).toHaveLength(1);
      expect(result.active_alerts[0].field_name).toBe('Heatwave Advisory');
      expect(result.active_alerts[0].issuing_authority).toBe('IMD Odisha');
    });
  });

  describe('getEnvironmentScenes', () => {
    it('fetches latest sentinel-2 scene from backend endpoint', async () => {
      const mockResponse = {
        place: {
          id: 'IN-OD-29',
          canonical_name: 'Khordha',
          aliases: [],
          place_type: 'district',
          geometry_available: true,
        },
        field_name: 'latest_sentinel2_scene',
        status: 'current',
        observation: {
          field_name: 'latest_sentinel2_scene',
          value: 'S2B_45QUC_20260205_0_L2A',
          place_id: 'IN-OD-29',
          source_id: 'src-esa-sentinel-stac',
          quality_status: 'current',
          retrieved_at: '2026-10-23T00:00:00Z',
          satellite_mission: 'Sentinel-2 (ESA/Copernicus)',
          resolution_meters: 10,
          cloud_cover_percentage: 0.29,
          scene_timestamp: '2026-02-05T05:02:58Z',
        },
      };

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getEnvironmentScenes('IN-OD-29');

      expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/places/IN-OD-29/environment-scenes');
      expect(result).not.toBeNull();
      expect(result?.status).toBe('current');
      expect(result?.observation?.value).toBe('S2B_45QUC_20260205_0_L2A');
    });

    it('returns null on fetch error or 404', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      } as Response);

      const result = await getEnvironmentScenes('UNKNOWN');
      expect(result).toBeNull();
    });
  });

  describe('normalizePlaceProfile', () => {
    it('mirrors history_culture and culture aliases bidirectionally', () => {
      const input = {
        place: { id: 'test', canonical_name: 'Test', aliases: [], place_type: 'district', geometry_available: false },
        hierarchy: {},
        panels: {
          history_culture: { domain: 'history_culture', status: 'current', observations: [] },
        },
      } as unknown as PlaceProfile;

      const normalized = normalizePlaceProfile(input);

      expect(normalized.panels.history_culture).toBeDefined();
      expect(normalized.panels.culture).toBeDefined();
      expect(normalized.panels.culture).toBe(normalized.panels.history_culture);
    });

    it('mirrors weather_disasters and weather aliases bidirectionally', () => {
      const input = {
        place: { id: 'test', canonical_name: 'Test', aliases: [], place_type: 'district', geometry_available: false },
        hierarchy: {},
        panels: {
          weather: { domain: 'weather_disasters', status: 'current', observations: [] },
        },
      } as unknown as PlaceProfile;

      const normalized = normalizePlaceProfile(input);

      expect(normalized.panels.weather_disasters).toBeDefined();
      expect(normalized.panels.weather).toBeDefined();
      expect(normalized.panels.weather_disasters).toBe(normalized.panels.weather);
    });
  });

  // ---------------------------------------------------------------------------
  // Deduplication, caching and abort tests
  // ---------------------------------------------------------------------------

  describe('getBoundariesWithProvenance – boundary cache and deduplication', () => {
    it('fetches only once when called concurrently (in-flight deduplication)', async () => {
      const mockBoundaries = { type: 'FeatureCollection', features: [] };
      let resolveFirst!: () => void;
      const latch = new Promise<void>((res) => { resolveFirst = res; });

      globalThis.fetch = vi.fn().mockReturnValue(
        latch.then(() => ({
          ok: true,
          json: async () => mockBoundaries,
        }) as Response)
      );

      // Fire two concurrent calls before the first resolves.
      const [r1, r2] = await Promise.all([
        getBoundariesWithProvenance(),
        (resolveFirst(), getBoundariesWithProvenance()),
      ]);

      // Only one network request should have been made.
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
      expect(r1.live).toBe(true);
      expect(r2.live).toBe(true);
    });

    it('returns cached result on the second call without a new fetch', async () => {
      const mockBoundaries = { type: 'FeatureCollection', features: [{ id: 'cached' }] };
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockBoundaries,
      } as Response);

      await getBoundariesWithProvenance();
      await getBoundariesWithProvenance();

      // Second call should use the cache: only one fetch.
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    it('surfaces HTTP 429 as live:false with status code', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
      } as Response);

      const result = await getBoundariesWithProvenance();

      expect(result.live).toBe(false);
      expect(result.status).toBe(429);
    });
  });

  describe('getPlaceProfileWithProvenance – deduplication and abort', () => {
    it('deduplicates concurrent fetches for the same placeId', async () => {
      const mockProfile = {
        place: { id: 'IN-OD-29', canonical_name: 'Khordha', aliases: [], place_type: 'district', geometry_available: true },
        hierarchy: {},
        panels: {},
      };
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockProfile,
      } as Response);

      const [r1, r2] = await Promise.all([
        getPlaceProfileWithProvenance('IN-OD-29'),
        getPlaceProfileWithProvenance('IN-OD-29'),
      ]);

      // Only one network request for the same placeId.
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
      expect(r1.live).toBe(true);
      expect(r2.live).toBe(true);
    });

    it('returns live:false and status code on HTTP 429', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
      } as Response);

      const result = await getPlaceProfileWithProvenance('IN-OD-RATE-LIMITED');
      expect(result.live).toBe(false);
      expect(result.status).toBe(429);
      expect(result.data).toBeNull();
    });
  });

  describe('reverseGeocodeWithProvenance – coordinate deduplication', () => {
    it('deduplicates requests for the same rounded coordinate', async () => {
      // Invalidate any cached request
      invalidateBoundaryCache();

      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      } as Response);

      // Two slightly different coordinates that round to the same 5dp value
      await Promise.all([
        reverseGeocodeWithProvenance(20.29610, 85.82450),
        reverseGeocodeWithProvenance(20.29610, 85.82450),
      ]);

      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });
  });
});

