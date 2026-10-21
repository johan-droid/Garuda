"""The public source register.

Every published figure must be traceable to a registered source, so this
register is public. It deliberately exposes only attribution metadata -
publisher, name, url, licence, verification status - and never the
credentials or transport details used to collect the data.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps.responses import json_with_etag
from app.api.deps.session import get_db
from app.core.config import settings
from app.domain.common import VerificationStatus
from app.services import source_service

router = APIRouter(prefix="/sources", tags=["sources"])

SessionDep = Annotated[Session, Depends(get_db)]
SourceIdPath = Annotated[
    str,
    Path(min_length=1, max_length=128, description="Registered source identifier"),
]


@router.get("", summary="List registered sources")
def list_sources(
    request: Request,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    verification_status: Annotated[str | None, Query(description="Filter by verification status")] = None,
) -> Response:
    """Return the registered sources with their verification status."""
    if verification_status is not None and verification_status not in {
        item.value for item in VerificationStatus
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported verification status filter.",
        )

    sources, total = source_service.list_sources(
        session,
        limit=limit,
        offset=offset,
        verification_status=verification_status,
    )
    payload: dict[str, Any] = {
        "sources": sources,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    return json_with_etag(request, payload)


@router.get("/diagnostics", summary="Registered source health and diagnostics")
def sources_diagnostics(session: SessionDep) -> dict[str, Any]:
    """Return detailed source health, last fetch, records served, error status, and TTLs."""
    return source_service.get_sources_diagnostics(session)


@router.get("/{source_id}", summary="Get one registered source")
def get_source(source_id: SourceIdPath, session: SessionDep) -> Any:
    """Return a single registered source."""
    source = source_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return source
