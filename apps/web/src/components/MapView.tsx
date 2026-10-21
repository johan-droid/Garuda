import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';

interface MapViewProps {
  center: [number, number]; // [lat, lng]
  zoom: number;
  onPlaceClick?: (lat: number, lng: number) => void;
}

export const MapView: React.FC<MapViewProps> = ({ center, zoom }) => {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const marker = useRef<maplibregl.Marker | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    // Center is [lat, lng], MapLibre expects [lng, lat]
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto-dark': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, © <a href="https://carto.com/">CARTO</a>',
          },
        },
        layers: [
          {
            id: 'carto-dark-layer',
            type: 'raster',
            source: 'carto-dark',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [center[1], center[0]],
      zoom: zoom,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    marker.current = new maplibregl.Marker({ color: '#3b82f6' })
      .setLngLat([center[1], center[0]])
      .addTo(map.current);

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (map.current) {
      map.current.flyTo({
        center: [center[1], center[0]],
        zoom: zoom,
        essential: true,
      });
      marker.current?.setLngLat([center[1], center[0]]);
    }
  }, [center, zoom]);

  return (
    <div className="map-container">
      <div ref={mapContainer} className="maplibre-viewport" />
      <div className="map-attribution-overlay">
        Map data: © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> | Basemap: © <a href="https://carto.com/" target="_blank" rel="noreferrer">CARTO</a>
      </div>
    </div>
  );
};
