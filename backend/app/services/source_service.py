"""Source register queries.

The source register is public: every published figure must be traceable to a
registered source. The response therefore includes the publisher, licence and
verification status, but never the credentials used to fetch the data.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.common import AccessMode, VerificationStatus
from app.domain.contracts import Source
from app.models.entities import ObservationModel, SourceModel



def list_sources(
    session: Session,
    limit: int = 50,
    offset: int = 0,
    verification_status: str | None = None,
) -> tuple[list[Source], int]:
    """Return the registered sources, newest first, with a total count."""
    limit = max(1, min(limit, settings.MAX_PAGE_SIZE))
    offset = max(0, offset)

    conditions = []
    if verification_status:
        conditions.append(SourceModel.verification_status == verification_status)

    total = session.scalar(select(func.count()).select_from(SourceModel).where(*conditions)) or 0

    rows = list(
        session.scalars(
            select(SourceModel)
            .where(*conditions)
            .order_by(SourceModel.publisher, SourceModel.name)
            .limit(limit)
            .offset(offset)
        )
    )

    return [_to_source(row) for row in rows], total


def get_source(session: Session, source_id: str) -> Source | None:
    """Return a single registered source."""
    if not source_id or len(source_id) > 128:
        return None
    row = session.get(SourceModel, source_id)
    if row is None:
        return None
    return _to_source(row)


def _to_source(row: SourceModel) -> Source:
    """Convert an ORM source row into the API contract."""
    return Source(
        id=row.id,
        publisher=row.publisher,
        name=row.name,
        url=row.url,
        licence=row.licence,
        access_mode=AccessMode(row.access_mode),
        verification_status=VerificationStatus(row.verification_status),
        last_success=row.last_success,
    )


def get_source_ttl_seconds(source_id: str) -> int:
    """Return the cache TTL in seconds configured for a registered source."""
    ttl_map: dict[str, int] = {
        "src-census-2011": settings.CACHE_TTL_DEMOGRAPHICS_SECONDS,
        "src-mohfw-nhm": settings.CACHE_TTL_FACILITIES_SECONDS,
        "src-idsp-ncdc": settings.CACHE_TTL_HEALTH_OUTBREAK_SECONDS,
        "src-udise-plus": settings.CACHE_TTL_FACILITIES_SECONDS,
        "src-asi": settings.CACHE_TTL_PLACE_LOOKUP_SECONDS,
        "src-imd": 1800,
        "src-isro-bhuvan": 86400,
    }
    if source_id in ttl_map:
        return ttl_map[source_id]
    if "census" in source_id or "pop" in source_id:
        return settings.CACHE_TTL_DEMOGRAPHICS_SECONDS
    if "alert" in source_id or "idsp" in source_id:
        return settings.CACHE_TTL_HEALTH_OUTBREAK_SECONDS
    return settings.CACHE_TTL_FACILITIES_SECONDS


def get_sources_diagnostics(session: Session) -> dict[str, Any]:
    """Compile diagnostic status, observation counts, and TTLs for each registered source."""
    sources = list(session.scalars(select(SourceModel).order_by(SourceModel.publisher, SourceModel.name)))

    # Compute records served and latest retrieved_at per source in a single query
    metrics_query = select(
        ObservationModel.source_id,
        func.count(ObservationModel.id).label("record_count"),
        func.max(ObservationModel.retrieved_at).label("last_retrieved"),
    ).group_by(ObservationModel.source_id)

    metrics_rows = session.execute(metrics_query).all()
    metrics_by_source: dict[str, tuple[int, datetime | None]] = {
        row.source_id: (row.record_count, row.last_retrieved) for row in metrics_rows
    }

    diagnostics = []
    for source in sources:
        record_count, last_retrieved = metrics_by_source.get(source.id, (0, None))
        last_fetch = last_retrieved or source.last_success

        if source.verification_status == "verified":
            health = "healthy"
            error_status = None
        elif source.verification_status == "verified_with_limits":
            health = "degraded"
            error_status = source.notes or "Verified with limitations"
        elif source.verification_status == "unverified":
            health = "unverified"
            error_status = "Source verification pending"
        elif source.verification_status == "deprecated":
            health = "deprecated"
            error_status = "Source has been deprecated"
        else:
            health = "healthy"
            error_status = None

        ttl_sec = get_source_ttl_seconds(source.id)

        diagnostics.append(
            {
                "source_id": source.id,
                "publisher": source.publisher,
                "name": source.name,
                "url": source.url,
                "licence": source.licence,
                "access_mode": source.access_mode,
                "verification_status": source.verification_status,
                "health": health,
                "last_fetch": last_fetch.isoformat() if last_fetch else None,
                "records_served": record_count,
                "error_status": error_status,
                "ttl_seconds": ttl_sec,
            }
        )

    return {
        "total_sources": len(diagnostics),
        "healthy_sources": sum(1 for d in diagnostics if d["health"] == "healthy"),
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": diagnostics,
    }

