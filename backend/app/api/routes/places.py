"""Place search, profile, observations, and alerts.

These are the public read endpoints. They carry no authentication because the
data they expose is public information with published provenance.

Two rules shape the responses:

  * "We do not know" is never rendered as a zero. A domain with no data
    returns `status: unavailable` with an explicit data-gap note, never a
    panel full of zeros.
  * A health alert is only ever rendered as an alert when it really is one:
    the alerts endpoint returns only `official_alert` observations and
    excludes expired ones.
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.responses import json_with_etag
from app.api.deps.session import get_db
from app.core.config import settings
from app.domain.common import (
    DOMAIN_DEMOGRAPHICS,
    DOMAIN_ENVIRONMENT,
    DOMAIN_HEALTH,
    DOMAIN_HISTORY_CULTURE,
    DOMAIN_INFRASTRUCTURE,
    DOMAIN_RESILIENCE,
    DOMAIN_SERVICES,
    DOMAIN_WEATHER_DISASTERS,
    DataStatus,
    PlaceType,
)
from app.domain.contracts import PlaceProfile, ReverseGeocodeResponse, SearchResponse
from app.services import observation_service
from app.services.boundary_service import get_boundaries_feature_collection, reverse_geocode
from app.services.place_service import get_place, get_profile, search_places, reverse_geocode

router = APIRouter(prefix="/places", tags=["places"])

# Domains served as profile panels.
PROFILE_DOMAINS = (
    DOMAIN_DEMOGRAPHICS,
    DOMAIN_HEALTH,
    DOMAIN_SERVICES,
    DOMAIN_INFRASTRUCTURE,
    DOMAIN_ENVIRONMENT,
    DOMAIN_RESILIENCE,
    DOMAIN_HISTORY_CULTURE,
    DOMAIN_WEATHER_DISASTERS,
)

SessionDep = Annotated[Session, Depends(get_db)]
PlaceIdPath = Annotated[
    str,
    Path(min_length=1, max_length=64, description="Stable place identifier"),
]


@router.get("/search", response_model=SearchResponse, summary="Search for places")
def search(
    request: Request,
    session: SessionDep,
    q: Annotated[str, Query(max_length=settings.MAX_SEARCH_QUERY_LENGTH, description="Place name or alias")] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    type: Annotated[str | None, Query(description="Filter by place type")] = None,
) -> Response:
    """Search for places by name.

    The response carries `degraded` and `notes` so a client can state plainly
    when results are incomplete rather than presenting a partial list as
    exhaustive.
    """
    if not q.strip():
        payload = SearchResponse(query="", results=[], total=0, limit=limit, offset=offset)
        return json_with_etag(request, payload)

    if type is not None and type not in {item.value for item in PlaceType}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported place type filter.",
        )

    try:
        payload = search_places(session, q, limit=limit, offset=offset, place_type=type)
    except ValueError as exc:
        # The service raises a safe, operator-written message (query too long).
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return json_with_etag(request, payload)


@router.get("/boundaries", summary="GeoJSON boundaries for supported places")
def boundaries(
    request: Request,
    place_type: Annotated[str | None, Query(description="Filter by place type (e.g. state, district, subdistrict)")] = None,
    parent_id: Annotated[str | None, Query(description="Filter by parent place ID")] = None,
) -> Response:
    """Return GeoJSON FeatureCollection of supported pilot boundaries."""
    payload = get_boundaries_feature_collection(place_type=place_type, parent_id=parent_id)
    return json_with_etag(request, payload)


@router.get("/{place_id}/profile", response_model=PlaceProfile, summary="Place profile")
def profile(place_id: PlaceIdPath, session: SessionDep, response: Response) -> PlaceProfile:
    """Return the multi-panel profile for a place.

    Each panel is loaded independently, so a failure in one domain does not
    prevent the others from being served. The profile answers a specific
    location query, so it is marked `no-store`.
    """
    result = get_profile(session, place_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{place_id}/observations", summary="Observations for a place")
def observations(
    place_id: PlaceIdPath,
    session: SessionDep,
    domain: Annotated[str | None, Query(description="Filter by domain")] = None,
    period_start: Annotated[date | None, Query(description="Earliest reference period")] = None,
    period_end: Annotated[date | None, Query(description="Latest reference period")] = None,
    include_stale: Annotated[bool, Query(description="Include stale observations")] = True,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Return the observations behind a place's panels, with full provenance.

    Every observation carries its source id, reference period, retrieval time,
    licence, and a recomputed quality status, so the caller can show where a
    figure came from and how old it is.
    """
    if get_place(session, place_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")

    if domain is not None and domain not in PROFILE_DOMAINS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown domain '{domain}'.",
        )

    if period_start and period_end and period_end < period_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period_end must not be earlier than period_start.",
        )

    rows, total = observation_service.list_observations(
        session,
        place_id,
        domain=domain,
        limit=limit,
        offset=offset,
        period_start=period_start,
        period_end=period_end,
        include_stale=include_stale,
    )

    return {
        "place_id": place_id,
        "domain": domain,
        "observations": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "sources": observation_service.sources_for_place(session, place_id, domain=domain),
    }


@router.get("/{place_id}/alerts", summary="Official health alerts for a place")
def alerts(
    place_id: PlaceIdPath,
    session: SessionDep,
    include_expired: Annotated[bool, Query(description="Include recently expired alerts")] = False,
) -> dict[str, Any]:
    """Return the official health alerts that apply to a place.

    Only `official_alert` observations are returned. Historical case counts,
    surveillance summaries, and modelled risk are different kinds of
    statement and are never presented as alerts.

    Expired alerts are excluded by default but always counted, so the client
    can say "no active alerts" while still disclosing that alerts existed and
    have lapsed.
    """
    if get_place(session, place_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")

    result = observation_service.list_health_alerts(
        session, place_id, include_expired=include_expired
    )
    active = result["alerts"]
    return {
        "place_id": place_id,
        "active_alerts": active,
        "expired_count": result["expired_count"],
        "source_count": result["source_count"],
        "note": (
            "No active alerts from connected sources."
            if not active
            else "Active alerts are shown with their issuing authority and expiry."
        ),
    }


@router.get("/{place_id}/status", summary="Per-domain data status for a place")
def status_summary(place_id: PlaceIdPath, session: SessionDep) -> dict[str, Any]:
    """Return the freshness and provenance status of each domain for a place.

    This is what the profile header renders: a per-domain badge showing
    whether the figures behind it are current, stale, or unavailable.
    """
    if get_place(session, place_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")

    domains = []
    for domain in PROFILE_DOMAINS:
        domain_status = observation_service.status_for_domain(session, place_id, domain)
        domain_rows, total = observation_service.list_observations(
            session, place_id, domain=domain, limit=settings.MAX_PAGE_SIZE
        )
        sources = observation_service.sources_for_place(session, place_id, domain=domain)
        latest = max(
            (observation.retrieved_at for observation in domain_rows),
            default=None,
        )
        domains.append(
            {
                "domain": domain,
                "status": domain_status,
                "observation_count": total,
                "source_count": len(sources),
                "last_updated": latest,
            }
        )

    return {
        "place_id": place_id,
        "domains": domains,
        "worst_status": _worst_status(domains),
    }


def _worst_status(domains: list[dict[str, Any]]) -> DataStatus:
    """Return the most severe status across the domains."""
    for candidate in (
        DataStatus.CONFLICTING,
        DataStatus.UNAVAILABLE,
        DataStatus.UNVERIFIED,
        DataStatus.STALE,
        DataStatus.HISTORICAL,
        DataStatus.APPROXIMATE,
    ):
        if any(domain["status"] == candidate for domain in domains):
            return candidate
    return DataStatus.CURRENT


@router.get(
    "/reverse",
    response_model=ReverseGeocodeResponse,
    summary="Reverse geocode a coordinate pair",
)
async def reverse(
    session: SessionDep,
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
) -> ReverseGeocodeResponse:
    """Reverse geocode a coordinate pair using keyless public APIs.

    Fetches concurrently:
      1. Nominatim OSM reverse geocoding
      2. Open-Meteo point weather & air quality
      3. Wikipedia location intelligence summary

    Responses are cached per (lat, lon) pair:
      * Weather: 15 minute TTL
      * Geocoding/Wikipedia: 24 hour TTL

    The `inside_coverage` field is always True for reverse geocode since
    any point on Earth can be resolved.
    """
    result = await reverse_geocode(lat, lon)
    return ReverseGeocodeResponse(
        place=result.place,
        hierarchy=result.hierarchy,
        match_type=result.match_type if hasattr(result, "match_type") else "enclosing",
        distance_km=result.distance_km,
        latitude=result.latitude,
        longitude=result.longitude,
        inside_coverage=result.inside_coverage,
        coverage_note=result.coverage_note,
    )

