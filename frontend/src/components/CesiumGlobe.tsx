/* eslint-disable react-refresh/only-export-components */
import '../cesium/env';
import { useEffect, useRef, useState } from 'react';
import * as Cesium from 'cesium';
import type { GeoJsonFeatureCollection, LiveBoundaryProperties } from '../types/contracts';
import {
  CAMERAS,
  ELLIPSOID_FALLBACK,
  OPEN_TERRAIN_SOURCE,
  type LocalMosaicManifest,
} from '../cesium/config';
import { createTerrain } from '../cesium/terrain';
import { addImageryLayers, addMosaicLayer } from '../cesium/imagery';

interface CesiumGlobeProps {
  boundaries: GeoJsonFeatureCollection<LiveBoundaryProperties> | null;
  selectedId: string | null;
  onSelectPlace: (placeId: string, label: string) => void;
  onReverseGeocode: (lat: number, lng: number) => void;
  /** Optional generated Sentinel-2 mosaic; null/absent keeps GIBS base only. */
  mosaic?: LocalMosaicManifest | null;
}

const BOUNDARY_COLOR = Cesium.Color.fromCssColorString('#ffcf5c');
const SELECTED_COLOR = Cesium.Color.fromCssColorString('#4ce0b3');

/** Place id encoded in an entity id (`IN-OD-29` or `IN-OD-29::ring1`). */
function placeIdFromEntityId(entityId: string): string {
  return entityId.split('::')[0];
}

function ringsOf(feature: GeoJsonFeatureCollection<LiveBoundaryProperties>['features'][number]): number[][][] {
  const geometry = feature.geometry;
  if (geometry.type === 'Polygon') {
    return [geometry.coordinates[0] as number[][]];
  }
  if (geometry.type === 'MultiPolygon') {
    return (geometry.coordinates as number[][][][]).map((polygon) => polygon[0]);
  }
  return [];
}

export function CesiumGlobe({
  boundaries,
  selectedId,
  onSelectPlace,
  onReverseGeocode,
  mosaic = null,
}: CesiumGlobeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const callbacksRef = useRef({ onSelectPlace, onReverseGeocode });
  const boundaryEntitiesRef = useRef<Map<string, Cesium.Entity[]>>(new Map());
  const mosaicLayerRef = useRef<Cesium.ImageryLayer | null>(null);

  const [ready, setReady] = useState(false);
  const [tilesLoading, setTilesLoading] = useState(true);
  const [terrainIssue, setTerrainIssue] = useState<string | null>(null);

  callbacksRef.current = { onSelectPlace, onReverseGeocode };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const terrain = createTerrain(OPEN_TERRAIN_SOURCE);
    if (!terrain.hasElevation) {
      setTerrainIssue(`Terrain source unavailable (${ELLIPSOID_FALLBACK.label}).`);
    }

    // Cesium's default credit display renders a "Cesium ion" logo even when ion
    // is never touched. This POC uses no ion services, so showing that branding
    // implies a dependency that does not exist. CesiumJS itself is still credited
    // in the sidebar attribution.
    (
      Cesium.CreditDisplay as unknown as { cesiumCredit: Cesium.Credit | undefined }
    ).cesiumCredit = undefined;

    const viewer = new Cesium.Viewer(container, {
      // Never fall back to Cesium ion's world imagery.
      baseLayer: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      terrainProvider: terrain.provider,
    });

    viewerRef.current = viewer;
    viewer.scene.globe.depthTestAgainstTerrain = true;
    viewer.scene.globe.showGroundAtmosphere = true;

    addImageryLayers(viewer);

    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(
        CAMERAS.india.longitude,
        CAMERAS.india.latitude,
        CAMERAS.india.height,
      ),
      orientation: {
        heading: 0,
        pitch: Cesium.Math.toRadians(-55),
        roll: 0,
      },
    });

    // Non-null only for a real terrain provider; silence would hide provider failure.
    const removeTerrainErrorListener = terrain.errorEvent?.addEventListener(
      (error: Cesium.TileProviderError) => {
        setTerrainIssue(error.message || 'Terrain tiles failed to load — showing flat globe.');
      },
    );

    let wasLoading = true;
    const removeProgressListener = viewer.scene.globe.tileLoadProgressEvent.addEventListener(
      (queued: number) => {
        const loading = queued > 0;
        if (loading !== wasLoading) {
          wasLoading = loading;
          setTilesLoading(loading);
        }
      },
    );

    const clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    clickHandler.setInputAction((movement: Cesium.ScreenSpaceEventHandler.PositionedEvent) => {
      const picked = viewer.scene.pick(movement.position);
      const pickedEntityId = picked?.id instanceof Cesium.Entity ? picked.id.id : undefined;

      if (pickedEntityId) {
        const placeId = placeIdFromEntityId(pickedEntityId);
        const label = boundaryEntitiesRef.current.has(placeId) ? placeId : null;
        if (label) {
          const first = boundaryEntitiesRef.current.get(placeId)?.[0];
          const name = first?.properties?.canonical_name?.getValue(Cesium.JulianDate.now());
          callbacksRef.current.onSelectPlace(placeId, typeof name === 'string' ? name : placeId);
          return;
        }
      }

      const ray = viewer.camera.getPickRay(movement.position);
      const cartesian = ray ? viewer.scene.globe.pick(ray, viewer.scene) : undefined;
      if (!cartesian) return;

      const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
      callbacksRef.current.onReverseGeocode(
        Cesium.Math.toDegrees(cartographic.latitude),
        Cesium.Math.toDegrees(cartographic.longitude),
      );
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    // Debug hook used by the verification script to assert real elevation.
    (window as unknown as { __garudaGlobe?: Cesium.Viewer }).__garudaGlobe = viewer;
    setReady(true);

    return () => {
      setReady(false);
      removeProgressListener();
      removeTerrainErrorListener?.();
      clickHandler.destroy();
      delete (window as unknown as { __garudaGlobe?: Cesium.Viewer }).__garudaGlobe;
      boundaryEntitiesRef.current.clear();
      viewerRef.current = null;
      if (!viewer.isDestroyed()) {
        viewer.destroy();
      }
    };
  }, []);

  // The mosaic is optional and resolves after the viewer starts. Never gate
  // the globe on a manifest request; add/remove the layer when it changes.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;

    if (mosaicLayerRef.current) {
      viewer.imageryLayers.remove(mosaicLayerRef.current, true);
      mosaicLayerRef.current = null;
    }
    if (mosaic) {
      mosaicLayerRef.current = addMosaicLayer(viewer, mosaic);
    }
    return () => {
      // The viewer-init effect cleans up first and destroys the viewer.
      if (mosaicLayerRef.current && !viewer.isDestroyed()) {
        viewer.imageryLayers.remove(mosaicLayerRef.current, true);
        mosaicLayerRef.current = null;
      }
    };
  }, [mosaic, ready]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;

    for (const entities of boundaryEntitiesRef.current.values()) {
      for (const entity of entities) viewer.entities.remove(entity);
    }
    boundaryEntitiesRef.current.clear();

    if (!boundaries) return;

    for (const feature of boundaries.features) {
      const props = feature.properties;
      const rings = ringsOf(feature);
      if (!rings.length) continue;

      const created: Cesium.Entity[] = [];

      rings.forEach((ring, ringIndex) => {
        const positions = ring.map(([lng, lat]) => Cesium.Cartesian3.fromDegrees(lng, lat));
        if (positions.length < 2) return;

        created.push(
          viewer.entities.add({
            id: ringIndex === 0 ? props.id : `${props.id}::ring${ringIndex}`,
            properties: { canonical_name: props.canonical_name },
            polyline: {
              positions,
              width: 2,
              material: BOUNDARY_COLOR,
              clampToGround: true,
            },
          }),
        );
      });

      if (typeof props.longitude === 'number' && typeof props.latitude === 'number') {
        created.push(
          viewer.entities.add({
            id: `${props.id}::label`,
            properties: { canonical_name: props.canonical_name },
            position: Cesium.Cartesian3.fromDegrees(props.longitude, props.latitude),
            label: {
              text: props.canonical_name,
              font: '600 13px "Plus Jakarta Sans", sans-serif',
              fillColor: Cesium.Color.WHITE,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 3,
              style: Cesium.LabelStyle.FILL_AND_OUTLINE,
              heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
              verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
              pixelOffset: new Cesium.Cartesian2(0, -6),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
              // At global zoom every pilot boundary collapses into one unreadable
              // cluster, so labels only appear once the camera is within 1500 km.
              distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 1_500_000),
            },
          }),
        );
      }

      if (created.length) {
        boundaryEntitiesRef.current.set(props.id, created);
      }
    }
  }, [boundaries, ready]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;

    for (const [placeId, entities] of boundaryEntitiesRef.current) {
      const selected = placeId === selectedId;
      for (const entity of entities) {
        if (entity.polyline) {
          entity.polyline.width = new Cesium.ConstantProperty(selected ? 5 : 2);
          entity.polyline.material = new Cesium.ColorMaterialProperty(
            selected ? SELECTED_COLOR : BOUNDARY_COLOR,
          );
        }
      }
    }
  }, [selectedId, boundaries, ready]);

  const flyTo = (target: { longitude: number; latitude: number; height: number }, pitch: number) => {
    viewerRef.current?.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(target.longitude, target.latitude, target.height),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(pitch), roll: 0 },
      duration: 2,
    });
  };

  return (
    <div className="globe-shell">
      <div ref={containerRef} className="globe-canvas" />

      <div className="globe-controls">
        <button type="button" onClick={() => flyTo(CAMERAS.earth, -90)}>
          Whole Earth
        </button>
        <button type="button" onClick={() => flyTo(CAMERAS.india, -55)}>
          India
        </button>
        <button type="button" onClick={() => flyTo(CAMERAS.odisha, -45)}>
          Odisha
        </button>
      </div>

      {tilesLoading && !terrainIssue && (
        <div className="globe-banner globe-banner--loading">Loading terrain tiles…</div>
      )}

      {terrainIssue && (
        <div className="globe-banner globe-banner--error" role="alert">
          <strong>Terrain unavailable.</strong> {terrainIssue}
          <span className="globe-banner__hint">
            The globe is showing the flat ellipsoid — elevation is not being rendered.
          </span>
        </div>
      )}
    </div>
  );
}
