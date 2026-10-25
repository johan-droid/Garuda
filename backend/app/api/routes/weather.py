"""Live IMD weather and NHM facility counts for a place.

Both routes answer the same question: is there live upstream data for this
place right now? A 200 does not mean yes. The client reads `status`;
`coverage_note` explains an absence and `data_gaps` names what is missing.

An unconfigured or unreachable upstream is an honest answer, not a server
error: these routes never raise on a provider failure. Because they answer a
specific location query, they are marked `no-store`.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps.session import get_db
from app.domain.common import DOMAIN_HEALTH, DOMAIN_WEATHER_DISASTERS, DataStatus
from app.domain.contracts import PanelResponse
from app.services.freshness import determine_status, summarize_domain
from app.services.provider_adapters import (
    BaseProviderAdapter,
    IMDWeatherAdapter,
    NHMHealthAdapter,
)

SessionDep = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="", tags=["live-providers"])


def _live_panel(adapter: BaseProviderAdapter, domain: str, place_id: str) -> PanelResponse:
    """Fetch from one upstream and render it as an independently-loaded panel.

    The adapter already reports *why* an upstream produced nothing (missing
    configuration, timeout, refusal), so the reason is carried through rather
    than replaced with a generic message.
    """
    now = datetime.now(UTC)
    try:
        observations = adapter.fetch_observations(place_id)
        sources = adapter.fetch_sources()
    except Exception as exc:  # noqa: BLE001 - a provider must never break the response
        return PanelResponse(
            domain=domain,
            status=DataStatus.UNAVAILABLE,
            sources=[],
            data_gaps=[f"{domain}_upstream"],
            coverage_note=f"{type(exc).__name__}: {exc}",
            error=str(exc),
        )

    # Judge freshness on the dates first. A publisher link says where a value
    # came from, not what period it describes, so it must not enter the
    # verdict above; it is attached afterwards for provenance only. The stored
    # status short-circuits `determine_status`, so the panel summary below
    # reaches the same answer.
    source_url = sources[0].url if sources else None
    for observation in observations:
        observation.quality_status = determine_status(observation, now)
        if observation.source_url is None:
            observation.source_url = source_url

    summary = summarize_domain(domain, observations, sources, now)
    missing = [o for o in observations if o.quality_status == DataStatus.UNAVAILABLE]
    data_gaps = [o.field_name for o in missing]
    if summary.status == DataStatus.UNAVAILABLE and not data_gaps:
        data_gaps = [f"{domain}_upstream"]

    return PanelResponse(
        domain=domain,
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
    "/places/{place_id}/weather",
    response_model=PanelResponse,
    summary="Live IMD weather observations for a place",
)
def weather(place_id: str, session: SessionDep, response: Response) -> PanelResponse:
    """Return live IMD weather for the place, or an explained absence.

    Served `no-store`: a weather reading is only useful while it is true.
    """
    _require_place(place_id, session)
    response.headers["Cache-Control"] = "no-store"
    return _live_panel(IMDWeatherAdapter(), DOMAIN_WEATHER_DISASTERS, place_id)


@router.get(
    "/places/{place_id}/health-facilities",
    response_model=PanelResponse,
    summary="Live NHM health facility counts for a place",
)
def health_facilities(place_id: str, session: SessionDep, response: Response) -> PanelResponse:
    """Return live NHM facility counts for the place, or an explained absence."""
    _require_place(place_id, session)
    response.headers["Cache-Control"] = "no-store"
    return _live_panel(NHMHealthAdapter(), DOMAIN_HEALTH, place_id)
