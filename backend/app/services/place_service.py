"""Place resolution, search, and profile assembly.

Search is deliberately simple and local (substring match over the `places`
table). An external geocoder can be added later behind the same interface;
the response contract already carries `degraded` and `notes` so the UI can
state plainly when results are incomplete.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

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
    HealthCategory,
)
from app.domain.contracts import (
    AdminHierarchy,
    HealthObservationView,
    Observation,
    PanelResponse,
    Place,
    PlaceProfile,
    SearchResponse,
    SearchResult,
    SourceSummary,
)
from app.models.entities import ObservationModel, PlaceAliasModel, PlaceModel, SourceModel
from app.services.cache import cached_response
from app.services.freshness import determine_status, summarize_domain


def _normalize(query: str) -> str:
    """Normalise a search query for matching."""
    return " ".join(query.strip().lower().split())


def search_places(
    session: Session,
    query: str,
    limit: int = 20,
    offset: int = 0,
    place_type: str | None = None,
) -> SearchResponse:
    """Search for places by name or alias.

    The query is length-limited and the page size is capped, so a malicious
    client cannot force an unbounded scan.
    """
    trimmed = query.strip()
    if not trimmed:
        return SearchResponse(query=trimmed, results=[], total=0, limit=limit, offset=offset)

    if len(trimmed) > settings.MAX_SEARCH_QUERY_LENGTH:
        raise ValueError(
            f"Search query must be {settings.MAX_SEARCH_QUERY_LENGTH} characters or fewer."
        )

    limit = max(1, min(limit, settings.MAX_PAGE_SIZE))
    offset = max(0, offset)

    normalized = _normalize(trimmed)
    like_term = f"%{normalized}%"

    def _run() -> tuple[list[PlaceModel], int]:
        alias_subquery = select(PlaceAliasModel.place_id).where(
            func.lower(PlaceAliasModel.alias).like(like_term)
        )
        text_match = or_(
            func.lower(PlaceModel.canonical_name).like(like_term),
            func.lower(PlaceModel.search_text).like(like_term),
            PlaceModel.id.in_(alias_subquery),
        )
        conditions = [text_match]
        if place_type:
            conditions.append(PlaceModel.place_type == place_type)

        total = session.scalar(select(func.count()).select_from(PlaceModel).where(*conditions)) or 0
        statement = (
            select(PlaceModel)
            .where(*conditions)
            # Shortest names first (closest match), then alphabetical for stability.
            .order_by(
                func.length(PlaceModel.canonical_name),
                PlaceModel.canonical_name,
            )
            .limit(limit)
            .offset(offset)
        )
        rows = list(session.scalars(statement))
        return rows, total

    # `cached_response` returns (value, cache_hit); the value is the
    # (rows, total) pair produced by `_run`.
    (rows, total), _cache_hit = cached_response(
        "place_lookup", f"search:{normalized}:{place_type}:{limit}:{offset}", _run
    )

    # The aliases are loaded for the whole page in one query rather than one
    # query per result.
    aliases_by_place = _load_aliases_for(session, [row.id for row in rows])

    results = []
    for row in rows:
        aliases = aliases_by_place.get(row.id, [])
        match_type = "name"
        if normalized not in row.canonical_name.lower() and normalized not in (row.search_text or "").lower():
            if any(normalized in a.lower() for a in aliases):
                match_type = "alias"
        results.append(
            SearchResult(
                place=_to_place(row, aliases),
                score=_score(row, normalized),
                match_type=match_type,
            )
        )
    return SearchResponse(
        query=trimmed,
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )


def _score(place: PlaceModel, normalized: str) -> float:
    """Score a search match. Higher is better."""
    name = place.canonical_name.lower()
    if name == normalized:
        return 1.0
    if name.startswith(normalized):
        return 0.9
    if normalized in name:
        return 0.7
    return 0.5


def get_place(session: Session, place_id: str) -> PlaceModel | None:
    """Fetch a place by id."""
    if len(place_id) > settings.MAX_ID_LENGTH:
        return None
    return session.get(PlaceModel, place_id)


def _to_place(row: PlaceModel, aliases: list[str] | None = None) -> Place:
    """Convert an ORM place row into the API contract."""
    coordinates = None
    if row.latitude is not None and row.longitude is not None:
        coordinates = (row.latitude, row.longitude)
    return Place(
        id=row.id,
        canonical_name=row.canonical_name,
        aliases=aliases or [],
        place_type=row.place_type,
        parent_id=row.parent_id,
        coordinates=coordinates,
        resolution_method=row.resolution_method,
        geometry_available=row.geometry_available,
    )


def load_aliases(session: Session, place_id: str) -> list[str]:
    """Return the alternative names recorded for a place."""
    rows = session.scalars(
        select(PlaceAliasModel.alias)
        .where(PlaceAliasModel.place_id == place_id)
        .order_by(PlaceAliasModel.alias)
    )
    return [alias for alias in rows if alias]


def _load_aliases_for(session: Session, place_ids: list[str]) -> dict[str, list[str]]:
    """Return the aliases of many places in a single query."""
    if not place_ids:
        return {}

    rows = session.execute(
        select(PlaceAliasModel.place_id, PlaceAliasModel.alias)
        .where(PlaceAliasModel.place_id.in_(place_ids))
        .order_by(PlaceAliasModel.place_id, PlaceAliasModel.alias)
    )

    grouped: dict[str, list[str]] = {}
    for place_id, alias in rows:
        if alias:
            grouped.setdefault(place_id, []).append(alias)
    return grouped


def build_hierarchy(session: Session, place: PlaceModel) -> AdminHierarchy:
    """Walk the parent chain to build the administrative hierarchy."""
    hierarchy = AdminHierarchy()
    current = place
    seen: set[str] = set()

    while current is not None and current.id not in seen:
        seen.add(current.id)
        match current.place_type:
            case "state":
                hierarchy.state = current.canonical_name
            case "district":
                hierarchy.district = current.canonical_name
            case "subdistrict":
                hierarchy.subdistrict = current.canonical_name
            case "village":
                hierarchy.village = current.canonical_name
            case _:
                pass
        if current.parent_id is None:
            break
        current = session.get(PlaceModel, current.parent_id)
    return hierarchy


def to_observation(row: ObservationModel) -> Observation:
    """Convert an ORM observation row into the API contract."""
    value: float | str | None = row.value_numeric
    if value is None:
        value = row.value_text
    return Observation(
        field_name=row.field_name,
        value=value,
        unit=row.unit,
        place_id=row.place_id,
        source_id=row.source_id,
        reference_period_start=row.reference_period_start,
        reference_period_end=row.reference_period_end,
        published_at=row.published_at,
        retrieved_at=row.retrieved_at,
        quality_status=row.quality_status,
        licence=row.licence,
        notes=row.notes,
    )


def to_health_observation(row: ObservationModel, now: datetime) -> HealthObservationView:
    """Convert an ORM observation row into the health read model.

    The health read model carries the safety fields (category, issuer,
    validity window, affected level) so a reader can tell an expired alert
    from a live one, and a district-level figure from a village-level one.
    """
    value: float | str | None = row.value_numeric
    if value is None:
        value = row.value_text
    view = HealthObservationView(
        field_name=row.field_name,
        value=value,
        unit=row.unit,
        place_id=row.place_id,
        source_id=row.source_id,
        reference_period_start=row.reference_period_start,
        reference_period_end=row.reference_period_end,
        published_at=row.published_at,
        retrieved_at=row.retrieved_at,
        quality_status=row.quality_status,
        licence=row.licence,
        notes=row.notes,
        health_category=row.health_category or HealthCategory.ROUTINE_SURVEILLANCE,
        issuing_authority=row.issuing_authority,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        affected_geography_level=row.affected_geography_level,
        severity=row.severity,
        disease_code=row.disease_code,
        prevention_link=row.prevention_link,
        prevention_link_date=row.prevention_link_date,
    )
    view.compute_expiry(now)
    return view


def to_source_summary(row: SourceModel, reference_period: str | None = None) -> SourceSummary:
    """Convert an ORM source row into the API contract."""
    return SourceSummary(
        source_id=row.id,
        publisher=row.publisher,
        name=row.name,
        url=row.url,
        licence=row.licence,
        reference_period=reference_period,
        retrieved_at=row.updated_at,
        verification_status=row.verification_status,
    )


def get_profile(session: Session, place_id: str) -> PlaceProfile | None:
    """Assemble the full profile for a place.

    Each domain panel is built independently: a failure in one domain must
    not prevent the others from being served.
    """
    place_row = get_place(session, place_id)
    if place_row is None:
        return None

    place = _to_place(place_row, load_aliases(session, place_row.id))
    hierarchy = build_hierarchy(session, place_row)

    panels: dict[str, PanelResponse] = {}
    for domain in (
        DOMAIN_DEMOGRAPHICS,
        DOMAIN_HEALTH,
        DOMAIN_SERVICES,
        DOMAIN_INFRASTRUCTURE,
        DOMAIN_ENVIRONMENT,
        DOMAIN_RESILIENCE,
        DOMAIN_HISTORY_CULTURE,
        DOMAIN_WEATHER_DISASTERS,
    ):
        panels[domain] = _build_panel(session, place_id, domain)

    return PlaceProfile(place=place, hierarchy=hierarchy, panels=panels)


def _build_panel(session: Session, place_id: str, domain: str) -> PanelResponse:
    """Build a single domain panel, tolerating missing data."""
    rows = list(
        session.scalars(
            select(ObservationModel)
            .where(
                ObservationModel.place_id == place_id,
                ObservationModel.domain == domain,
            )
            .order_by(ObservationModel.field_name)
        )
    )

    if not rows:
        return PanelResponse(
            domain=domain,
            status=DataStatus.UNAVAILABLE,
            observations=[],
            sources=[],
            data_gaps=[f"No {domain} data has been ingested for this area yet."],
        )

    # Health rows need the richer read model: the category, issuer, validity
    # window and expiry are what make a health statement interpretable.
    if domain == DOMAIN_HEALTH:
        now = datetime.now(UTC)
        observations = [to_health_observation(row, now) for row in rows]
    else:
        observations = [to_observation(row) for row in rows]

    source_rows: dict[str, SourceModel] = {}
    for row in rows:
        if row.source_id not in source_rows and row.source is not None:
            source_rows[row.source_id] = row.source

    reference_periods: dict[str, str] = {}
    for row in rows:
        if row.source_id in reference_periods:
            continue
        if row.reference_period_start and row.reference_period_end:
            reference_periods[row.source_id] = (
                f"{row.reference_period_start.isoformat()} to {row.reference_period_end.isoformat()}"
            )
        elif row.reference_period_start:
            reference_periods[row.source_id] = row.reference_period_start.isoformat()

    sources = [
        to_source_summary(source, reference_periods.get(source_id))
        for source_id, source in source_rows.items()
    ]

    # Recompute status per observation so age is judged at read time.
    now = datetime.now(UTC)
    for observation in observations:
        observation.quality_status = determine_status(observation, now)

    summary = summarize_domain(domain, observations, sources, now)

    return PanelResponse(
        domain=domain,
        status=summary.status,
        observations=observations,
        sources=sources,
        last_updated=summary.last_updated,
        coverage_note=_coverage_note(rows),
        data_gaps=[],
    )


def _coverage_note(rows: list[ObservationModel]) -> str | None:
    """Describe the geographic granularity actually present in the data.

    A district-level figure must not be presented as if it were a village-level
    measurement, so the note states the level explicitly.
    """
    if not rows:
        return None
    levels = {row.affected_geography_level for row in rows if row.affected_geography_level}
    if not levels:
        return "Figures are published at the level supplied by the source."
    return f"Figures are published at {'/'.join(sorted(levels))} level."


def place_count(session: Session) -> int:
    """Return the number of places in the database."""
    return session.scalar(select(func.count()).select_from(PlaceModel)) or 0


def observation_count(session: Session) -> int:
    """Return the number of observations in the database."""
    return session.scalar(select(func.count()).select_from(ObservationModel)) or 0


def recent_observations(session: Session, limit: int = 10) -> list[dict[str, Any]]:
    """Return the most recently retrieved observations (admin/health use)."""
    rows = session.scalars(
        select(ObservationModel)
        .order_by(ObservationModel.retrieved_at.desc())
        .limit(max(1, min(limit, settings.MAX_PAGE_SIZE)))
    )
    return [
        {
            "field_name": row.field_name,
            "place_id": row.place_id,
            "domain": row.domain,
            "source_id": row.source_id,
            "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
        }
        for row in rows
    ]

