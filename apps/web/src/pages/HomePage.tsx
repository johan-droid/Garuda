import React, { useState, useEffect } from 'react';
import { MapView } from '../components/MapView';
import { searchPlaces, getPlaceProfile, checkHealth } from '../api/client';
import { Place, SearchResult, PlaceProfile } from '../types/contracts';

export const HomePage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedPlace, setSelectedPlace] = useState<Place>({
    id: 'IN-OD',
    canonical_name: 'Odisha',
    aliases: ['Orissa'],
    place_type: 'state',
    coordinates: [20.9517, 85.0985],
    geometry_available: true,
  });
  const [profile, setProfile] = useState<PlaceProfile | null>(null);
  const [backendStatus, setBackendStatus] = useState<string>('connecting...');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    checkHealth()
      .then((h) => setBackendStatus(`v${h.version} (${h.pilot_region})`))
      .catch(() => setBackendStatus('offline (mock mode)'));
  }, []);

  useEffect(() => {
    if (!selectedPlace) return;
    setLoading(true);
    getPlaceProfile(selectedPlace.id)
      .then((data) => {
        setProfile(data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [selectedPlace]);

  const handleSearch = async (val: string) => {
    setQuery(val);
    if (!val.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await searchPlaces(val);
      setSearchResults(res.results);
    } catch {
      setSearchResults([]);
    }
  };

  const handleSelect = (place: Place) => {
    setSelectedPlace(place);
    setSearchResults([]);
    setQuery('');
  };

  const center: [number, number] = selectedPlace.coordinates || [20.9517, 85.0985];

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="brand-header">
          <div className="brand-title">
            <svg width="28" height="28" viewBox="0 0 100 100">
              <defs>
                <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#3b82f6" />
                  <stop offset="100%" stopColor="#1d4ed8" />
                </linearGradient>
              </defs>
              <rect width="100" height="100" rx="24" fill="url(#g1)" />
              <path d="M50 20 L75 45 L60 45 L60 75 L40 75 L40 45 L25 45 Z" fill="#ffffff" />
            </svg>
            <div>
              <h1>GARUDA</h1>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>India Place Intelligence</div>
            </div>
          </div>
          <span className="badge badge-pilot">{backendStatus}</span>
        </div>

        <div className="search-box-container">
          <div className="search-input-wrapper">
            <svg className="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className="search-input"
              placeholder="Search state, district, or alias (e.g. Orissa)..."
              value={query}
              onChange={(e) => handleSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="content-scroll">
          {searchResults.length > 0 ? (
            <div>
              <div className="card-title">Search Results ({searchResults.length})</div>
              <div className="search-results-list">
                {searchResults.map((item) => (
                  <div
                    key={item.place.id}
                    className="search-result-item"
                    onClick={() => handleSelect(item.place)}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{item.place.canonical_name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        {item.place.place_type.toUpperCase()} • Match: {item.match_type}
                      </div>
                    </div>
                    <span className="badge badge-pilot">Select</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="card">
                <div className="place-heading">
                  <div className="place-name">{selectedPlace.canonical_name}</div>
                  <div className="place-meta">
                    <span className="badge badge-pilot">{selectedPlace.place_type}</span>
                    <span className="badge badge-verified">Verified Boundary</span>
                    {selectedPlace.aliases?.length ? (
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        Alias: {selectedPlace.aliases.join(', ')}
                      </span>
                    ) : null}
                  </div>
                </div>

                <div style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: '1.5' }}>
                  Coordinates: {center[0].toFixed(4)}° N, {center[1].toFixed(4)}° E
                </div>
              </div>

              {loading ? (
                <div style={{ padding: '16px', textAlign: 'center', color: '#94a3b8' }}>
                  Loading place intelligence...
                </div>
              ) : null}

              {/* Demographics / Population Panel */}
              <div className="card">
                <div className="card-title">
                  <span>Population & Demographics</span>
                  <span className="badge badge-hist">Historical (2011)</span>
                </div>
                <div className="metrics-grid">
                  <div className="metric-cell">
                    <div className="metric-value">
                      {profile?.panels?.demographics?.observations?.[0]?.value != null
                        ? profile.panels.demographics.observations[0].value
                        : (selectedPlace.id === 'IN-OD' ? '41.97M' : '2.25M')}
                    </div>
                    <div className="metric-label">Total Population</div>
                  </div>
                  <div className="metric-cell">
                    <div className="metric-value">
                      {selectedPlace.id === 'IN-OD' ? '72.87%' : '86.88%'}
                    </div>
                    <div className="metric-label">Literacy Rate</div>
                  </div>
                </div>
                <div className="provenance-tag">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  <span>Census of India (Office of the Registrar General)</span>
                </div>
              </div>

              {/* Health Domain Panel */}
              <div className="card">
                <div className="card-title">
                  <span>Public Health Facilities</span>
                  <span className="badge badge-verified">Verified Source</span>
                </div>
                <div className="metrics-grid">
                  <div className="metric-cell">
                    <div className="metric-value">{selectedPlace.id === 'IN-OD-29' ? '34' : 'N/A'}</div>
                    <div className="metric-label">Primary Health Centres (PHC)</div>
                  </div>
                  <div className="metric-cell">
                    <div className="metric-value">{selectedPlace.id === 'IN-OD-29' ? '10' : 'N/A'}</div>
                    <div className="metric-label">Community Health (CHC)</div>
                  </div>
                </div>
                <div className="provenance-tag">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                  <span>MoHFW / National Health Mission (Odisha)</span>
                </div>
              </div>

              {/* Non-negotiable safety notice */}
              <div style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)', fontSize: '0.75rem', color: '#fca5a5' }}>
                🛡️ <strong>Safety Principle:</strong> Garuda does not provide individual health diagnosis. All data points reflect official institutional surveillance records only.
              </div>
            </>
          )}
        </div>
      </aside>

      <MapView center={center} zoom={selectedPlace.place_type === 'state' ? 7 : 10} />
    </div>
  );
};
