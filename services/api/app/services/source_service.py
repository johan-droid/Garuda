"""Source register queries.

The source register is public: every published figure must be traceable to a
registered source. The response therefore includes the publisher, licence and
verification status, but never the credentials used to fetch the data.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.contracts import Source
from app.models.entities import SourceModel


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
        access_mode=row.access_mode,
        verification_status=row.verification_status,
        last_success=row.last_success,
    )
