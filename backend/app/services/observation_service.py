"""Domain-scoped observation queries and health alert assembly.

The profile endpoint returns panels; this module answers the narrower
questions the UI asks directly: "show me every observation for this place in
this domain" and "show me the live health alerts for this place".

Health alerts are filtered on *expiry* at read time. An alert whose validity
window has passed is not silently presented as current; it is either marked
expired or excluded, and the caller is told which.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.common import DOMAIN_HEALTH, DataStatus, HealthCategory
from app.domain.contracts import HealthObservationView, Observation, SourceSummary
from app.models.entities import ObservationModel, SourceModel
from app.services.freshness import determine_status
from app.services.place_service import to_health_observation, to_observation, to_source_summary


def list_observations(
    session: Session,
    place_id: str,
    domain: str | None = None,
    limit: int = 100,
    offset: int = 0,
    period_start: date | None = None,
    period_end: date | None = None,
    include_stale: bool = True,
) -> tuple[list[Observation], int]:
    """Return observations for a place, optionally restricted to one domain.

    Returns the observations and the total number of matching rows, so the
    caller can paginate without a second count query.

    `period_start` / `period_end` filter on the observation's reference
    period. An observation with no reference period is treated as current
    and is therefore excluded when a period filter is supplied - a filter
    asking for "2026 data" must not return undated rows.

    `include_stale=False` drops observations whose recomputed status is
    `stale`. The default keeps them, because the response carries the status
    so the caller can decide how to present them.
    """
    if len(place_id) > settings.MAX_ID_LENGTH:
        return [], 0

    limit = max(1, min(limit, settings.MAX_PAGE_SIZE))
    offset = max(0, offset)

    conditions = [ObservationModel.place_id == place_id]
    if domain:
        conditions.append(ObservationModel.domain == domain)
    if period_start is not None:
        conditions.append(ObservationModel.reference_period_end.is_not(None))
        conditions.append(ObservationModel.reference_period_end >= period_start)
    if period_end is not None:
        conditions.append(ObservationModel.reference_period_start.is_not(None))
        conditions.append(ObservationModel.reference_period_start <= period_end)

    total = session.scalar(select(func.count()).select_from(ObservationModel).where(*conditions)) or 0

    rows = list(
        session.scalars(
            select(ObservationModel)
            .where(*conditions)
            .order_by(ObservationModel.field_name, ObservationModel.id)
            .limit(limit)
            .offset(offset)
        )
    )

    now = datetime.now(UTC)
    observations: list[Observation] = []
    for row in rows:
        if row.domain == DOMAIN_HEALTH:
            observations.append(to_health_observation(row, now))
        else:
            observations.append(to_observation(row))

    # Recompute status at read time so the age of the data is judged now.
    for observation in observations:
        observation.quality_status = determine_status(observation, now)

    if not include_stale:
        observations = [
            observation
            for observation in observations
            if observation.quality_status != DataStatus.STALE
        ]

    return observations, total


def sources_for_place(
    session: Session,
    place_id: str,
    domain: str | None = None,
) -> list[SourceSummary]:
    """Return the source summaries that back a place's observations."""
    conditions = [ObservationModel.place_id == place_id]
    if domain:
        conditions.append(ObservationModel.domain == domain)

    rows = list(session.scalars(select(ObservationModel).where(*conditions)))

    source_rows: dict[str, SourceModel] = {}
    reference_periods: dict[str, str] = {}
    for row in rows:
        if row.source_id not in source_rows and row.source is not None:
            source_rows[row.source_id] = row.source
        if row.source_id in reference_periods:
            continue
        if row.reference_period_start and row.reference_period_end:
            reference_periods[row.source_id] = (
                f"{row.reference_period_start.isoformat()} to {row.reference_period_end.isoformat()}"
            )
        elif row.reference_period_start:
            reference_periods[row.source_id] = row.reference_period_start.isoformat()

    return [
        to_source_summary(source, reference_periods.get(source_id))
        for source_id, source in source_rows.items()
    ]


def status_for_domain(session: Session, place_id: str, domain: str) -> DataStatus:
    """Return the aggregate status for a place/domain pair.

    The worst status wins: a panel is only `current` when every observation
    behind it is current.
    """
    observations, _ = list_observations(session, place_id, domain=domain, limit=settings.MAX_PAGE_SIZE)
    if not observations:
        return DataStatus.UNAVAILABLE
    statuses = {determine_status(observation) for observation in observations}
    for candidate in (
        DataStatus.CONFLICTING,
        DataStatus.UNAVAILABLE,
        DataStatus.UNVERIFIED,
        DataStatus.STALE,
        DataStatus.HISTORICAL,
        DataStatus.APPROXIMATE,
    ):
        if candidate in statuses:
            return candidate
    return DataStatus.CURRENT




def list_health_alerts(
    session: Session,
    place_id: str,
    include_expired: bool = False,
) -> dict[str, Any]:
    """Return the official health alerts that apply to a place.

    Only `official_alert` observations are included. Everything else in the
    health domain (historical case counts, surveillance summaries, prevention
    guidance) is a different kind of statement and must not be rendered as an
    alert.
    """
    if len(place_id) > settings.MAX_ID_LENGTH:
        return {"alerts": [], "expired_count": 0, "source_count": 0}

    rows = list(
        session.scalars(
            select(ObservationModel)
            .where(
                ObservationModel.place_id == place_id,
                ObservationModel.domain == DOMAIN_HEALTH,
                ObservationModel.health_category == HealthCategory.OFFICIAL_ALERT.value,
            )
            .order_by(ObservationModel.valid_until.is_(None), ObservationModel.valid_until)
        )
    )

    now = datetime.now(UTC)
    alerts: list[HealthObservationView] = []
    expired_count = 0
    source_ids: set[str] = set()

    for row in rows:
        view = to_health_observation(row, now)
        if view.expired:
            expired_count += 1
            if not include_expired:
                continue
        else:
            view.quality_status = determine_status(view, now)
        source_ids.add(row.source_id)
        alerts.append(view)

    return {
        "alerts": alerts,
        "expired_count": expired_count,
        "source_count": len(source_ids),
    }
