# Route module re-exports for the API

from app.api.routes.admin import router as admin_router
from app.api.routes.environment_scenes import router as environment_scenes_router
from app.api.routes.health import router as health_router
from app.api.routes.observations import router as observations_router
from app.api.routes.places import router as places_router
from app.api.routes.sources import router as sources_router

__all__ = [
    "admin_router",
    "environment_scenes_router",
    "health_router",
    "observations_router",
    "places_router",
    "sources_router",
]