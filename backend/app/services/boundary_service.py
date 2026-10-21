"""Boundary GeoJSON loading, point-in-polygon resolution, and reverse geocoding.

Provides fast, dependency-free reverse geocoding against the pilot administrative
hierarchy (Odisha state, Khordha district, and the 8 subdistrict blocks).
"""

from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.domain.contracts import AdminHierarchy, Place, ReverseGeocodeResponse
from app.models.entities import PlaceModel
from app.services.place_service import build_hierarchy, get_place, load_aliases, _to_place


def _find_geojson_path() -> Path:
    """Locate the pilot boundaries GeoJSON fixture file."""
    candidates = [
        Path(__file__).resolve().parents[2] / "data" / "fixtures" / "boundaries" / "khordha_pilot.geojson",
        Path.cwd() / "backend" / "data" / "fixtures" / "boundaries" / "khordha_pilot.geojson",
        Path.cwd() / "data" / "fixtures" / "boundaries" / "khordha_pilot.geojson",
        Path(__file__).resolve().parents[3] / "data" / "fixtures" / "boundaries" / "khordha_pilot.geojson",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@lru_cache(maxsize=1)
def load_pilot_boundaries() -> dict[str, Any]:
    """Load and cache the pilot GeoJSON feature collection."""
    path = _find_geojson_path()
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_boundaries_feature_collection(
    place_type: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Return the GeoJSON FeatureCollection, optionally filtered by place_type or parent_id."""
    data = load_pilot_boundaries()
    features = data.get("features", [])

    if place_type:
        features = [f for f in features if f.get("properties", {}).get("place_type") == place_type]
    if parent_id:
        features = [f for f in features if f.get("properties", {}).get("parent_id") == parent_id]

    return {
        "type": "FeatureCollection",
        "name": data.get("name", "khordha_pilot_boundaries"),
        "crs": data.get("crs"),
        "features": features,
    }


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    """Ray casting algorithm to determine if point (x=lng, y=lat) is in a polygon ring."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    p1x, p1y = ring[0]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n]
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or x <= xinters:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def point_in_geometry(lng: float, lat: float, geometry: dict[str, Any]) -> bool:
    """Check if coordinate (lng, lat) falls within a GeoJSON Polygon or MultiPolygon."""
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if geom_type == "Polygon":
        if not coords:
            return False
        # First ring is exterior boundary
        if point_in_ring(lng, lat, coords[0]):
            # Test interior holes
            for hole in coords[1:]:
                if point_in_ring(lng, lat, hole):
                    return False
            return True
        return False
    elif geom_type == "MultiPolygon":
        for poly in coords:
            if poly and point_in_ring(lng, lat, poly[0]):
                in_hole = False
                for hole in poly[1:]:
                    if point_in_ring(lng, lat, hole):
                        in_hole = True
                        break
                if not in_hole:
                    return True
        return False
    return False


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 2)


def reverse_geocode(session: Session, lat: float, lng: float) -> ReverseGeocodeResponse:
    """Reverse geocode coordinates to the enclosing or nearest supported place in the pilot hierarchy.

    Hierarchy checks subdistricts first (most granular), then district, then state.
    If outside all polygons, falls back to the nearest supported centroid.
    """
    boundaries = load_pilot_boundaries()
    features = boundaries.get("features", [])

    subdistricts = [f for f in features if f.get("properties", {}).get("place_type") == "subdistrict"]
    districts = [f for f in features if f.get("properties", {}).get("place_type") == "district"]
    states = [f for f in features if f.get("properties", {}).get("place_type") == "state"]

    matched_feature: dict[str, Any] | None = None
    match_type = "enclosing"
    distance_km = 0.0

    # 1. Check subdistricts (most specific)
    for feat in subdistricts:
        if point_in_geometry(lng, lat, feat.get("geometry", {})):
            matched_feature = feat
            break

    # 2. Check district
    if matched_feature is None:
        for feat in districts:
            if point_in_geometry(lng, lat, feat.get("geometry", {})):
                matched_feature = feat
                break

    # 3. Check state
    if matched_feature is None:
        for feat in states:
            if point_in_geometry(lng, lat, feat.get("geometry", {})):
                matched_feature = feat
                break

    # 4. If outside all polygons, find nearest centroid
    if matched_feature is None and features:
        min_dist = float("inf")
        nearest_feat = None
        for feat in features:
            props = feat.get("properties", {})
            f_lat = props.get("latitude")
            f_lng = props.get("longitude")
            if f_lat is not None and f_lng is not None:
                dist = haversine_distance_km(lat, lng, f_lat, f_lng)
                if dist < min_dist:
                    min_dist = dist
                    nearest_feat = feat
        if nearest_feat is not None:
            matched_feature = nearest_feat
            match_type = "nearest"
            distance_km = min_dist

    if matched_feature is None:
        raise ValueError("No supported boundaries available.")

    props = matched_feature.get("properties", {})
    place_id = props.get("id")

    # Resolve from DB if present
    place_row = get_place(session, place_id) if place_id else None
    if place_row is not None:
        place = _to_place(place_row, load_aliases(session, place_id))
        hierarchy = build_hierarchy(session, place_row)
    else:
        # Fallback to feature properties when DB row not yet seeded
        coords = None
        if props.get("latitude") is not None and props.get("longitude") is not None:
            coords = (props["latitude"], props["longitude"])
        place = Place(
            id=props["id"],
            canonical_name=props["canonical_name"],
            aliases=[],
            place_type=props["place_type"],
            parent_id=props.get("parent_id"),
            coordinates=coords,
            resolution_method="boundary_lookup",
            geometry_available=True,
        )
        hierarchy = AdminHierarchy()
        if props.get("place_type") == "state":
            hierarchy.state = props["canonical_name"]
        elif props.get("place_type") == "district":
            hierarchy.state = "Odisha"
            hierarchy.district = props["canonical_name"]
        elif props.get("place_type") == "subdistrict":
            hierarchy.state = "Odisha"
            hierarchy.district = "Khordha"
            hierarchy.subdistrict = props["canonical_name"]

    return ReverseGeocodeResponse(
        place=place,
        hierarchy=hierarchy,
        match_type=match_type,
        distance_km=distance_km,
        latitude=lat,
        longitude=lng,
    )
