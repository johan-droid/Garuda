export type PlaceType = 'state' | 'district' | 'subdistrict' | 'village' | 'point';

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
}

export interface SourceSummary {
  source_id: string;
  publisher: string;
  name: string;
  url?: string | null;
  licence?: string | null;
  verification_status: string;
}

export interface Observation {
  field_name: string;
  value: number | string | null;
  unit?: string | null;
  place_id: string;
  source_id: string;
  quality_status: string;
  licence?: string | null;
  retrieved_at: string;
}

export interface PlaceProfile {
  place: Place;
  hierarchy: {
    ancestors?: Place[];
  };
  panels: Record<string, {
    status: string;
    observations?: Observation[];
    error?: string | null;
    data_gaps?: string[];
  }>;
}
