export type PlaceType = 'state' | 'district' | 'subdistrict' | 'block' | 'village' | 'point';

export interface Place {
  id: string;
  canonical_name: string;
  aliases: string[];
  place_type: PlaceType;
  parent_id?: string | null;
  coordinates?: [number, number] | null; // [latitude, longitude]
  resolution_method?: string | null;
  geometry_available: boolean;
}

export interface AdminHierarchy {
  state?: string | null;
  district?: string | null;
  subdistrict?: string | null;
  block?: string | null;
  village?: string | null;
  ancestors?: Place[];
}

export interface SearchResult {
  place: Place;
  score: number;
  match_type: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  limit: number;
  offset: number;
  degraded?: boolean;
  notes?: string[];
}

export interface SourceSummary {
  source_id: string;
  publisher: string;
  name: string;
  url?: string | null;
  licence?: string | null;
  reference_period?: string | null;
  retrieved_at?: string;
  verification_status: string;
}

export interface HealthAlert {
  id?: string;
  field_name?: string;
  value?: number | string | null;
  unit?: string | null;
  health_category?: string;
  issuing_authority: string;
  valid_from?: string | null;
  valid_until?: string | null;
  affected_geography_level?: string | null;
  severity?: 'low' | 'moderate' | 'high' | 'critical' | string | null;
  disease_code?: string | null;
  prevention_link?: string | null;
  prevention_link_date?: string | null;
  expired?: boolean;
  notes?: string | null;
  source_id?: string;
  licence?: string | null;
  retrieved_at?: string;
}

export interface HealthAlertsResponse {
  place_id: string;
  active_alerts: HealthAlert[];
  expired_alerts?: HealthAlert[];
  expired_count: number;
  source_count: number;
  note?: string;
}

export interface Observation {
  field_name: string;
  value: number | string | null;
  unit?: string | null;
  place_id: string;
  source_id: string;
  quality_status: string; // 'current' | 'historical' | 'stale' | 'approximate' | 'unverified'
  licence?: string | null;
  retrieved_at: string;
  reference_period_start?: string | null;
  reference_period_end?: string | null;
  published_at?: string | null;
  notes?: string | null;
  domain?: string | null;
  /** Link to the record the value came from, when the source publishes one. */
  source_url?: string | null;

  // Health-specific extended fields
  health_category?: string;
  issuing_authority?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  severity?: string | null;
  disease_code?: string | null;
  prevention_link?: string | null;
  prevention_link_date?: string | null;
  expired?: boolean;

  // Environment & Satellite observations
  satellite_mission?: string | null;
  resolution_meters?: number | null;
  cloud_cover_percentage?: number | null;
  scene_timestamp?: string | null;

  // History & Culture observations
  monument_id?: string | null;
  historical_period?: string | null;
  citation?: string | null;
}

export interface PanelResponse {
  domain: string;
  status: 'current' | 'historical' | 'stale' | 'unavailable' | 'unverified' | string;
  observations?: Observation[];
  sources?: SourceSummary[];
  last_updated?: string | null;
  coverage_note?: string | null;
  data_gaps?: string[];
  error?: string | null;
}

export interface PlaceProfile {
  place: Place;
  hierarchy: AdminHierarchy;
  panels: Record<string, PanelResponse>;
  retrieved_at?: string;
}

export interface SourceDiagnosticItem {
  source_id: string;
  publisher: string;
  name: string;
  url?: string | null;
  licence?: string | null;
  verification_status: string;
  status: 'connected' | 'degraded' | 'offline' | 'ok';
  records_served: number;
  latency_ms?: number;
  last_sync?: string | null;
  access_mode?: string;
}

export interface SourceDiagnostics {
  timestamp: string;
  total_sources: number;
  active_sources: number;
  sources: SourceDiagnosticItem[];
}

export interface ReverseGeocodeResult {
  place: Place;
  hierarchy?: AdminHierarchy;
  distance_meters?: number;
  confidence?: number;
}

// GeoJSON Types
export type GeoJsonGeometryType =
  | 'Point'
  | 'MultiPoint'
  | 'LineString'
  | 'MultiLineString'
  | 'Polygon'
  | 'MultiPolygon'
  | 'GeometryCollection';

export interface GeoJsonGeometry {
  type: GeoJsonGeometryType;
  coordinates: any;
}

export interface BoundaryProperties {
  id: string;
  name: string;
  level: 'state' | 'district' | 'block' | 'subdistrict' | 'village';
  parent_id?: string | null;
  centroid?: [number, number]; // [lat, lng]
  [key: string]: any;
}

/**
 * Shape actually returned by `GET /api/v1/places/boundaries` (see
 * backend/app/services/boundary_service.py). `BoundaryProperties` above
 * declares `name`/`level`, which the backend does not emit.
 */
export interface LiveBoundaryProperties {
  id: string;
  canonical_name: string;
  place_type: string;
  parent_id?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface GeoJsonFeature<P = BoundaryProperties> {
  type: 'Feature';
  id?: string | number;
  geometry: GeoJsonGeometry;
  properties: P;
}

export interface GeoJsonFeatureCollection<P = BoundaryProperties> {
  type: 'FeatureCollection';
  features: GeoJsonFeature<P>[];
}

export type LiveBoundaryCollection = GeoJsonFeatureCollection<LiveBoundaryProperties>;
