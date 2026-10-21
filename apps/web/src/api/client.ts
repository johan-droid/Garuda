import { SearchResponse, PlaceProfile } from '../types/contracts';

const API_BASE = '/api/v1';

export async function searchPlaces(query: string): Promise<SearchResponse> {
  if (!query.trim()) {
    return { query, results: [], total: 0, limit: 20, offset: 0 };
  }
  const res = await fetch(`${API_BASE}/places/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new Error(`Search failed: ${res.statusText}`);
  }
  return res.json();
}

export async function getPlaceProfile(placeId: string): Promise<PlaceProfile> {
  const res = await fetch(`${API_BASE}/places/${encodeURIComponent(placeId)}/profile`);
  if (!res.ok) {
    throw new Error(`Profile fetch failed: ${res.statusText}`);
  }
  return res.json();
}

export async function checkHealth(): Promise<{ status: string; version: string; pilot_region: string }> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error('Backend offline');
  }
  return res.json();
}
