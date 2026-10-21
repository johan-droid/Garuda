"""Application health endpoints.

These endpoints report the health of the *service*, not the health of a
population. The `note` field is returned on every response so a client that
renders the payload can never mistake it for a public-health alert.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import healthcheck
from app.services.cache import get_cache

router = APIRouter(tags=["health"])

HEALTH_NOTE = "This is application health, not public-health data."


@router.get("/health", summary="Service health snapshot")
def health() -> dict[str, Any]:
    """Return a summary of the service's own state.

    This never reports on population health. It reports whether the API
    process, its database, and its cache are functioning.
    """
    database_ok = healthcheck()
    cache = get_cache().stats()

    return {
        "status": "healthy" if database_ok else "degraded",
        "note": HEALTH_NOTE,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "pilot_region": settings.PILOT_REGION,
        "database": {"ok": database_ok},
        "cache": cache,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/live", summary="Liveness probe")
def liveness() -> dict[str, Any]:
    """Liveness probe: the process is running and can serve requests.

    Deliberately does not touch the database, so a transient database outage
    does not cause the orchestrator to restart a healthy process.
    """
    return {
        "status": "alive",
        "note": HEALTH_NOTE,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/ready", summary="Readiness probe")
def readiness(response: Response) -> dict[str, Any]:
    """Readiness probe: the service can actually serve data.

    Returns 503 when the database is unreachable, so the load balancer stops
    sending traffic to this instance instead of serving errors.
    """
    database_ok = healthcheck()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if database_ok else "not_ready",
        "note": HEALTH_NOTE,
        "database": {"ok": database_ok},
        "timestamp": datetime.now(UTC).isoformat(),
    }
