"""Shared domain enums.

These values are part of the public contract. They are mirrored on the
TypeScript side in `apps/web/src/types/contracts.ts`.
"""

from enum import Enum


class DataStatus(str, Enum):
    """Quality/freshness state of a datum or panel.

    `UNAVAILABLE` is distinct from a zero value. The system must never
    represent "we do not know" as `0`.
    """

    CURRENT = "current"
    HISTORICAL = "historical"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"
    APPROXIMATE = "approximate"
    UNVERIFIED = "unverified"


class PlaceType(str, Enum):
    """Administrative or geographic level of a place."""

    STATE = "state"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"  # block / tehsil
    VILLAGE = "village"
    POINT = "point"


class HealthCategory(str, Enum):
    """Strict classification of public-health information.

    These categories must never be mixed: a historical case count can never be
    presented as a current alert, and a model projection can never be presented
    as confirmed cases.
    """

    OFFICIAL_ALERT = "official_alert"
    HISTORICAL_CASES = "historical_cases"
    ROUTINE_SURVEILLANCE = "routine_surveillance"
    FORECAST_MODELLED_RISK = "forecast_modelled_risk"
    GENERAL_PREVENTION = "general_prevention"
    COMMUNITY_REPORT = "community_report"


class VerificationStatus(str, Enum):
    """Verification state of a data source."""

    VERIFIED = "verified"
    VERIFIED_WITH_LIMITS = "verified_with_limits"
    UNVERIFIED = "unverified"
    DEPRECATED = "deprecated"


class AccessMode(str, Enum):
    """How the source data is obtained."""

    API = "api"
    DOWNLOAD = "download"
    BULK = "bulk"
    MANUAL = "manual"


class GeographyLevel(str, Enum):
    """Geographic granularity a data point applies to."""

    STATE = "state"
    DISTRICT = "district"
    SUBDISTRICT = "subdistrict"
    VILLAGE = "village"
    POINT = "point"


# Data domains served as independently-loaded profile panels.
DOMAIN_DEMOGRAPHICS = "demographics"
DOMAIN_HEALTH = "health"
DOMAIN_SERVICES = "services"
DOMAIN_INFRASTRUCTURE = "infrastructure"
DOMAIN_ENVIRONMENT = "environment"
DOMAIN_RESILIENCE = "resilience"
DOMAIN_HISTORY_CULTURE = "history_culture"
DOMAIN_WEATHER_DISASTERS = "weather_disasters"

