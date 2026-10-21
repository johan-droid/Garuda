"""Cross-place observation queries.

The place-scoped view lives at `/places/{place_id}/observations`. This router
serves the questions that span places: "which sources have published health
data in Odisha", "what changed most recently".

Every observation carries its provenance, so these responses are as
attributable as the place-scoped ones.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
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
)
from app.models.entities import ObservationModel
from app.services.freshness import determine_status
from app.services.place_service import recent_observations, to_health_observation, to_observation

router = APIRouter(prefix="/observations", tags=["observations"])

SessionDep = Annotated[Session, Depends(get_db)]


@router.get("", summary="List observations across places")
def list_observations(
    request: Request,
    session: SessionDep,
    place_id: Annotated[str | None, Query(max_length=64)] = None,
    domain: Annotated[str | None, Query(max_length=64)] = None,
    source_id: Annotated[str | None, Query(max_length=128)] = None,
    field_name: Annotated[str | None, Query(max_length=128)] = None,
    period_start: Annotated[date | None, Query(description="Earliest reference period")] = None,
    period_end: Annotated[date | None, Query(description="Latest reference period")] = None,
    include_stale: Annotated[bool, Query(description="Include stale observations")] = True,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response:
    """Return observations matching the supplied filters.

    Results are ordered by retrieval time, newest first, so a client polling
    for changes sees them in the order they arrived.
    """
    limit = max(1, min(limit, settings.MAX_PAGE_SIZE))
    offset = max(0, offset)

    conditions = []
    if place_id:
        conditions.append(ObservationModel.place_id == place_id)
    if domain:
        conditions.append(ObservationModel.domain == domain)
    if source_id:
        conditions.append(ObservationModel.source_id == source_id)
    if field_name:
        conditions.append(ObservationModel.field_name == field_name)
    if period_start is not None:
        conditions.append(
            ObservationModel.reference_period_end.is_not(None),
            ObservationModel.reference_period_end >= period_start,
        )
    if period_end is not None:
        conditions.append(
            ObservationModel.reference_period_start.is_not(None),
            ObservationModel.reference_period_start <= period_end,
        )

    total = len(list(session.scalars(select(ObservationModel.id).where(*conditions))))
    rows = list(
        session.scalars(
            select(ObservationModel)
            .where(*conditions)
            .order_by(ObservationModel.retrieved_at.desc(), ObservationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )

    now = datetime.now(UTC)
    observations: list[Any] = []
    for row in rows:
        if row.domain == DOMAIN_HEALTH:
            view = to_health_observation(row, now)
            view.quality_status = determine_status(view, now)
            observations.append(view)
        else:
            view = to_observation(row)
            view.quality_status = determine_status(view, now)
            observations.append(view)

    if not include_stale:
        observations = [
            observation
            for observation in observations
            if observation.quality_status != DataStatus.STALE
        ]

    payload: dict[str, Any] = {
        "observations": observations,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "place_id": place_id,
            "domain": domain,
            "source_id": source_id,
            "field_name": field_name,
            "period_start": period_start,
            "period_end": period_end,
        },
    }
    return json_with_etag(request, payload)


@router.get("/domains", summary="Known data domains")
def domains() -> dict[str, Any]:
    """Return the domains this API serves as independently-loaded panels."""
    return {
        "domains": [
            DOMAIN_DEMOGRAPHICS,
            DOMAIN_HEALTH,
            DOMAIN_SERVICES,
            DOMAIN_INFRASTRUCTURE,
            DOMAIN_ENVIRONMENT,
            DOMAIN_RESILIENCE,
            DOMAIN_HISTORY_CULTURE,
            DOMAIN_WEATHER_DISASTERS,
        ]
    }


@router.get("/recent", summary="Most recently retrieved observations")
def recent(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = 10,
) -> dict[str, Any]:
    """Return the most recently retrieved observations (operator view)."""
    return {"observations": recent_observations(session, limit=limit)}
