"""Administrative import endpoints.

These routes are protected by a bearer API key (`app.core.admin_auth`). They
are the only write path into the database, and they exist so that dataset
ingestion is auditable: every import is recorded as a batch with a status, a
row count, and a last-known-good flag.

The import itself is atomic (see `app.services.import_service`): a failure
rolls the whole batch back and the previously imported dataset keeps serving.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps.session import get_db
from app.core.admin_auth import verify_admin_key
from app.core.config import settings
from app.services import import_service
from app.services.import_service import ImportBatch, ImportResult

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)],
)

SessionDep = Annotated[Session, Depends(get_db)]


@router.post("/import", response_model=ImportResult, summary="Import a dataset batch")
def import_dataset(batch: ImportBatch, session: SessionDep) -> ImportResult:
    """Apply an import batch atomically.

    The batch is validated before the transaction opens, so a malformed batch
    is rejected without touching the database. On success the batch becomes
    the last-known-good dataset for its domain; on failure the transaction is
    rolled back and the previous dataset continues to serve.
    """
    try:
        result = import_service.import_batch(session, batch)
    except ValueError as exc:
        # Validation failures carry an operator-written message that names the
        # offending row without exposing internals.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        # The transaction has already been rolled back by the service.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The import failed and was rolled back. The previous dataset is still in service.",
        ) from exc
    return result


@router.get("/imports", summary="List recent import batches")
def list_imports(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = 50,
) -> dict[str, Any]:
    """Return the recent import batches, newest first."""
    return {
        "batches": import_service.list_batches(session, limit=limit),
        "limit": limit,
    }


@router.get("/stats", summary="Administrative counters")
def admin_stats(session: SessionDep) -> dict[str, Any]:
    """Return coarse operational counters for the operator dashboard."""
    from app.services.place_service import observation_count, place_count

    return {
        "places": place_count(session),
        "observations": observation_count(session),
    }
