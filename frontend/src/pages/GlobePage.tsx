import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { CesiumGlobe } from '../components/CesiumGlobe';
import {
  getBoundariesWithProvenance,
  getPlaceProfileWithProvenance,
  reverseGeocodeWithProvenance,
} from '../api/client';
import type { LiveBoundaryCollection, PanelResponse, PlaceProfile } from '../types/contracts';
import { CESIUM_ATTRIBUTION, GIBS_ACKNOWLEDGEMENT, LOCAL_MOSAIC_MANIFESTS, OPEN_TERRAIN_SOURCE, type LocalMosaicManifest } from '../cesium/config';
import { parseMosaicManifest } from '../cesium/imagery';
import '../styles/cesium.css';

const PANEL_ORDER = [
  'demographics',
  'health',
  'services',
  'infrastructure',
  'environment',
  'resilience',
  'history_culture',
  'weather_disasters',
];

function panelRank(domain: string): number {
  const index = PANEL_ORDER.indexOf(domain);
  return index === -1 ? PANEL_ORDER.length : index;
}

function formatValue(value: unknown, unit?: string | null): string {
  // Missing data must stay visibly missing, never rendered as zero.
  if (value === null || value === undefined || value === '') return 'unavailable';
  return unit ? `${String(value)} ${unit}` : String(value);
}

function PanelCard({ domain, panel }: { domain: string; panel: PanelResponse }) {
  const observations = panel.observations ?? [];
  const gaps = panel.data_gaps ?? [];

  return (
    <section className={`panel-card panel-card--${panel.status}`}>
      <header className="panel-card__header">
        <h3>{domain.replace(/_/g, ' ')}</h3>
        <span className={`status-badge status-badge--${panel.status}`}>{panel.status}</span>
      </header>

      {panel.coverage_note && <p className="panel-card__note">{panel.coverage_note}</p>}

      {observations.length > 0 ? (
        <ul className="obs-list">
          {observations.map((obs, index) => (
            <li key={`${obs.field_name}-${index}`} className="obs-row">
              <span className="obs-row__field">{obs.field_name.replace(/_/g, ' ')}</span>
              <span className="obs-row__value">{formatValue(obs.value, obs.unit)}</span>
              <span className="obs-row__meta">
                {obs.quality_status}
                {obs.source_id ? ` · ${obs.source_id}` : ''}
                {obs.retrieved_at ? ` · retrieved ${obs.retrieved_at.slice(0, 10)}` : ''}
                {obs.licence ? ` · ${obs.licence}` : ''}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="panel-card__empty">No verified observations in this domain.</p>
      )}

      {gaps.length > 0 && (
        <div className="panel-card__gaps">
          <strong>Data gaps</strong>
          <ul>
            {gaps.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>
        </div>
      )}

      {(panel.sources ?? []).length > 0 && (
        <p className="panel-card__sources">
          Sources:{' '}
          {(panel.sources ?? [])
            .map((source) => `${source.publisher} — ${source.name} (${source.licence ?? 'licence n/a'})`)
            .join(' · ')}
        </p>
      )}

      {panel.error && <p className="panel-card__error">{panel.error}</p>}
    </section>
  );
}

type MosaicState =
  | { status: 'loading' }
  | { status: 'missing' }
  | { status: 'ready'; manifest: LocalMosaicManifest };

export function GlobePage() {
  const [boundaries, setBoundaries] = useState<LiveBoundaryCollection | null>(null);
  const [boundariesLive, setBoundariesLive] = useState<boolean | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedLabel, setSelectedLabel] = useState('');
  const [profile, setProfile] = useState<PlaceProfile | null>(null);
  const [profileLive, setProfileLive] = useState<boolean | null>(null);
  const [profileState, setProfileState] = useState<'idle' | 'loading' | 'ready'>('idle');
  const [notice, setNotice] = useState<string | null>(null);
  const [mosaic, setMosaic] = useState<MosaicState>({ status: 'loading' });

  const requestSeq = useRef(0);

  // Optional locally generated Sentinel-2 mosaic. A missing or malformed
  // manifest is an explicit, visible state — never a silent skip or placeholder.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(LOCAL_MOSAIC_MANIFESTS[0]);
        if (!resp.ok) throw new Error(`manifest HTTP ${resp.status}`);
        const manifest = parseMosaicManifest(await resp.json());
        if (!cancelled) {
          setMosaic(manifest ? { status: 'ready', manifest } : { status: 'missing' });
        }
      } catch {
        if (!cancelled) setMosaic({ status: 'missing' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    getBoundariesWithProvenance().then(({ data, live }) => {
      if (cancelled) return;
      setBoundaries(data);
      setBoundariesLive(live);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectPlace = useCallback(async (placeId: string, label: string) => {
    const seq = ++requestSeq.current;
    setSelectedId(placeId);
    setSelectedLabel(label);
    setProfileState('loading');
    setNotice(null);

    const { data, live } = await getPlaceProfileWithProvenance(placeId);
    if (seq !== requestSeq.current) return;

    setProfile(data);
    setProfileLive(live);
    setProfileState('ready');
    if (!live) {
      setNotice('Backend unreachable — no profile loaded. Fixture data is deliberately not shown.');
    }
  }, []);

  const handleReverseGeocode = useCallback(
    async (lat: number, lng: number) => {
      const seq = ++requestSeq.current;
      setNotice(null);

      const { data, live } = await reverseGeocodeWithProvenance(lat, lng);
      if (seq !== requestSeq.current) return;

      if (!live) {
        setNotice('Backend unreachable — this location could not be resolved.');
        return;
      }
      if (!data) {
        setNotice(`No registered place at ${lat.toFixed(3)}, ${lng.toFixed(3)}.`);
        return;
      }
      // Outside the supported boundary set the pin is not resolved to a place:
      // the nearest boundary's profile would describe somewhere else.
      if (!data.inside_coverage) {
        setNotice(
          data.coverage_note ??
            `${lat.toFixed(3)}, ${lng.toFixed(3)} is outside Garuda's supported boundaries.`,
        );
        return;
      }
      await selectPlace(data.place.id, data.place.canonical_name);
    },
    [selectPlace],
  );

  const orderedPanels = useMemo(() => {
    if (!profile) return [];
    // normalizePlaceProfile mirrors some panels under alias keys (`culture`,
    // `weather`); render each underlying panel once.
    const seen = new Set<PanelResponse>();
    return Object.entries(profile.panels ?? {})
      .filter(([, panel]) => {
        if (seen.has(panel)) return false;
        seen.add(panel);
        return true;
      })
      .sort(([a], [b]) => panelRank(a) - panelRank(b));
  }, [profile]);

  return (
    <div className="globe-page">
      <aside className="globe-sidebar">
        <header className="globe-sidebar__header">
          <div>
            <h1>Garuda · 3D Terrain</h1>
            <p className="globe-sidebar__subtitle">
              {OPEN_TERRAIN_SOURCE.label}
            </p>
          </div>
          <a className="globe-sidebar__back" href="/">
            ← 2D map
          </a>
        </header>

        <div className="provenance">
          <span className={`provenance__dot provenance__dot--${boundariesLive ? 'live' : 'offline'}`} />
          {boundariesLive === null
            ? 'Loading boundaries…'
            : boundariesLive
              ? `Live backend · ${boundaries?.features.length ?? 0} boundaries`
              : 'Backend unavailable · no boundaries shown'}
        </div>

        <section className="globe-sidebar__section">
          <h2>Boundaries</h2>
          <ul className="boundary-list">
            {(boundaries?.features ?? []).map((feature) => {
              const { id, canonical_name, place_type } = feature.properties;
              return (
                <li key={id}>
                  <button
                    type="button"
                    className={`boundary-list__item${id === selectedId ? ' is-selected' : ''}`}
                    onClick={() => void selectPlace(id, canonical_name)}
                  >
                    <span>{canonical_name}</span>
                    <span className="boundary-list__type">{place_type}</span>
                  </button>
                </li>
              );
            })}
            {boundariesLive && (boundaries?.features.length ?? 0) === 0 && (
              <li className="boundary-list__empty">Backend returned no boundaries.</li>
            )}
          </ul>
        </section>

        <section className="globe-sidebar__section globe-sidebar__section--profile">
          <h2>Profile</h2>

          {notice && <p className="notice">{notice}</p>}

          {profileState === 'idle' && !notice && (
            <p className="hint">Click a boundary or any point on the globe to inspect a place.</p>
          )}

          {profileState === 'loading' && <p className="hint">Loading profile…</p>}

          {profileState === 'ready' && !profile && (
            <p className="hint">No live profile available for this place.</p>
          )}

          {profile && (
            <>
              <div className="profile-header">
                <h3>{profile.place.canonical_name}</h3>
                <p className="profile-header__meta">
                  {selectedLabel && selectedLabel !== profile.place.canonical_name
                    ? `${selectedLabel} · `
                    : ''}
                  {profile.place.id} · {profile.place.place_type}
                </p>
                <p className="profile-header__hierarchy">
                  {[profile.hierarchy?.state, profile.hierarchy?.district, profile.hierarchy?.subdistrict]
                    .filter(Boolean)
                    .join(' › ')}
                </p>
                <div className="provenance provenance--inline">
                  <span className={`provenance__dot provenance__dot--${profileLive ? 'live' : 'offline'}`} />
                  {profileLive ? 'Live backend response' : 'Not live'}
                  {profile.retrieved_at ? ` · retrieved ${profile.retrieved_at.slice(0, 10)}` : ''}
                </div>
              </div>

              {orderedPanels.map(([domain, panel]) => (
                <PanelCard key={domain} domain={domain} panel={panel} />
              ))}
            </>
          )}
        </section>

        <footer className="globe-sidebar__attribution">
          <p>{GIBS_ACKNOWLEDGEMENT}</p>
          {mosaic.status === 'ready' && (
            <p>
              {mosaic.manifest.attribution_display} — true-colour Sentinel-2 mosaic, locally
              generated ({mosaic.manifest.mosaic.ground_res_m} m ground resolution) and served
              same-origin. See ATTRIBUTION.md.
            </p>
          )}
          {mosaic.status === 'missing' && (
            <p>
              Local Sentinel-2 mosaic unavailable — it has not been generated on this machine. Run
              <code> make imagery-build </code>(see docs/imagery-pipeline.md). Base imagery is NASA
              GIBS.
            </p>
          )}
          <p>{OPEN_TERRAIN_SOURCE.attribution}</p>
          <p>{CESIUM_ATTRIBUTION}</p>
          <p>Boundary and profile data: Garuda pilot backend.</p>
        </footer>
      </aside>

      <main className="globe-main">
        <CesiumGlobe
          boundaries={boundaries}
          selectedId={selectedId}
          onSelectPlace={(placeId, label) => void selectPlace(placeId, label)}
          onReverseGeocode={(lat, lng) => void handleReverseGeocode(lat, lng)}
          mosaic={mosaic.status === 'ready' ? mosaic.manifest : null}
        />
      </main>
    </div>
  );
}

export default GlobePage;
