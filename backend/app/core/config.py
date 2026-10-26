"""
Garuda Indian Area Intelligence System - Core Configuration.
Follows 12-factor principles with secure defaults.

Security notes:
  * No secret has a usable default. SECRET_KEY / ADMIN_API_KEY must be supplied
    explicitly; startup validation fails loudly in staging/production.
  * Secrets are only ever read from the server environment. They are never
    serialised into API responses, logs, or the frontend bundle.
"""

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, List, Optional, Union

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used to detect "not configured". Deliberately not a usable secret.
_UNSET = "unset"

# Default database configuration
# - SQLite: for local development (zero-cost, ephemeral)
# - PostgreSQL: required for production and Vercel serverless deployment
_DEFAULT_SQLITE_PATH = (Path(__file__).resolve().parents[3] / "garuda_local.db").resolve()

# PostgreSQL connection pool settings for serverless
# Vercel serverless functions have short lifetimes, so we use tiny pools
_PG_POOL_SIZE = 2
_PG_MAX_OVERFLOW = 0
_PG_TIMEOUT = 15
_PG_POOL_RECYCLE = 300  # 30 minutes - shorter than SQLite default
# (garuda/backend/app/core/config.py -> parents[3] == garuda/)
_DEFAULT_SQLITE_PATH = (Path(__file__).resolve().parents[3] / "garuda_local.db").resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_DEFAULT_SQLITE_PATH.parent / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application Info
    APP_NAME: str = "Garuda Area Intelligence"
    APP_VERSION: str = "1.0.0"
    PILOT_REGION: str = Field(
        default="IN-OD",
        validation_alias=AliasChoices("PILOT_REGION", "GARUDA_PILOT_REGION"),
        description="Default pilot region code",
    )
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "GARUDA_ENV"),
        description="development, staging, production, or testing",
    )
    DEBUG: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG", "GARUDA_DEBUG"),
        description="Debug mode must remain False in production",
    )

    # API Configuration
    API_V1_STR: str = "/api/v1"

    # Secrets. No defaults on purpose.
    SECRET_KEY: str = Field(
        default=_UNSET,
        validation_alias=AliasChoices("SECRET_KEY", "GARUDA_SECRET_KEY"),
        description="Signing/session secret. Required outside development.",
    )
    ADMIN_API_KEY: str = Field(
        default=_UNSET,
        validation_alias=AliasChoices("ADMIN_API_KEY", "GARUDA_ADMIN_API_KEY"),
        description="Key for privileged administrative operations.",
    )

    # Database
    DATABASE_URL: str = Field(
        default=f"sqlite:///{_DEFAULT_SQLITE_PATH}",
        validation_alias=AliasChoices("DATABASE_URL", "GARUDA_DATABASE_URL"),
        description=(
            "Database connection URL. "
            "SQLite for zero-cost dev/testing (ephemeral - not for production). "
            "PostgreSQL (e.g. postgresql://user:pass@host:port/db) for production/serverless."
        ),
    )
    DB_POOL_SIZE: int = Field(default=5, description="Connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=10, description="Max overflow connections")
    DB_TIMEOUT: int = Field(default=30, description="Database query/connect timeout in seconds")
    DB_POOL_RECYCLE_SECONDS: int = Field(default=1800, description="Recycle pooled connections to avoid stale handles")
    DB_ENABLE_SQLITE_FK: bool = Field(default=True, description="Enable foreign key enforcement on SQLite")

    # CORS & Security
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        validation_alias=AliasChoices("ALLOWED_ORIGINS", "CORS_ORIGINS", "GARUDA_ALLOWED_ORIGINS"),
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins. Set explicitly in production.",
    )
    ALLOWED_ORIGINS_REGEX: Optional[str] = Field(
        default=None, description="Optional regex for allowed origins. Unset by default; do not use with credentials."
    )
    ENABLE_HSTS: bool = Field(default=False, description="Set True behind HTTPS in production")
    TRUSTED_PROXY_HOPS: int = Field(default=0, description="Number of trusted proxy hops for client IP resolution")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=False, description="Allow cookies/credentials cross-origin")

    # Security headers
    CSP_DIRECTIVES: Optional[str] = Field(
        default=None,
        description="Optional CSP override as a semicolon-separated directive string.",
    )
    SECURITY_HEADERS_MAX_AGE: int = Field(default=31536000, description="max-age for HSTS when enabled")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable request rate limiting")
    RATE_LIMIT_PUBLIC_PER_MINUTE: int = Field(
        validation_alias=AliasChoices("RATE_LIMIT_PUBLIC_PER_MINUTE", "RATE_LIMIT_PER_MINUTE", "GARUDA_RATE_LIMIT_PER_MINUTE"),
        default=60,
        description="Max public requests per minute per IP",
    )
    RATE_LIMIT_SEARCH_PER_MINUTE: int = Field(default=30, description="Max search requests per minute per IP")
    RATE_LIMIT_ADMIN_PER_MINUTE: int = Field(default=10, description="Max admin requests per minute per IP")

    # Body / request size limits
    MAX_REQUEST_BODY_BYTES: int = Field(default=1_000_000, description="Max accepted request body size (1MB)")
    MAX_IMPORT_PAYLOAD_BYTES: int = Field(default=5_000_000, description="Max import payload size (5MB)")
    MAX_PAGE_SIZE: int = Field(default=50, description="Hard cap on page size for list endpoints")
    MAX_SEARCH_QUERY_LENGTH: int = Field(default=200, description="Max length of a search query string")
    MAX_ID_LENGTH: int = Field(default=64, description="Max length of a geographic identifier")

    # Data Freshness Windows (in days)
    HEALTH_DATA_MAX_AGE_DAYS: int = Field(default=7, description="Threshold after which health data is marked STALE")
    FACILITIES_MAX_AGE_DAYS: int = Field(default=90, description="Threshold after which facility data is marked STALE")
    DEMOGRAPHICS_MAX_AGE_DAYS: int = Field(default=3650, description="Census data freshness window")

    # Cache TTLs per data category (seconds). Deliberately NOT one global TTL.
    CACHE_TTL_DEMOGRAPHICS_SECONDS: int = Field(default=86_400, description="Population/census TTL (1 day)")
    CACHE_TTL_FACILITIES_SECONDS: int = Field(default=21_600, description="Facilities/education TTL (6 hours)")
    CACHE_TTL_HEALTH_ADVISORY_SECONDS: int = Field(default=900, description="Health advisory TTL (15 minutes)")
    CACHE_TTL_HEALTH_OUTBREAK_SECONDS: int = Field(default=300, description="Health outbreak TTL (5 minutes)")
    CACHE_TTL_PLACE_LOOKUP_SECONDS: int = Field(default=604_800, description="Place/geography lookup TTL (7 days)")
    CACHE_TTL_ENVIRONMENT_SECONDS: int = Field(default=900, description="Environment imagery metadata TTL (15 minutes)")
    CACHE_MAX_ENTRIES: int = Field(default=2048, description="Max in-memory cache entries before eviction")

    # Upstream & Ingestion Safety
    UPSTREAM_TIMEOUT_SECONDS: int = Field(default=15, description="Timeout for external API calls")
    EARTH_SEARCH_STAC_ENDPOINT: str = Field(
        default="https://earth-search.aws.element84.com/v1",
        validation_alias=AliasChoices("EARTH_SEARCH_STAC_ENDPOINT", "GARUDA_EARTH_SEARCH_STAC_ENDPOINT"),
        description="Earth Search STAC public endpoint for Sentinel-2 L2A scene metadata.",
    )
    UPSTREAM_MAX_RETRIES: int = Field(default=3, description="Max retries for transient upstream failures")
    UPSTREAM_BACKOFF_BASE_SECONDS: float = Field(default=0.5, description="Base for exponential backoff")
    UPSTREAM_BACKOFF_MAX_SECONDS: float = Field(default=8.0, description="Max backoff delay")
    UPSTREAM_MAX_CONCURRENT: int = Field(default=8, description="Max concurrent outbound upstream requests")
    UPSTREAM_USER_AGENT: str = Field(
        default="Garuda-Area-Intelligence/1.0 (public information service)",
        description="User-Agent sent to upstream APIs. Must identify the service per provider policy.",
    )
    ALLOW_PRIVATE_UPSTREAM: bool = Field(
        default=False,
        description="Allow outbound requests to private/loopback IPs. Development only.",
    )
    INGEST_MAX_ROWS: int = Field(default=50_000, description="Max rows accepted in a single import batch")
    IMD_API_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("IMD_API_BASE_URL", "GARUDA_IMD_API_BASE_URL"),
        description="Base URL for IMD weather upstream API. Live calls disabled when unset.",
    )
    NHM_API_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("NHM_API_BASE_URL", "GARUDA_NHM_API_BASE_URL"),
        description="Base URL for NHM health upstream API. Live calls disabled when unset.",
    )
    NDMA_API_BASE_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("NDMA_API_BASE_URL", "GARUDA_NDMA_API_BASE_URL"),
        description="Base URL for NDMA disaster bulletin upstream API. Live calls disabled when unset.",
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Minimum log level")
    LOG_JSON: bool = Field(default=False, description="Emit JSON structured logs")

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = {"development", "staging", "production", "testing"}
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v.lower()

    @field_validator("DEBUG")
    @classmethod
    def validate_debug(cls, v: bool, info) -> bool:
        # Prevent debug mode in production
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production" and v is True:
            raise ValueError("DEBUG mode cannot be enabled in production environment!")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        level = v.upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be a standard level name")
        return level

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        """Accept JSON array string, comma-separated string, or list for CORS origins."""
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
                try:
                    parsed = json.loads(s.replace("'", '"'))
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in s.split(",") if item.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Anchor relative default SQLite URL to project root database."""
        if v in ("sqlite:///./garuda_local.db", "sqlite:///garuda_local.db"):
            return f"sqlite:///{_DEFAULT_SQLITE_PATH}"
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Fail fast when production-critical configuration is missing or insecure."""
        if self.ENVIRONMENT in {"production", "staging"}:
            if self.SECRET_KEY == _UNSET or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a random value of at least 32 characters "
                    f"in {self.ENVIRONMENT}."
                )
            if self.ADMIN_API_KEY == _UNSET or len(self.ADMIN_API_KEY) < 16:
                raise ValueError(
                    "ADMIN_API_KEY must be set to a random value of at least 16 characters "
                    f"in {self.ENVIRONMENT}."
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production/staging.")
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Wildcard CORS origin is not permitted.")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def secret_key_configured(self) -> bool:
        return self.SECRET_KEY != _UNSET and len(self.SECRET_KEY) >= 32

    @property
    def admin_key_configured(self) -> bool:
        return self.ADMIN_API_KEY != _UNSET and len(self.ADMIN_API_KEY) >= 16

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgresql(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def is_serverless_suitable(self) -> bool:
        """Check if the current config is suitable for serverless deployment."""
        return self.is_postgresql and not self.is_sqlite


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor.

    Raises on invalid configuration so the process fails at startup rather than
    serving requests with insecure defaults.
    """
    return Settings()


settings = get_settings()

