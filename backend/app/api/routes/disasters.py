"""Live NDMA disaster bulletins for a place.

This route exists because weather observations and hazard advisories are
different kinds of statement and must not be judged by the same rule. The
panel it returns carries each record's `record_type`, so a client can tell a
measurement from a projection from a warning - and the freshness verdict
already reflects which rule was applied:

  * `forecast`     - served as `forecast`, never `current`.
  * `alert`        - served `current` while its validity window holds, and
                     `unavailable` once it has expired.
  * `observation`  - judged on its own date.

An unconfigured or unreachable NDMA is an explained absence, not a server
error: the endpoint never raises on a provider failure.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.session import get_db
from app.domain.common import DOMAIN_WEATHER_DISASTERS, DataStatus
from app.domain.contracts import PanelResponse
from app.services.freshness import determine_status, summarize_domain
from app.services.ndma_adapter import NDMADisasterAdapter
from app.services.provider_adapters import BaseProviderAdapter

SessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="", tags=["live-providers"])


def _disaster_panel(adapter: BaseProviderAdapter, place_id: str) -> PanelResponse:
    """Fetch hazard records and render them as an independently-loaded panel.

    Each record's status is recomputed here, after the record type is known,
    so the verdict matches the kind of statement rather than a generic age
    check. The adapter's own reason for producing nothing travels through in
    `coverage_note` rather than being replaced.
    """
    now = datetime.now(UTC)
    try:
        observations = adapter.fetch_observations(place_id)
        sources = adapter.fetch_sources()
    except Exception as exc:  # noqa: BLE001 - a provider must never break the response
        return PanelResponse(
            domain=DOMAIN_WEATHER_DISASTERS,
            status=DataStatus.UNAVAILABLE,
            sources=[],
            data_gaps=[f"{DOMAIN_WEATHER_DISASTERS}_upstream"],
            coverage_note=f"{type(exc).__name__}: {exc}",
            error=str(exc),
        )

    # Freshness is judged on the dates first. A publisher link says where a
    # value came from, not what period it describes, so it must not enter the
    # verdict; it is attached afterwards for provenance only. Same hazard the
    # IMD route documents.
    source_url = sources[0].url if sources else None
    for observation in observations:
        observation.quality_status = determine_status(observation, now)
        if observation.source_url is None:
            observation.source_url = source_url

    summary = summarize_domain(DOMAIN_WEATHER_DISASTERS, observations, sources, now)
    missing = [o for o in observations if o.quality_status == DataStatus.UNAVAILABLE]
    data_gaps = [o.field_name for o in missing]
    if summary.status == DataStatus.UNAVAILABLE and not data_gaps:
        data_gaps = [f"{DOMAIN_WEATHER_DISASTERS}_upstream"]

    return PanelResponse(
        domain=DOMAIN_WEATHER_DISASTERS,
        status=summary.status,
        observations=observations,
        sources=sources,
        last_updated=summary.last_updated,
        coverage_note=next((o.notes for o in missing), None) or summary.message,
        data_gaps=data_gaps,
    )


def _require_place(place_id: str, session: Session) -> None:
    from app.models.entities import PlaceModel

    if session.get(PlaceModel, place_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found.")


@router.get(
    "/places/{place_id}/disasters",
    response_model=PanelResponse,
    summary="Live NDMA hazard bulletins for a place",
)
def disasters(place_id: str, session: SessionDep, response: Response) -> PanelResponse:
    """Return live NDMA advisories, forecasts and observations for the place.

    Served `no-store`: a warning is only useful while it is true, and this
    route is where expiry is decided.
    """
    _require_place(place_id, session)
    response.headers["Cache-Control"] = "no-store"
    return _disaster_panel(NDMADisasterAdapter(), place_id)
