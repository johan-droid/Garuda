"""Response helpers shared by the API routes."""

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from app.services.cache import compute_etag


def json_with_etag(request: Request, payload: Any, status_code: int = 200) -> Response:
    """Serialise a payload with an ETag and honour `If-None-Match`.

    The ETag is derived from the payload itself, so a client that revalidates
    receives `304 Not Modified` exactly when the content has not changed.
    """
    etag = compute_etag(payload)
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=0, must-revalidate",
    }
    if request.headers.get("if-none-match", "").strip() == etag:
        return Response(status_code=304, headers=headers)
    return JSONResponse(
        content=jsonable_encoder(payload),
        status_code=status_code,
        headers=headers,
    )
