import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getEnvironmentScenes,
  getHealthAlerts,
  normalizePlaceProfile,
} from './client';
import { PlaceProfile } from '../types/contracts';

describe('client API honesty & contract tests', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
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
});
