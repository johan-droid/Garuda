"""Latest available Sentinel-2 scene metadata for a place.

Returns a single scene observation from the Earth Search STAC public catalog,
not imagery pixels. The scene's acquisition date, cloud fraction, and source
are returned with explicit provenance.

The client must use `status` to distinguish a reported observation from an
unavailable or reluctant response. A successful HTTP 200 does not mean the
returned scene is current.

Because this answers a specific location query, it is marked `no-store`.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.orm import Session
from typing import Annotated

from app.api.deps.responses import json_with_etag
from app.api.deps.session import get_db
from app.core.config import settings

SessionDep = Annotated[Session, Depends(get_db)]
from app.domain.common import (
    DOMAIN_ENVIRONMENT,
    DataStatus,
)
from app.domain.contracts import (
    GetLatestObservationStatus,
    LatestObservationResponse,
    Observation,
    Place,
)
from app.services import observation_service
from app.services.provider_adapters import EarthSearchSentinelAdapter

router = APIRouter(prefix="", tags=["environment-scenes"])


def _extract_place_bbox(place_id: str, session: Session) -> tuple[float, float, float, float] | None:
    """Extract west, south, east, north from a place record."""
    from app.models.entities import PlaceModel
    place = session.get(PlaceModel, place_id)
    if place is None or place.latitude is None or place.longitude is None:
        return None
    # Use a default radius of ~5km at the place's location
    # Rough conversion: ~0.05 degrees ≈ 5km at the equator
    lat = place.latitude
    lng = place.longitude
    # Bounding box ±0.05 degrees (approximately 5km)
    west = lng - 0.05
    south = lat - 0.05
    east = lng + 0.05
    north = lat + 0.05
    return (west, south, east, north)


@router.get(
    "/places/{place_id}/environment-scenes",
    response_model=LatestObservationResponse,
    summary="Latest available Sentinel-2 scene metadata for a place",
)
def environment_scenes(
    place_id: str,
    session: SessionDep,
    response: Response,
    raise_on_error: Annotated[bool, Query(description="If true, propagate provider errors to the client.")] = False,
) -> Any:
    """Return imagery metadata for the latest available Sentinel-2 L2A scene covering the place.

    This endpoint returns a single scene observation from the Earth Search STAC
    public catalog, not imagery pixels. The scene's acquisition date, cloud
    fraction, and source are returned with explicit provenance.

    The client must use `status` to distinguish a reported observation from an
    unavailable or reluctant response. A successful HTTP 200 does not mean the
    returned scene is current.

    Because this answers a specific location query, it is marked `no-store`.
    """
    # First verify the place exists
    from app.models.entities import PlaceModel
    place = session.get(PlaceModel, place_id)
    if place is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")

    # Extract bbox from place coordinates
    bbox = _extract_place_bbox(place_id, session)
    if bbox is None:
        # Place has no coordinates; return unavailable
        now = datetime.now(UTC)
        return LatestObservationResponse(
            place=Place(
                id=place_id,
                canonical_name=place_id,
                place_type="point",
                coordinates=(place.longitude, place.latitude) if (place.longitude is not None and place.latitude is not None) else None,
                geometry_available=False,
            ),
            field_name="latest_sentinel2_scene",
            status=GetLatestObservationStatus.UNAVAILABLE,
            unavailable_reason="Place has no geocoded coordinates.",
            retrieved_at=now,
            coverage_note="The place record does not have latitude/longitude data; cannot query STAC catalog.",
            data_gaps=["place_coordinates"],
        )

    west, south, east, north = bbox
    adapter = EarthSearchSentinelAdapter()
    try:
        observations = adapter.fetch_observations_for_bbox(west, south, east, north)
    except Exception as exc:
        if raise_on_error:
            raise
        now = datetime.now(UTC)
        return LatestObservationResponse(
            place=Place(
                id=place_id,
                canonical_name=place_id,
                place_type="point",
                coordinates=(place.longitude, place.latitude) if (place.longitude is not None and place.latitude is not None) else None,
                geometry_available=False,
            ),
            field_name="latest_sentinel2_scene",
            status=GetLatestObservationStatus.UNAVAILABLE,
            unavailable_reason=str(exc),
            retrieved_at=now,
            coverage_note=f"Sentinel STAC query failed: {exc}",
            data_gaps=["sentinel_stac_query"],
        )

    if not observations:
        now = datetime.now(UTC)
        return LatestObservationResponse(
            place=Place(
                id=place_id,
                canonical_name=place_id,
                place_type="point",
                coordinates=(place.longitude, place.latitude) if (place.longitude is not None and place.latitude is not None) else None,
                geometry_available=False,
            ),
            field_name="latest_sentinel2_scene",
            status=GetLatestObservationStatus.UNAVAILABLE,
            unavailable_reason="No Sentinel-2 scene found covering this area.",
            retrieved_at=now,
            coverage_note="No Sentinel-2 L2A scene with cloud cover ≤40% was found covering the area near this place in the searched date window.",
            data_gaps=["no_sentinel_scene"],
        )

    # observations is a list; take the first (best) one
    obs = observations[0]

    # Build the response
    retrieved_at = obs.retrieved_at
    # Map the observation fields to the response model
    return LatestObservationResponse(
        place=Place(
            id=place.id,
            canonical_name=place.canonical_name,
            place_type=place.place_type,
            coordinates=place.coordinates,
            geometry_available=place.geometry_available,
        ),
        field_name=obs.field_name,
        status=GetLatestObservationStatus.CURRENT,
        observation=Observation(
            field_name=obs.field_name,
            value=obs.value,
            unit=obs.unit,
            place_id=obs.place_id,
            source_id=obs.source_id,
            reference_period_start=obs.reference_period_start,
            reference_period_end=obs.reference_period_end,
            published_at=obs.published_at,
            retrieved_at=obs.retrieved_at,
            quality_status=obs.quality_status,
            licence=obs.licence,
            notes=obs.notes,
            domain=obs.domain,
            source_url=obs.source_url,
            satellite_mission=obs.satellite_mission,
            resolution_meters=obs.resolution_meters,
            cloud_cover_percentage=obs.cloud_cover_percentage,
            scene_timestamp=obs.scene_timestamp,
        ),
        unavailable_reason=None,
        retrieved_at=retrieved_at,
        coverage_note=None,
        data_gaps=[],
    )