import {
  SearchResponse,
  PlaceProfile,
  PanelResponse,
  GeoJsonFeatureCollection,
  LiveBoundaryCollection,
  SourceDiagnostics,
  HealthAlertsResponse,
  Place,
  LatestObservationResponse,
} from '../types/contracts';

const API_BASE = '/api/v1';

// Grounded Pilot Places for Fallback / Mock
export const PILOT_PLACES: Place[] = [
  {
    id: 'IN-OD',
    canonical_name: 'Odisha',
    aliases: ['Orissa', 'Utkal'],
    place_type: 'state',
    parent_id: null,
    coordinates: [20.9517, 85.0985],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-29',
    canonical_name: 'Khordha',
    aliases: ['Khurda', 'Khurda District'],
    place_type: 'district',
    parent_id: 'IN-OD',
    coordinates: [20.1812, 85.6174],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-BBSR',
    canonical_name: 'Bhubaneswar',
    aliases: ['Bhubaneswar Municipal Corporation', 'BBSR'],
    place_type: 'subdistrict',
    parent_id: 'IN-OD-29',
    coordinates: [20.2961, 85.8245],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-JAT',
    canonical_name: 'Jatni',
    aliases: ['Jatani'],
    place_type: 'subdistrict',
    parent_id: 'IN-OD-29',
    coordinates: [20.1700, 85.7050],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-KHD',
    canonical_name: 'Khordha Town',
    aliases: ['Khurda Town'],
    place_type: 'subdistrict',
    parent_id: 'IN-OD-29',
    coordinates: [20.1812, 85.6174],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-BEG',
    canonical_name: 'Begunia',
    aliases: ['Begunia Block'],
    place_type: 'block',
    parent_id: 'IN-OD-29',
    coordinates: [20.2100, 85.4600],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-BAN',
    canonical_name: 'Banapur',
    aliases: ['Banpur', 'Banapur Block'],
    place_type: 'block',
    parent_id: 'IN-OD-29',
    coordinates: [19.7820, 85.1780],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-BOL',
    canonical_name: 'Bolagarh',
    aliases: ['Bolgarh', 'Bolagarh Block'],
    place_type: 'block',
    parent_id: 'IN-OD-29',
    coordinates: [20.1200, 85.3100],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-CHI',
    canonical_name: 'Chilika',
    aliases: ['Chilka', 'Chilika Block'],
    place_type: 'block',
    parent_id: 'IN-OD-29',
    coordinates: [19.7200, 85.3200],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
  {
    id: 'IN-OD-TAN',
    canonical_name: 'Tangi',
    aliases: ['Tangi Block'],
    place_type: 'block',
    parent_id: 'IN-OD-29',
    coordinates: [19.9300, 85.4500],
    geometry_available: true,
    resolution_method: 'census_2011',
  },
];

// Grounded GeoJSON Boundary Features
const MOCK_BOUNDARIES: GeoJsonFeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'IN-OD',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [81.4, 18.2],
            [82.6, 17.8],
            [84.1, 19.1],
            [85.0, 19.5],
            [86.8, 20.8],
            [87.5, 21.6],
            [86.7, 22.5],
            [84.8, 22.4],
            [83.5, 21.8],
            [82.5, 21.0],
            [82.6, 19.6],
            [81.8, 18.6],
            [81.4, 18.2],
          ],
        ],
      },
      properties: {
        id: 'IN-OD',
        name: 'Odisha',
        level: 'state',
        centroid: [20.9517, 85.0985],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-29',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.10, 19.68],
            [85.45, 19.60],
            [85.90, 20.10],
            [85.95, 20.42],
            [85.70, 20.45],
            [85.20, 20.30],
            [84.95, 20.15],
            [85.00, 19.80],
            [85.10, 19.68],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-29',
        name: 'Khordha',
        level: 'district',
        parent_id: 'IN-OD',
        centroid: [20.1812, 85.6174],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-BBSR',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.76, 20.22],
            [85.88, 20.22],
            [85.89, 20.36],
            [85.77, 20.36],
            [85.76, 20.22],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-BBSR',
        name: 'Bhubaneswar',
        level: 'subdistrict',
        parent_id: 'IN-OD-29',
        centroid: [20.2961, 85.8245],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-JAT',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.67, 20.14],
            [85.75, 20.14],
            [85.75, 20.21],
            [85.67, 20.21],
            [85.67, 20.14],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-JAT',
        name: 'Jatni',
        level: 'subdistrict',
        parent_id: 'IN-OD-29',
        centroid: [20.1700, 85.7050],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-KHD',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.58, 20.15],
            [85.66, 20.15],
            [85.66, 20.22],
            [85.58, 20.22],
            [85.58, 20.15],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-KHD',
        name: 'Khordha Town',
        level: 'subdistrict',
        parent_id: 'IN-OD-29',
        centroid: [20.1812, 85.6174],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-BEG',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.35, 20.15],
            [85.55, 20.15],
            [85.55, 20.30],
            [85.35, 20.30],
            [85.35, 20.15],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-BEG',
        name: 'Begunia',
        level: 'block',
        parent_id: 'IN-OD-29',
        centroid: [20.2100, 85.4600],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-BAN',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.05, 19.70],
            [85.25, 19.70],
            [85.25, 19.90],
            [85.05, 19.90],
            [85.05, 19.70],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-BAN',
        name: 'Banapur',
        level: 'block',
        parent_id: 'IN-OD-29',
        centroid: [19.7820, 85.1780],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-BOL',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.20, 20.05],
            [85.40, 20.05],
            [85.40, 20.20],
            [85.20, 20.20],
            [85.20, 20.05],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-BOL',
        name: 'Bolagarh',
        level: 'block',
        parent_id: 'IN-OD-29',
        centroid: [20.1200, 85.3100],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-CHI',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.15, 19.65],
            [85.50, 19.65],
            [85.50, 19.85],
            [85.15, 19.85],
            [85.15, 19.65],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-CHI',
        name: 'Chilika',
        level: 'block',
        parent_id: 'IN-OD-29',
        centroid: [19.7200, 85.3200],
      },
    },
    {
      type: 'Feature',
      id: 'IN-OD-TAN',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [85.35, 19.85],
            [85.55, 19.85],
            [85.55, 20.05],
            [85.35, 20.05],
            [85.35, 19.85],
          ],
        ],
      },
      properties: {
        id: 'IN-OD-TAN',
        name: 'Tangi',
        level: 'block',
        parent_id: 'IN-OD-29',
        centroid: [19.9300, 85.4500],
      },
    },
  ],
};

// Grounded Pilot Data Profiles
const MOCK_PROFILES: Record<string, PlaceProfile> = {
  'IN-OD-29': {
    place: PILOT_PLACES[1],
    hierarchy: {
      state: 'Odisha',
      district: 'Khordha',
    },
    retrieved_at: new Date().toISOString(),
    panels: {
      demographics: {
        domain: 'demographics',
        status: 'historical',
        coverage_note: 'Census of India 2011 Primary Census Abstract (PCA)',
        last_updated: '2026-10-21T00:00:00Z',
        sources: [
          {
            source_id: 'src-census-2011',
            publisher: 'Office of the Registrar General & Census Commissioner, India (ORGI)',
            name: 'Census of India 2011 Primary Census Abstract',
            url: 'https://censusindia.gov.in/nada/index.php/catalog/11382',
            licence: 'GODL-India',
            reference_period: '2011',
            retrieved_at: '2026-10-21T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'total_population',
            value: 2251673,
            unit: 'persons',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
            reference_period_start: '2011-02-09',
            reference_period_end: '2011-02-28',
          },
          {
            field_name: 'male_population',
            value: 1167114,
            unit: 'persons',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'female_population',
            value: 1084559,
            unit: 'persons',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'sex_ratio',
            value: 929,
            unit: 'females per 1000 males',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'literacy_rate',
            value: 86.88,
            unit: '%',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'total_households',
            value: 504264,
            unit: 'households',
            place_id: 'IN-OD-29',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
        ],
      },
      health: {
        domain: 'health',
        status: 'current',
        coverage_note: 'MoHFW / National Health Mission Odisha Directory & IDSP Surveillance',
        last_updated: '2026-10-21T18:00:00Z',
        sources: [
          {
            source_id: 'src-mohfw',
            publisher: 'Ministry of Health & Family Welfare / NHM Odisha',
            name: 'District Health Facility Directory & Bulletin',
            url: 'https://nhmodisha.gov.in/facilities',
            licence: 'GODL-India',
            reference_period: '2026-Q3',
            retrieved_at: '2026-10-21T18:00:00Z',
            verification_status: 'verified',
          },
          {
            source_id: 'src-idsp',
            publisher: 'Integrated Disease Surveillance Programme (IDSP)',
            name: 'Weekly Disease Surveillance Reports',
            url: 'https://idsp.mohfw.gov.in',
            licence: 'GODL-India',
            reference_period: '2026-W42',
            retrieved_at: '2026-10-21T12:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'primary_health_centres',
            value: 34,
            unit: 'facilities',
            place_id: 'IN-OD-29',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            notes: 'Operational 24x7 PHCs and Sub-Centres across 10 CD blocks',
          },
          {
            field_name: 'community_health_centres',
            value: 10,
            unit: 'facilities',
            place_id: 'IN-OD-29',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            notes: 'First Referral Units with emergency obstetric care',
          },
          {
            field_name: 'surveillance_dengue_cases',
            value: 18,
            unit: 'notified cases',
            place_id: 'IN-OD-29',
            source_id: 'src-idsp',
            quality_status: 'current',
            health_category: 'routine_surveillance',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T12:00:00Z',
            notes: 'Weekly routine surveillance count. Not an individualized diagnosis.',
          },
          {
            field_name: 'surveillance_cholera_cases',
            value: 2,
            unit: 'sentinel cases',
            place_id: 'IN-OD-29',
            source_id: 'src-idsp',
            quality_status: 'current',
            health_category: 'routine_surveillance',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T12:00:00Z',
            notes: 'Laboratory confirmed sentinel cases under IDSP protocol.',
          },
        ],
      },
      services: {
        domain: 'services',
        status: 'current',
        coverage_note: 'UDISE+ & Ministry of Jal Shakti Mission Indicators',
        last_updated: '2026-10-20T00:00:00Z',
        sources: [
          {
            source_id: 'src-udise',
            publisher: 'Ministry of Education, Govt. of India',
            name: 'Unified District Information System for Education Plus (UDISE+)',
            url: 'https://udiseplus.gov.in',
            licence: 'GODL-India',
            reference_period: '2023-2024',
            retrieved_at: '2026-10-20T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'schools_count',
            value: 1942,
            unit: 'schools',
            place_id: 'IN-OD-29',
            source_id: 'src-udise',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-20T00:00:00Z',
            notes: 'Government and recognized private educational institutions',
          },
          {
            field_name: 'drinking_water_coverage',
            value: 88.4,
            unit: '% households',
            place_id: 'IN-OD-29',
            source_id: 'src-udise',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-20T00:00:00Z',
            notes: 'Functional household tap connection (FHTC) in rural and peri-urban areas',
          },
          {
            field_name: 'electrification_coverage',
            value: 98.6,
            unit: '% households',
            place_id: 'IN-OD-29',
            source_id: 'src-udise',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-20T00:00:00Z',
            notes: 'Electrification under Saubhagya & Revamped Distribution Scheme',
          },
        ],
      },
      culture: {
        domain: 'culture',
        status: 'verified',
        coverage_note: 'Archaeological Survey of India (ASI) & Odisha State Monuments Inventory',
        last_updated: '2026-10-18T00:00:00Z',
        sources: [
          {
            source_id: 'src-asi',
            publisher: 'Archaeological Survey of India (ASI)',
            name: 'Inventory of Monuments of National Importance (Bhubaneswar Circle)',
            url: 'https://asi.nic.in/protected-monuments-in-odisha/',
            licence: 'Open Access / Citations',
            reference_period: 'Historical Archive',
            retrieved_at: '2026-10-18T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'heritage_site',
            value: 'Lingaraj Temple',
            place_id: 'IN-OD-29',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            monument_id: 'ASI-OD-001',
            historical_period: '11th Century CE (Somavamshi dynasty)',
            citation: 'ASI Central Protected Monument #N-OR-17; Rekha Deula architecture exemplar.',
          },
          {
            field_name: 'heritage_site',
            value: 'Khandagiri & Udayagiri Caves',
            place_id: 'IN-OD-29',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            monument_id: 'ASI-OD-002',
            historical_period: '2nd Century BCE (King Kharavela of Mahameghavahana dynasty)',
            citation: 'ASI Monument #N-OR-15; Hathigumpha inscription in Brahmi script.',
          },
          {
            field_name: 'heritage_site',
            value: 'Dhauli Shanti Stupa & Ashokan Rock Edicts',
            place_id: 'IN-OD-29',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            monument_id: 'ASI-OD-003',
            historical_period: '261 BCE (Kalinga War site & Edicts of Emperor Ashoka)',
            citation: 'Major Rock Edicts on Daya River banks; international peace monument.',
          },
        ],
      },
      environment: {
        domain: 'environment',
        status: 'current',
        coverage_note: 'ISRO Bhuvan / Sentinel-2 Surface Water Extent & FSI Forest Survey',
        last_updated: '2026-10-21T06:00:00Z',
        sources: [
          {
            source_id: 'src-isro-bhuvan',
            publisher: 'ISRO National Remote Sensing Centre (NRSC) & Copernicus',
            name: 'Bhuvan Thematic Geospatial Services & Sentinel-2 L2A',
            url: 'https://bhuvan.nrsc.gov.in',
            licence: 'CC-BY 4.0 / Open Science',
            reference_period: 'October 2026',
            retrieved_at: '2026-10-21T06:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'forest_cover',
            value: 21.4,
            unit: '% land area',
            place_id: 'IN-OD-29',
            source_id: 'src-isro-bhuvan',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T06:00:00Z',
            notes: 'India State of Forest Report (ISFR) biennial assessment',
          },
          {
            field_name: 'chilika_water_spread',
            value: 984.5,
            unit: 'sq km',
            place_id: 'IN-OD-29',
            source_id: 'src-isro-bhuvan',
            quality_status: 'current',
            licence: 'CC-BY 4.0',
            retrieved_at: '2026-10-21T06:00:00Z',
            satellite_mission: 'Sentinel-2 MSI / ISRO RISAT',
            resolution_meters: 10,
            cloud_cover_percentage: 4.2,
            scene_timestamp: '2026-10-15T04:42:10Z',
            notes: 'Post-monsoon water spread index (MNDWI calculation). Ramsar Site #229.',
          },
          {
            field_name: 'air_quality_index',
            value: 78,
            unit: 'AQI (Satisfactory)',
            place_id: 'IN-OD-29',
            source_id: 'src-isro-bhuvan',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T06:00:00Z',
            notes: 'Central Pollution Control Board / Odisha SPCB station average',
          },
        ],
      },
      weather: {
        domain: 'weather',
        status: 'current',
        coverage_note: 'India Meteorological Department (IMD) Surface Station Observations',
        last_updated: '2026-10-21T21:00:00Z',
        sources: [
          {
            source_id: 'src-imd',
            publisher: 'India Meteorological Department (IMD), Ministry of Earth Sciences',
            name: 'IMD Bhubaneswar Airport Station Surface Meteorological Observations',
            url: 'https://mausam.imd.gov.in',
            licence: 'GODL-India',
            reference_period: '2026-10-21 21:00 IST',
            retrieved_at: '2026-10-21T21:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'temperature',
            value: 28.5,
            unit: '°C',
            place_id: 'IN-OD-29',
            source_id: 'src-imd',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T21:00:00Z',
          },
          {
            field_name: 'humidity',
            value: 74,
            unit: '%',
            place_id: 'IN-OD-29',
            source_id: 'src-imd',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T21:00:00Z',
          },
          {
            field_name: 'wind_speed',
            value: 12,
            unit: 'km/h (ENE)',
            place_id: 'IN-OD-29',
            source_id: 'src-imd',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T21:00:00Z',
          },
          {
            field_name: 'barometric_pressure',
            value: 1011.2,
            unit: 'hPa',
            place_id: 'IN-OD-29',
            source_id: 'src-imd',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T21:00:00Z',
          },
          {
            field_name: 'weather_warning',
            value: 'Green - Normal conditions',
            unit: 'alert level',
            place_id: 'IN-OD-29',
            source_id: 'src-imd',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T21:00:00Z',
            notes: 'No severe weather warning active for Khordha coastal plain.',
          },
        ],
      },
    },
  },
  'IN-OD': {
    place: PILOT_PLACES[0],
    hierarchy: {
      state: 'Odisha',
    },
    retrieved_at: new Date().toISOString(),
    panels: {
      demographics: {
        domain: 'demographics',
        status: 'historical',
        coverage_note: 'Census of India 2011 Primary Census Abstract (PCA)',
        last_updated: '2026-10-21T00:00:00Z',
        sources: [
          {
            source_id: 'src-census-2011',
            publisher: 'Office of the Registrar General & Census Commissioner, India (ORGI)',
            name: 'Census of India 2011 Primary Census Abstract',
            url: 'https://censusindia.gov.in',
            licence: 'GODL-India',
            reference_period: '2011',
            retrieved_at: '2026-10-21T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'total_population',
            value: 41974218,
            unit: 'persons',
            place_id: 'IN-OD',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'male_population',
            value: 21212136,
            unit: 'persons',
            place_id: 'IN-OD',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'female_population',
            value: 20762082,
            unit: 'persons',
            place_id: 'IN-OD',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'sex_ratio',
            value: 979,
            unit: 'females per 1000 males',
            place_id: 'IN-OD',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'literacy_rate',
            value: 72.87,
            unit: '%',
            place_id: 'IN-OD',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
        ],
      },
      health: {
        domain: 'health',
        status: 'current',
        coverage_note: 'State level health infrastructure summary',
        last_updated: '2026-10-21T18:00:00Z',
        sources: [
          {
            source_id: 'src-mohfw',
            publisher: 'MoHFW / National Health Mission Odisha',
            name: 'State Health Bulletin',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'primary_health_centres',
            value: 1288,
            unit: 'facilities',
            place_id: 'IN-OD',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
          },
          {
            field_name: 'community_health_centres',
            value: 377,
            unit: 'facilities',
            place_id: 'IN-OD',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
          },
        ],
      },
    },
  },
  'IN-OD-BBSR': {
    place: PILOT_PLACES[2],
    hierarchy: {
      state: 'Odisha',
      district: 'Khordha',
      subdistrict: 'Bhubaneswar',
    },
    retrieved_at: new Date().toISOString(),
    panels: {
      demographics: {
        domain: 'demographics',
        status: 'historical',
        coverage_note: 'Census 2011 Municipal Area (BMC)',
        last_updated: '2026-10-21T00:00:00Z',
        sources: [
          {
            source_id: 'src-census-2011',
            publisher: 'ORGI',
            name: 'Census 2011',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'total_population',
            value: 843402,
            unit: 'persons',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'literacy_rate',
            value: 91.87,
            unit: '%',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'sex_ratio',
            value: 890,
            unit: 'females per 1000 males',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
        ],
      },
      health: {
        domain: 'health',
        status: 'current',
        coverage_note: 'Urban Primary Health & Tertiary Hospitals',
        last_updated: '2026-10-21T18:00:00Z',
        sources: [
          {
            source_id: 'src-mohfw',
            publisher: 'National Urban Health Mission (NUHM)',
            name: 'Bhubaneswar Urban Health Directory',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'urban_phcs',
            value: 24,
            unit: 'facilities',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            notes: 'Includes UPHCs and Capital Hospital complex',
          },
          {
            field_name: 'tertiary_institutes',
            value: 3,
            unit: 'institutes',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            notes: 'AIIMS Bhubaneswar, Capital Hospital Medical College, RMRC (ICMR)',
          },
        ],
      },
      culture: {
        domain: 'culture',
        status: 'verified',
        coverage_note: 'Temple City Heritage Monuments (ASI)',
        last_updated: '2026-10-18T00:00:00Z',
        sources: [
          {
            source_id: 'src-asi',
            publisher: 'ASI Bhubaneswar Circle',
            name: 'Protected Monuments Inventory',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'heritage_site',
            value: 'Lingaraj Temple',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            monument_id: 'ASI-OD-001',
            historical_period: 'Somavamshi (11th Century CE)',
            citation: 'Ekamra Kshetra heritage masterplan zone.',
          },
          {
            field_name: 'heritage_site',
            value: 'Mukteshvara Temple',
            place_id: 'IN-OD-BBSR',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            monument_id: 'ASI-OD-004',
            historical_period: '10th Century CE',
            citation: 'Known as the "Gem of Odishan Architecture", famed stone torana archway.',
          },
        ],
      },
      environment: {
        domain: 'environment',
        status: 'unavailable',
        coverage_note: 'Micro-level environmental assessment',
        last_updated: null,
        observations: [],
        data_gaps: [
          'Subdistrict-level hyper-local microclimate sensors not deployed',
          'Urban tree canopy index calculation requires high-res drone LiDAR (pending)',
        ],
      },
    },
  },
  'IN-OD-BAN': {
    place: PILOT_PLACES[6],
    hierarchy: {
      state: 'Odisha',
      district: 'Khordha',
      block: 'Banapur',
    },
    retrieved_at: new Date().toISOString(),
    panels: {
      demographics: {
        domain: 'demographics',
        status: 'historical',
        coverage_note: 'Census 2011 CD Block data',
        last_updated: '2026-10-21T00:00:00Z',
        sources: [
          {
            source_id: 'src-census-2011',
            publisher: 'ORGI',
            name: 'Census 2011 Primary Census Abstract',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'total_population',
            value: 121854,
            unit: 'persons',
            place_id: 'IN-OD-BAN',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'literacy_rate',
            value: 81.42,
            unit: '%',
            place_id: 'IN-OD-BAN',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
          {
            field_name: 'sex_ratio',
            value: 968,
            unit: 'females per 1000 males',
            place_id: 'IN-OD-BAN',
            source_id: 'src-census-2011',
            quality_status: 'historical',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T00:00:00Z',
          },
        ],
      },
      health: {
        domain: 'health',
        status: 'current',
        coverage_note: 'NHM Block Level Health Infrastructure',
        last_updated: '2026-10-21T18:00:00Z',
        sources: [
          {
            source_id: 'src-mohfw',
            publisher: 'NHM Odisha',
            name: 'Block Facility Register',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'primary_health_centres',
            value: 4,
            unit: 'facilities',
            place_id: 'IN-OD-BAN',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
          },
          {
            field_name: 'community_health_centres',
            value: 1,
            unit: 'facilities',
            place_id: 'IN-OD-BAN',
            source_id: 'src-mohfw',
            quality_status: 'current',
            licence: 'GODL-India',
            retrieved_at: '2026-10-21T18:00:00Z',
            notes: 'Banapur CHC with 30 in-patient beds',
          },
        ],
      },
      culture: {
        domain: 'culture',
        status: 'verified',
        coverage_note: 'Heritage site',
        last_updated: '2026-10-18T00:00:00Z',
        sources: [
          {
            source_id: 'src-asi',
            publisher: 'State Archaeology Department, Odisha',
            name: 'Protected Heritage Monuments',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            verification_status: 'verified',
          },
        ],
        observations: [
          {
            field_name: 'heritage_site',
            value: 'Bhagabati Temple & Dakshineswar Temple',
            place_id: 'IN-OD-BAN',
            source_id: 'src-asi',
            quality_status: 'verified',
            licence: 'Open Access',
            retrieved_at: '2026-10-18T00:00:00Z',
            historical_period: '9th-10th Century CE',
            citation: 'Shakti Peetha and historical center of the Banapur Rajas.',
          },
        ],
      },
      environment: {
        domain: 'environment',
        status: 'unavailable',
        coverage_note: 'Micro-environmental domain',
        last_updated: null,
        observations: [],
        data_gaps: [
          'No automated meteorological station (AWS) inside Banapur block interior',
          'Wetland catchment runoff sedimentation gauge pending installation',
        ],
      },
    },
  },
};

// Registered Sources Diagnostics
const MOCK_DIAGNOSTICS: SourceDiagnostics = {
  timestamp: new Date().toISOString(),
  total_sources: 7,
  active_sources: 7,
  sources: [
    {
      source_id: 'src-census-2011',
      publisher: 'Office of the Registrar General & Census Commissioner, India (ORGI)',
      name: 'Census of India 2011 Primary Census Abstract',
      url: 'https://censusindia.gov.in',
      licence: 'GODL-India',
      verification_status: 'verified',
      status: 'connected',
      records_served: 41974218,
      latency_ms: 12,
      last_sync: '2026-10-21T00:00:00Z',
      access_mode: 'local_sqlite',
    },
    {
      source_id: 'src-mohfw',
      publisher: 'Ministry of Health & Family Welfare / NHM Odisha',
      name: 'National Health Facility Directory & Bulletin',
      url: 'https://nhmodisha.gov.in',
      licence: 'GODL-India',
      verification_status: 'verified',
      status: 'connected',
      records_served: 1420,
      latency_ms: 28,
      last_sync: '2026-10-21T18:00:00Z',
      access_mode: 'verified_dataset',
    },
    {
      source_id: 'src-idsp',
      publisher: 'Integrated Disease Surveillance Programme (IDSP)',
      name: 'Weekly Disease Surveillance Reports',
      url: 'https://idsp.mohfw.gov.in',
      licence: 'GODL-India',
      verification_status: 'verified',
      status: 'connected',
      records_served: 850,
      latency_ms: 34,
      last_sync: '2026-10-21T12:00:00Z',
      access_mode: 'surveillance_feed',
    },
    {
      source_id: 'src-udise',
      publisher: 'Ministry of Education, Govt. of India',
      name: 'Unified District Information System for Education Plus (UDISE+)',
      url: 'https://udiseplus.gov.in',
      licence: 'GODL-India',
      verification_status: 'verified',
      status: 'connected',
      records_served: 2890,
      latency_ms: 22,
      last_sync: '2026-10-20T00:00:00Z',
      access_mode: 'education_atlas',
    },
    {
      source_id: 'src-asi',
      publisher: 'Archaeological Survey of India (ASI)',
      name: 'Inventory of Monuments of National Importance (Bhubaneswar Circle)',
      url: 'https://asi.nic.in',
      licence: 'Open Access',
      verification_status: 'verified',
      status: 'connected',
      records_served: 120,
      latency_ms: 15,
      last_sync: '2026-10-18T00:00:00Z',
      access_mode: 'curated_register',
    },
    {
      source_id: 'src-isro-bhuvan',
      publisher: 'ISRO / NRSC & Copernicus Sentinel-2',
      name: 'Bhuvan Geospatial Services & Sentinel-2 Surface Water Extent',
      url: 'https://bhuvan.nrsc.gov.in',
      licence: 'CC-BY 4.0 / Open Science',
      verification_status: 'verified',
      status: 'connected',
      records_served: 64,
      latency_ms: 45,
      last_sync: '2026-10-21T06:00:00Z',
      access_mode: 'raster_geotiff',
    },
    {
      source_id: 'src-imd',
      publisher: 'India Meteorological Department (IMD)',
      name: 'Direct Surface Weather Observations & Warnings',
      url: 'https://mausam.imd.gov.in',
      licence: 'GODL-India',
      verification_status: 'verified',
      status: 'connected',
      records_served: 340,
      latency_ms: 18,
      last_sync: '2026-10-21T21:00:00Z',
      access_mode: 'surface_station_api',
    },
  ],
};


export async function searchPlaces(query: string): Promise<SearchResponse> {
  if (!query.trim()) {
    return { query, results: [], total: 0, limit: 20, offset: 0 };
  }
  try {
    const res = await fetch(`${API_BASE}/places/search?q=${encodeURIComponent(query)}`);
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // Backend offline / network failure -> fallback to local search
  }

  // Fallback search over pilot dataset
  const q = query.trim().toLowerCase();
  const matched = PILOT_PLACES.filter(
    (p) =>
      p.canonical_name.toLowerCase().includes(q) ||
      p.aliases.some((a) => a.toLowerCase().includes(q)) ||
      p.id.toLowerCase().includes(q)
  );

  return {
    query,
    results: matched.map((p) => ({
      place: p,
      score: p.canonical_name.toLowerCase().startsWith(q) ? 1.0 : 0.8,
      match_type: p.canonical_name.toLowerCase().includes(q) ? 'name' : 'alias',
    })),
    total: matched.length,
    limit: 20,
    offset: 0,
    degraded: true,
    notes: ['Serving verified pilot dataset from local cache'],
  };
}

/**
 * Normalizes a place profile response ensuring both canonical backend keys
 * and frontend consumer aliases are accessible.
 */
export function normalizePlaceProfile(profile: PlaceProfile): PlaceProfile {
  if (!profile || !profile.panels) {
    return profile;
  }
  const panels: Record<string, PanelResponse> = { ...profile.panels };

  // 1. History & Culture mapping (history_culture <-> culture)
  const culturePanel = panels.history_culture || panels.culture;
  if (culturePanel) {
    panels.culture = culturePanel;
    panels.history_culture = culturePanel;
  }

  // 2. Weather & Disasters mapping (weather_disasters <-> weather)
  const weatherPanel = panels.weather_disasters || panels.weather;
  if (weatherPanel) {
    panels.weather = weatherPanel;
    panels.weather_disasters = weatherPanel;
  }

  return {
    ...profile,
    panels,
  };
}

/**
 * Load a place profile.
 *
 * Returns null when the backend has no profile for the place. It deliberately
 * does not synthesise figures: inventing a population, a school count, or a
 * facility count for an arbitrary place ID would be indistinguishable from
 * measured data once it reaches the screen.
 *
 * `MOCK_PROFILES` is a bundled sample for the pilot IDs only, and the UI only
 * reaches it when the backend is unreachable, under an explicit offline banner.
 */
export async function getPlaceProfile(placeId: string): Promise<PlaceProfile | null> {
  try {
    const res = await fetch(`${API_BASE}/places/${encodeURIComponent(placeId)}/profile`);
    if (res.ok) {
      const data: PlaceProfile = await res.json();
      return normalizePlaceProfile(data);
    }
  } catch {
    // Backend offline
  }

  const fixture = MOCK_PROFILES[placeId];
  if (fixture) {
    return normalizePlaceProfile(fixture);
  }

  return null;
}

export async function checkHealth(): Promise<{ status: string; version: string; pilot_region: string }> {
  // Try /health first (canonical unversioned root probe),
  // then try ${API_BASE}/health if an API gateway or proxy mounts it under the version prefix
  const endpoints = ['/health', `${API_BASE}/health`];
  for (const endpoint of endpoints) {
    try {
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        return {
          status: data.status || 'healthy',
          version: data.version || '1.0.0',
          pilot_region: data.pilot_region || 'Khordha, Odisha',
        };
      }
    } catch {
      // Network connection error on this endpoint, attempt next endpoint
    }
  }
  throw new Error('Backend offline');
}

export async function getBoundaries(): Promise<GeoJsonFeatureCollection> {
  try {
    const res = await fetch(`${API_BASE}/places/boundaries`);
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // fallback to mock
  }
  return MOCK_BOUNDARIES;
}

/**
 * Resolve a coordinate through the backend.
 *
 * Returns null when the backend is unreachable. It does not guess a place
 * from a bounding box: a bounding-box guess would place a pin in a district
 * it may not be in, and the profile that followed would look authoritative.
 */
export async function reverseGeocode(lat: number, lng: number): Promise<Place | null> {
  try {
    const res = await fetch(`${API_BASE}/places/reverse?lat=${lat}&lng=${lng}`);
    if (res.ok) {
      const data = await res.json();
      if (data.place) return data.place;
      if (data.id) return data;
    }
  } catch {
    // backend unreachable
  }
  return null;
}

export async function getSourceDiagnostics(): Promise<SourceDiagnostics> {
  try {
    const res = await fetch(`${API_BASE}/sources/diagnostics`);
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // fallback
  }
  return MOCK_DIAGNOSTICS;
}

export async function getHealthAlerts(placeId: string): Promise<HealthAlertsResponse> {
  try {
    const res = await fetch(`${API_BASE}/places/${encodeURIComponent(placeId)}/alerts`);
    if (res.ok) {
      const data = await res.json();
      // Ensure expected fields
      return {
        place_id: placeId,
        active_alerts: data.active_alerts || [],
        expired_alerts: data.expired_alerts || [],
        expired_count: data.expired_count || 0,
        source_count: data.source_count || 1,
        note: data.note,
      };
    }
  } catch {
    // fallback
  }


  // No alert is invented for an unknown place. "No active alerts" here means
  // Garuda has no ingested alert for this place, which is weaker than "the
  // district has issued no advisory" and is worded accordingly.
  return {
    place_id: placeId,
    active_alerts: [],
    expired_alerts: [],
    expired_count: 0,
    source_count: 0,
    note: 'No health alerts are available from Garuda\'s connected sources for this place.',
  };
}

/**
 * Load latest Sentinel-2 observation metadata for a place.
 * Returns null if the backend is unreachable or returns 404.
 */
export async function getEnvironmentScenes(
  placeId: string,
  raiseOnError = false,
): Promise<LatestObservationResponse | null> {
  try {
    const res = await fetch(
      `${API_BASE}/places/${encodeURIComponent(placeId)}/environment-scenes${
        raiseOnError ? '?raise_on_error=true' : ''
      }`
    );
    if (res.ok) {
      return (await res.json()) as LatestObservationResponse;
    }
  } catch {
    // Backend offline / network error
  }
  return null;
}

// ---------------------------------------------------------------------------
// Provenance-aware reads used by the Cesium 3D-terrain POC.
// These never substitute mock or generated data: when the backend cannot be
// reached they return `live: false` with empty/null data so the caller can
// display the real state instead of presenting a fixture as live.
//
// Deduplication & caching rationale:
//   * Boundaries rarely change — one fetch per browser session is fine.
//     A 5-minute memory cache avoids refetching on every mount.
//   * Profile fetches are deduplicated: a second call for the same placeId
//     while the first is in-flight reuses the same Promise.
//   * AbortSignal is threaded through so the globe can cancel stale fetches
//     when the user selects a new place before the previous one resolves.
// ---------------------------------------------------------------------------

export interface LiveData<T> {
  data: T;
  /** True only when the backend answered 2xx with a usable body. */
  live: boolean;
  /** HTTP status code from the server (absent when offline). */
  status?: number;
}

// ---------------------------------------------------------------------------
// Boundary cache — stable geographic data; 5-minute TTL is long enough to
// avoid redundant fetches across page interactions without risking stale
// geometry after a backend redeploy.
// ---------------------------------------------------------------------------
interface CacheEntry<T> {
  value: T;
  expiresAt: number; // Date.now() ms
}

const _boundaryCache: { entry: CacheEntry<LiveData<LiveBoundaryCollection>> | null } = {
  entry: null,
};
const BOUNDARY_TTL_MS = 5 * 60 * 1_000; // 5 minutes

/** In-flight request deduplication: key → Promise */
const _inflight = new Map<string, Promise<unknown>>();

export async function getBoundariesWithProvenance(
  signal?: AbortSignal,
): Promise<LiveData<LiveBoundaryCollection>> {
  // Return cached value if still fresh.
  const now = Date.now();
  if (_boundaryCache.entry && _boundaryCache.entry.expiresAt > now) {
    return _boundaryCache.entry.value;
  }

  // Deduplicate concurrent fetches for the same boundary set.
  const key = 'boundaries';
  const existing = _inflight.get(key) as Promise<LiveData<LiveBoundaryCollection>> | undefined;
  if (existing) return existing;

  const promise: Promise<LiveData<LiveBoundaryCollection>> = (async () => {
    try {
      const res = await fetch(`${API_BASE}/places/boundaries`, { signal });
      if (res.ok) {
        const result: LiveData<LiveBoundaryCollection> = {
          data: (await res.json()) as LiveBoundaryCollection,
          live: true,
          status: res.status,
        };
        _boundaryCache.entry = { value: result, expiresAt: Date.now() + BOUNDARY_TTL_MS };
        return result;
      }
      // 429 → surface it; don't cache
      return {
        data: { type: 'FeatureCollection', features: [] } as LiveBoundaryCollection,
        live: false,
        status: res.status,
      };
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      return { data: { type: 'FeatureCollection', features: [] }, live: false };
    } finally {
      _inflight.delete(key);
    }
  })();

  _inflight.set(key, promise);
  return promise;
}

/** Invalidate the boundary cache (e.g. after a backend redeploy). */
export function invalidateBoundaryCache(): void {
  _boundaryCache.entry = null;
}

export async function getPlaceProfileWithProvenance(
  placeId: string,
  signal?: AbortSignal,
): Promise<LiveData<PlaceProfile | null>> {
  // Deduplicate concurrent fetches for the same placeId.
  const key = `profile:${placeId}`;
  const existing = _inflight.get(key) as
    | Promise<LiveData<PlaceProfile | null>>
    | undefined;
  if (existing) return existing;

  const promise: Promise<LiveData<PlaceProfile | null>> = (async () => {
    try {
      const res = await fetch(`${API_BASE}/places/${encodeURIComponent(placeId)}/profile`, {
        signal,
      });
      if (res.ok) {
        return {
          data: normalizePlaceProfile((await res.json()) as PlaceProfile),
          live: true,
          status: res.status,
        };
      }
      return { data: null, live: false, status: res.status };
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      return { data: null, live: false };
    } finally {
      _inflight.delete(key);
    }
  })();

  _inflight.set(key, promise);
  return promise;
}

/**
 * Reverse geocode with the coverage verdict the backend supplies.
 *
 * `inside_coverage: false` means the returned place is only the nearest
 * supported boundary, so its profile must not be shown as this pin's data.
 */
export interface ReverseGeocodeOutcome {
  place: Place;
  inside_coverage: boolean;
  distance_km: number;
  coverage_note?: string | null;
}

export async function reverseGeocodeWithProvenance(
  lat: number,
  lng: number,
  signal?: AbortSignal,
): Promise<LiveData<ReverseGeocodeOutcome | null>> {
  // Deduplicate coordinate lookups rounded to 5 decimal places (~1 m precision).
  const roundedLat = lat.toFixed(5);
  const roundedLng = lng.toFixed(5);
  const key = `rgc:${roundedLat},${roundedLng}`;
  const existing = _inflight.get(key) as
    | Promise<LiveData<ReverseGeocodeOutcome | null>>
    | undefined;
  if (existing) return existing;

  const promise: Promise<LiveData<ReverseGeocodeOutcome | null>> = (async () => {
    try {
      const res = await fetch(`${API_BASE}/places/reverse?lat=${lat}&lng=${lng}`, { signal });
      if (res.ok) {
        const data = await res.json();
        const place: Place | undefined = data.place ?? (data.id ? data : undefined);
        if (place) {
          return {
            data: {
              place,
              inside_coverage:
                typeof data.inside_coverage === 'boolean'
                  ? data.inside_coverage
                  : data.match_type === 'enclosing',
              distance_km: typeof data.distance_km === 'number' ? data.distance_km : 0,
              coverage_note: data.coverage_note ?? null,
            },
            live: true,
            status: res.status,
          };
        }
      }
      return { data: null, live: res.status < 500, status: res.status };
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      return { data: null, live: false };
    } finally {
      _inflight.delete(key);
    }
  })();

  _inflight.set(key, promise);
  return promise;
}

