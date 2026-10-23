import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { getBoundaries } from '../api/client';
import { GeoJsonFeatureCollection } from '../types/contracts';

interface MapViewProps {
  center: [number, number]; // [lat, lng]
  zoom: number;
  selectedPlaceId?: string;
  onPlaceClick?: (lat: number, lng: number) => void;
}

export const MapView: React.FC<MapViewProps> = ({
  center,
  zoom,
  selectedPlaceId,
  onPlaceClick,
}) => {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);
  const boundariesData = useRef<GeoJsonFeatureCollection | null>(null);
  const onPlaceClickRef = useRef(onPlaceClick);

  useEffect(() => {
    onPlaceClickRef.current = onPlaceClick;
  }, [onPlaceClick]);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Center is [lat, lng], MapLibre expects [lng, lat]
    const m = new maplibregl.Map({
      container: mapContainer.current,
      // OpenFreeMap's public instance is keyless and unauthenticated. CARTO's
      // rastertiles now answer unkeyed requests with "API KEY REQUIRED"
      // watermarks, which would make the default map depend on a credential.
      // ponytail: third-party free instance, no SLA; self-host the style if
      // availability ever matters.
      style: 'https://tiles.openfreemap.org/styles/dark',
      center: [center[1], center[0]],
      zoom: zoom,
    });

    m.addControl(new maplibregl.NavigationControl({ showCompass: true, showZoom: true }), 'top-right');
    m.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');

    const mk = new maplibregl.Marker({ color: '#3b82f6' })
      .setLngLat([center[1], center[0]])
      .addTo(m);

    marker.current = mk;
    map.current = m;

    m.on('load', async () => {
      try {
        const geojson = await getBoundaries();
        // The live backend emits `place_type`; the bundled fixture emits
        // `level`. Normalise once, so the style filters below work for both.
        const normalized = {
          ...geojson,
          features: geojson.features.map((feature) => {
            const props = feature.properties as unknown as Record<string, unknown>;
            return {
              ...feature,
              properties: { ...props, level: props.level ?? props.place_type },
            };
          }),
        };
        boundariesData.current = normalized as unknown as GeoJsonFeatureCollection;

        if (!m.getSource('garuda-boundaries')) {
          m.addSource('garuda-boundaries', {
            type: 'geojson',
            data: normalized as any,
          });

          // 1. State Boundaries Layer (Blue tint)
          m.addLayer({
            id: 'state-boundaries-fill',
            type: 'fill',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'level'], 'state'],
            paint: {
              'fill-color': '#3b82f6',
              'fill-opacity': 0.05,
            },
          });
          m.addLayer({
            id: 'state-boundaries-line',
            type: 'line',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'level'], 'state'],
            paint: {
              'line-color': '#3b82f6',
              'line-width': 2,
              'line-opacity': 0.7,
            },
          });

          // 2. District Boundaries Layer (Emerald Green tint)
          m.addLayer({
            id: 'district-boundaries-fill',
            type: 'fill',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'level'], 'district'],
            paint: {
              'fill-color': '#10b981',
              'fill-opacity': 0.09,
            },
          });
          m.addLayer({
            id: 'district-boundaries-line',
            type: 'line',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'level'], 'district'],
            paint: {
              'line-color': '#10b981',
              'line-width': 2,
              'line-opacity': 0.85,
            },
          });

          // 3. Block / Subdistrict Boundaries Layer (Purple / Indigo tint)
          m.addLayer({
            id: 'block-boundaries-fill',
            type: 'fill',
            source: 'garuda-boundaries',
            filter: [
              'any',
              ['==', ['get', 'level'], 'block'],
              ['==', ['get', 'level'], 'subdistrict'],
            ],
            paint: {
              'fill-color': '#8b5cf6',
              'fill-opacity': 0.12,
            },
          });
          m.addLayer({
            id: 'block-boundaries-line',
            type: 'line',
            source: 'garuda-boundaries',
            filter: [
              'any',
              ['==', ['get', 'level'], 'block'],
              ['==', ['get', 'level'], 'subdistrict'],
            ],
            paint: {
              'line-color': '#a78bfa',
              'line-width': 1.5,
              'line-dasharray': [2, 2],
              'line-opacity': 0.8,
            },
          });

          // 4. Selected Place Highlight Layer (Amber / Gold glow)
          m.addLayer({
            id: 'selected-place-highlight-fill',
            type: 'fill',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'id'], selectedPlaceId || ''],
            paint: {
              'fill-color': '#f59e0b',
              'fill-opacity': 0.28,
            },
          });
          m.addLayer({
            id: 'selected-place-highlight-line',
            type: 'line',
            source: 'garuda-boundaries',
            filter: ['==', ['get', 'id'], selectedPlaceId || ''],
            paint: {
              'line-color': '#fbbf24',
              'line-width': 3.5,
            },
          });
        }
      } catch (err) {
        console.warn('Could not load boundaries into MapLibre:', err);
      }
    });

    // Map Click Listener -> resolves administrative unit via reverse geocoding
    m.on('click', (e) => {
      onPlaceClickRef.current?.(e.lngLat.lat, e.lngLat.lng);
    });

    // Pointer cursor when hovering over interactive boundary areas
    const interactiveLayers = [
      'block-boundaries-fill',
      'district-boundaries-fill',
      'state-boundaries-fill',
    ];

    interactiveLayers.forEach((layerId) => {
      m.on('mouseenter', layerId, () => {
        if (mapContainer.current) mapContainer.current.style.cursor = 'pointer';
      });
      m.on('mouseleave', layerId, () => {
        if (mapContainer.current) mapContainer.current.style.cursor = '';
      });
    });

    return () => {
      m.remove();
      map.current = null;
    };
  }, []);

  // Update center & zoom
  useEffect(() => {
    if (map.current) {
      map.current.flyTo({
        center: [center[1], center[0]],
        zoom: zoom,
        speed: 1.2,
        curve: 1.4,
        essential: true,
      });
      marker.current?.setLngLat([center[1], center[0]]);
    }
  }, [center, zoom]);

  // Update selected place highlight filter
  useEffect(() => {
    if (map.current && map.current.isStyleLoaded()) {
      const filter: any = ['==', ['get', 'id'], selectedPlaceId || ''];
      if (map.current.getLayer('selected-place-highlight-fill')) {
        map.current.setFilter('selected-place-highlight-fill', filter);
      }
      if (map.current.getLayer('selected-place-highlight-line')) {
        map.current.setFilter('selected-place-highlight-line', filter);
      }
    }
  }, [selectedPlaceId]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="maplibre-viewport" />
      <div className="map-legend-overlay">
        <div className="legend-item">
          <span className="legend-swatch legend-state" />
          <span>State (OD)</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-district" />
          <span>District (Khordha)</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-block" />
          <span>Block / Municipal</span>
        </div>
        <div className="legend-item">
          <span className="legend-swatch legend-selected" />
          <span>Selected Area</span>
        </div>
      </div>
      <div className="map-attribution-overlay">
        Map data: ©{' '}
        <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
          OpenStreetMap
        </a>{' '}
        | Basemap: ©{' '}
        <a href="https://openfreemap.org/" target="_blank" rel="noreferrer">
          OpenFreeMap
        </a>{' '}
        | Boundaries: Garuda pilot fixture (schematic outlines, not survey-grade)
      </div>
    </div>
  );
};
