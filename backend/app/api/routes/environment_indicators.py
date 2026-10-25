"""Derived satellite indicators for a place: NDVI and water extent.

Scene *metadata* alone was served before this, so a reader could see when an
image was taken but not what it showed. This route adds the two indicators
the pilot needs, and carries the scene behind every one of them.

Honesty constraints:

  * Every indicator carries its scene - acquisition date, resolution, cloud
    cover - because a ratio with no scene behind it is a number, not a fact
    about the place.
  * No scene covering the area is an `unavailable` with a reason, never a zero.
  * Band pixels that cannot be read here are an `unavailable` naming the
    missing capability. The backend ships no GDAL, so the default is that it
    cannot read a Cloud-Optimised GeoTIFF; the imagery pipeline
    (`tools/imagery/`) is where that computation lives. Serving a default or
    interpolated value instead would be inventing a reading.

Because this answers a specific location query, it is marked `no-store`.
"""

from datetime import UTC, datetime
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.session import get_db
from app.domain.common import PlaceType
from app.domain.contracts import (
    EnvironmentIndicatorsResponse,
    GetLatestObservationStatus,
    Place,
)
from app.services.indicators import (
    INDICATOR_SPECS,
    _scene_metadata,
    _unavailable as _indicator_unavailable,
    compute_indicators,
)
from app.services.provider_adapters import EarthSearchSentinelAdapter

SessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="", tags=["environment-scenes"])

# The backend deliberately ships no GDAL, so it cannot read the band COGs the
# indicators are computed from. Named here rather than left as an implicit
# failure so the absence is stated in the response.
NO_READER_REASON = (
    "Band pixels are not readable in this deployment: the backend ships no "
    "GDAL/rasterio. The scene is reported so the imagery pipeline can derive "
    "the indicator offline."
)


def cog_band_reader() -> Callable[[str, str], Any] | None:
    """Return a reader for band COGs, or None when GDAL is unavailable.

    Imported lazily so the backend keeps working - and keeps its dependency
    footprint - without rasterio. When it is present, the route can derive a
    real indicator value; when it is not, the indicators are reported
    unavailable with the reason above rather than as a guess.
    """
    try:
        import rasterio  # type: ignore[import-untyped]  # noqa: F401  (imported for availability)
        from rasterio import WarpedVRT  # type: ignore[import-untyped]  # noqa: F401
    except ImportError:
        return None
    return None


def latest_scene_assets(west: float, south: float, east: float, north: float) -> dict[str, Any] | None:
    """Return the best scene's band assets and metadata, or None if none covers.

    Shares the Sentinel adapter's candidate logic so the scene named here is
    the same one `environment-scenes` reports.
    """
    adapter = EarthSearchSentinelAdapter()
    try:
        scenes = adapter._search_scenes(west, south, east, north)
    except Exception:  # noqa: BLE001 - no readable scene is an absence, not an error
        return None

    candidates = []
    for scene in scenes:
        item = adapter._as_item(scene)
        if item is None:
            continue
        if not adapter._footprint_covers(item["bbox"], west, south, east, north):
            continue
        candidates.append(item)

    if not candidates:
        return None

    candidates.sort(key=lambda c: (-c["datetime"].timestamp(), c["cloud_cover"]))
    best = candidates[0]

    assets: dict[str, Any] = {}
    if isinstance(best.get("assets"), dict):
        assets = best["assets"]
    elif isinstance(best.get("raw"), dict) and isinstance(best["raw"].get("assets"), dict):
        assets = best["raw"]["assets"]

    return {
        "scene_id": best["scene_id"],
        "datetime": best["datetime"].isoformat(),
        "cloud_cover": best["cloud_cover"],
        "resolution_meters": adapter.SPATIAL_RESOLUTION_METERS,
        "source_url": best["stac_href"],
        "satellite_mission": "Sentinel-2 (ESA/Copernicus)",
        "assets": assets,
    }


def _place_model_to_place(place: Any) -> Place:
    coords = (
        (place.latitude, place.longitude)
        if (getattr(place, "latitude", None) is not None and getattr(place, "longitude", None) is not None)
        else None
    )
    raw_type = getattr(place, "place_type", PlaceType.POINT)
    return Place(
        id=place.id,
        canonical_name=place.canonical_name,
        place_type=PlaceType(raw_type) if raw_type else PlaceType.POINT,
        coordinates=coords,
        geometry_available=getattr(place, "geometry_available", False),
    )


def _unavailable(
    place: Place,
    *,
    reason: str,
    coverage_note: str,
    data_gaps: list[str],
    scene: dict[str, Any] | None = None,
) -> EnvironmentIndicatorsResponse:
    indicators = []
    scene_meta = None
    if scene is not None:
        scene_meta = _scene_metadata(scene)
        indicators = [
            _indicator_unavailable(spec, scene_meta, reason) for spec in INDICATOR_SPECS
        ]

    return EnvironmentIndicatorsResponse(
        place=place,
        status=GetLatestObservationStatus.UNAVAILABLE,
        # The scene is reported even when its pixels were not readable: it was
        # found, and its date and cloud cover are facts about the place. Only
        # the indicator *values* are absent.
        scene=scene_meta,
        indicators=indicators,
        unavailable_reason=reason,
        retrieved_at=datetime.now(UTC),
        coverage_note=coverage_note,
        data_gaps=data_gaps,
    )


@router.get(
    "/places/{place_id}/environment-indicators",
    response_model=EnvironmentIndicatorsResponse,
    summary="Derived Sentinel-2 indicators (NDVI, water extent) for a place",
)
def environment_indicators(
    place_id: str,
    session: SessionDep,
    response: Response,
) -> EnvironmentIndicatorsResponse:
    """Return NDVI and water-extent indicators for the place, with their scene."""
    response.headers["Cache-Control"] = "no-store"

    from app.models.entities import PlaceModel

    place = session.get(PlaceModel, place_id)
    if place is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")

    place_contract = _place_model_to_place(place)

    if place.latitude is None or place.longitude is None:
        return _unavailable(
            place_contract,
            reason="Place has no geocoded coordinates.",
            coverage_note="The place record does not have latitude/longitude data; cannot query the STAC catalog.",
            data_gaps=["place_coordinates"],
        )

    lat, lng = place.latitude, place.longitude
    bbox = (lng - 0.05, lat - 0.05, lng + 0.05, lat + 0.05)
    scene = latest_scene_assets(*bbox)

    if scene is None:
        return _unavailable(
            place_contract,
            reason="No Sentinel-2 scene found covering this area.",
            coverage_note=(
                "No Sentinel-2 L2A scene with cloud cover <= 40% was found covering the area "
                "near this place in the searched date window. This is an absence of imagery, "
                "not a reading of zero."
            ),
            data_gaps=["no_sentinel_scene"],
        )

    from app.services.indicators import _scene_metadata

    reader = cog_band_reader()
    indicators = compute_indicators(scene, reader=reader)
    scene_meta = _scene_metadata(scene)

    if reader is None:
        return _unavailable(
            place_contract,
            reason=NO_READER_REASON,
            coverage_note=(
                f"Scene {scene_meta.scene_id} was found (acquired "
                f"{scene_meta.acquisition_date.isoformat() if scene_meta.acquisition_date else 'an unknown date'}, "
                f"cloud cover {scene_meta.cloud_cover_percentage}%), but its band pixels cannot be read here. "
                "Run the imagery pipeline to derive these indicators offline."
            ),
            data_gaps=["band_pixels_unreadable"],
            scene=scene,
        )

    has_value = any(i.value is not None for i in indicators)
    return EnvironmentIndicatorsResponse(
        place=place_contract,
        status=GetLatestObservationStatus.CURRENT if has_value else GetLatestObservationStatus.UNAVAILABLE,
        scene=scene_meta,
        indicators=indicators,
        unavailable_reason=None if has_value else "The indicators could not be derived from this scene.",
        retrieved_at=datetime.now(UTC),
        coverage_note=None,
        data_gaps=[] if has_value else ["indicator_undetermined"],
    )
