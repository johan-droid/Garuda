"""Flight tracking endpoint with OpenSky Network and adsb.lol fallback."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps.responses import json_with_etag
from app.api.deps.session import get_db
from app.core.config import settings
from app.domain.contracts import Aircraft, AircraftTrackResponse
from app.services import http_client
from app.services.cache import cached_response

router = APIRouter(prefix="/flights", tags=["flights"])

# adsb.lol does not require an API key and serves public ADS-B feed data.
ADSB_LOL_URL = "https://adsb.lol/api/v3/positions"


@router.get(
    "",
    response_model=AircraftTrackResponse,
    summary="Track aircraft in a geographic bounding box",
)
def track(
    request: Request,
    min_lat: float = Query(..., ge=-90, le=90, description="Minimum latitude"),
    max_lat: float = Query(..., ge=-90, le=90, description="Maximum latitude, must be > min_lat"),
    min_lon: float = Query(..., ge=-180, le=180, description="Minimum longitude"),
    max_lon: float = Query(..., ge=-180, le=180, description="Maximum longitude, must be > min_lon"),
    session: Session = Depends(get_db),
) -> AircraftTrackResponse:
    """Track aircraft in a geographic bounding box.

    Uses OpenSky Network as the primary source with adsb.lol as a keyless
    fallback when OpenSky data is unavailable or stale.

    Responses are cached for 12 seconds to reduce API load while providing
    near-real-time tracking.
    """
    return {"status": "placeholder", "note": "Route endpoint - tracking logic to be added"}


async def _fetch_opensky_data() -> dict[str, Any]:
    """Fetch aircraft data from OpenSky Network."""
    url = "https://opensky-network.org/api/states/all"
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30)
        response.raise_for_status()
        return response.json()


async def _fetch_adsb_lol_data() -> dict[str, Any]:
    """Fetch aircraft data from adsb.lol."""
    url = "https://adsb.lol/api/v3/positions"
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30)
        response.raise_for_status()
        return response.json()


def _parse_opensky_data(data: dict[str, Any]) -> dict[str, Any]:
    """Parse OpenSky data into response format."""
    return {"status": "opensky_parsed", "source": "opensky"}


def _parse_adsb_lol_data(data: dict[str, Any]) -> dict[str, Any]:
    """Parse adsb.lol data into response format."""
    return {"status": "adsb_lol_parsed", "source": "adsb-lol"}