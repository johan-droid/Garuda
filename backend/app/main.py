"""FastAPI application factory and entrypoint.

Run locally with:

    uvicorn app.main:app --reload

The application is deliberately small and explicit:

  * Versioned routes live under `/api/v1` (`settings.API_V1_STR`).
  * The health probes live at the root (`/health`, `/health/live`,
    `/health/ready`) so an orchestrator does not have to know the API
    version, and they are exempt from rate limiting.
  * Errors are converted into a uniform, safe envelope by
    `app.core.errors`.
  * Security headers, CORS, request IDs, and rate limiting are applied as
    middleware.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    disasters,
    environment_indicators,
    environment_scenes,
    observations,
    places,
    saved_places,
    sources,
    weather,
)
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from app.core.security import SecurityHeadersMiddleware

logger = get_logger("garuda.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepare and tear down application resources."""
    configure_logging()
    logger.info(
        "startup",
        extra={
            "extra_fields": {
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "api_prefix": settings.API_V1_STR,
            }
        },
    )
    yield
    logger.info("shutdown", extra={"extra_fields": {"version": settings.APP_VERSION}})


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Public area intelligence for India. Every published figure carries "
            "its source, reference period, and freshness status."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware is applied bottom-up, so the order here is the reverse of
    # the order in which the requests traverse the stack.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=settings.ALLOWED_ORIGINS_REGEX,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        # DELETE is here because removing a saved place is a real request;
        # without it a cross-origin client would be refused at preflight.
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "ETag",
            "X-Request-ID",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
            "Retry-After",
        ],
    )
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    # Health probes sit at the root so the orchestrator does not have to
    # track the API version.
    app.include_router(health_router)

    # Versioned API.
    app.include_router(places.router, prefix=settings.API_V1_STR)
    app.include_router(sources.router, prefix=settings.API_V1_STR)
    app.include_router(environment_scenes.router, prefix=settings.API_V1_STR)
    app.include_router(observations.router, prefix=settings.API_V1_STR)
    app.include_router(weather.router, prefix=settings.API_V1_STR)
    app.include_router(disasters.router, prefix=settings.API_V1_STR)
    app.include_router(environment_indicators.router, prefix=settings.API_V1_STR)
    app.include_router(saved_places.router, prefix=settings.API_V1_STR)
    app.include_router(admin.router, prefix=settings.API_V1_STR)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, object]:
        """Return a short pointer to the API surface."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "api": settings.API_V1_STR,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
