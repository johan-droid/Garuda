"""Vercel serverless handler for Garuda FastAPI application.

This file exports a `handler` function that Vercel can use to serve
the FastAPI app as a serverless function. It also exports the app
itself for local development with `vercel dev`.

See: https://github.com/kwfitz/fastapi-vercel
"""

import os
import sys
from typing import Any, Dict

# Ensure the app can be imported from the garuda package
# Vercel adds the function directory to PATH, so we need the right import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))


def _build_app() -> Any:
    """Build and return the FastAPI application instance."""
    # Set required env vars for production if not already set
    if os.getenv("ENVIRONMENT") not in ("production", "staging"):
        os.environ.setdefault("ENVIRONMENT", "development")
    if not os.getenv("SECRET_KEY") or os.getenv("SECRET_KEY") == "unset":
        # Generate a random secret key for development if not set
        import secrets
        os.environ["SECRET_KEY"] = secrets.token_hex(32)

    # Import after path is set
    from app.main import create_app
    app = create_app()
    return app


# Create the app instance at module load time
app = _build_app()


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Vercel serverless function handler.

    Adapts the FastAPI ASGI interface to Vercel's serverless HTTP event format.

    Args:
        event: Vercel serverless function event dict
        context: Vercel context object (optional)

    Returns:
        Vercel serverless function response dict
    """
    import json

    # FastAPI/Starlette receives the ASGI scope, receive, and send
    # We need to parse the Vercel event into ASGI format

    method = event.get("http", {}).get("method", "GET")
    path = event.get("http", {}).get("path", "/")
    headers = event.get("headers", {})
    query_string = event.get("queryString", "") or ""

    # Build ASGI scope
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query_string,
        "headers": [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
        "server": ("localhost", int(os.getenv("PORT", "80"))),
        "client": None,
        "state": type("obj", (object,), {"csrf_token": None})(),
    }

    # Receive function for ASGI
    async def receive():
        return {"type": "http.request", "body": b""}

    # Response collection
    status_code = 200
    headers_list: list = []
    body = b""

    async def send(message):
        nonlocal status_code, headers_list, body
        if message["type"] == "http.response.start":
            status_code = message["status"]
            headers_list = message.get("headers", [])
        elif message["type"] == "http.response.body":
            body = message.get("body", b"")

    # Run the ASGI application
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is already running (e.g., in some Vercel configs),
            # use create_task
            task = loop.create_task(app(scope, receive, send))
            loop.run_until_complete(task)
        else:
            asyncio.get_event_loop().run_until_complete(
                app(scope, receive, send)
            )
    except Exception as e:
        # Fallback error response
        status_code = 500
        headers_list = [("content-type", "application/json")]
        body = json.dumps({"detail": str(e)}).encode("utf-8")

    # Build Vercel response
    # Parse headers from the ASGI response
    vercel_headers: Dict[str, str] = {}
    for name, value in headers_list:
        key = name.decode("latin-1") if isinstance(name, bytes) else str(name)
        val = value.decode("latin-1") if isinstance(value, bytes) else str(value)
        vercel_headers[key] = val

    # Determine content type
    content_type = "application/json"
    for name, value in headers_list:
        key = name.decode("latin-1") if isinstance(name, bytes) else str(name)
        if key.lower() == "content-type":
            content_type = val

    return {
        "statusCode": status_code,
        "headers": vercel_headers,
        "body": body.decode("utf-8") if body else "",
    }