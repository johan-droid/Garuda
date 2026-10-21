"""Freshness and provenance computation.

Central rule of the system: a value is never presented as "current" unless
the underlying source says it is. Freshness is derived from the *reference
period* of the data (when it describes a period) or its publication/retrieval
time, and never from the ingestion time alone.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.domain.common import DataStatus
from app.domain.contracts import DataStatusSummary, Observation, SourceSummary

# Maximum age (days) applied to each domain.
DOMAIN_MAX_AGE_DAYS: dict[str, int] = {
    "demographics": settings.DEMOGRAPHICS_MAX_AGE_DAYS,
    "health": settings.HEALTH_DATA_MAX_AGE_DAYS,
    "services": settings.FACILITIES_MAX_AGE_DAYS,
    "infrastructure": settings.FACILITIES_MAX_AGE_DAYS,
    "environment": settings.FACILITIES_MAX_AGE_DAYS,
    "resilience": settings.FACILITIES_MAX_AGE_DAYS,
    "history_culture": settings.DEMOGRAPHICS_MAX_AGE_DAYS,
    "weather_disasters": settings.HEALTH_DATA_MAX_AGE_DAYS,
}

# Statuses that mean "this datum is not usable as a current fact".
_NON_CURRENT = {
    DataStatus.UNAVAILABLE,
    DataStatus.CONFLICTING,
    DataStatus.UNVERIFIED,
    DataStatus.HISTORICAL,
}


def max_age_days_for(domain: str) -> int:
    """Return the freshness threshold for a domain."""
    return DOMAIN_MAX_AGE_DAYS.get(domain, settings.FACILITIES_MAX_AGE_DAYS)


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a datetime to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def effective_data_time(observation: Observation) -> datetime:
    """Return the moment that best describes how current the observation is.

    Preference order:
      1. `reference_period_end` - the end of the period the fact describes.
      2. `published_at`          - when the source published it.
      3. `retrieved_at`          - when we fetched it (last resort).
    """
    if observation.reference_period_end is not None:
        end = _as_utc(datetime.combine(observation.reference_period_end, datetime.min.time()))
        if end is not None:
            return end
    published = _as_utc(observation.published_at)
    if published is not None:
        return published
    return _as_utc(observation.retrieved_at) or datetime.now(UTC)


def age_days(observation: Observation, now: datetime | None = None) -> int:
    """Age of an observation in whole days."""
    reference = now or datetime.now(UTC)
    delta = reference - effective_data_time(observation)
    return max(0, int(delta.total_seconds() // 86400))


def determine_status(observation: Observation, now: datetime | None = None) -> DataStatus:
    """Compute the effective status of a single observation.

    A stored status is authoritative when it marks the datum as unusable
    (`unavailable`, `conflicting`, `unverified`). Otherwise the status is
    derived from the age of the data relative to the domain threshold.
    """
    stored = observation.quality_status
    if stored in _NON_CURRENT:
        return stored

    domain = _domain_for_observation(observation)
    threshold = max_age_days_for(domain)
    age = age_days(observation, now)

    if age > threshold:
        return DataStatus.STALE
    if stored == DataStatus.APPROXIMATE:
        return DataStatus.APPROXIMATE
    return DataStatus.CURRENT


def _domain_for_observation(observation: Observation) -> str:
    """Infer the domain of an observation from its field name.

    Health observations are identifiable by their health category; other
    domains are inferred from the field name prefix.
    """
    from app.domain.contracts import HealthObservation

    if isinstance(observation, HealthObservation):
        return "health"
    field = observation.field_name.lower()
    if field.startswith(("population_", "demographic_", "literacy_")):
        return "demographics"
    if field.startswith(("health_", "case_", "disease_")):
        return "health"
    if field.startswith(("facility_", "school_", "hospital_", "clinic_")):
        return "services"
    if field.startswith(("road_", "connectivity_", "network_")):
        return "infrastructure"
    if field.startswith(("air_", "water_", "soil_", "noise_")):
        return "environment"
    if field.startswith(("disaster_", "flood_", "cyclone_", "seismic_")):
        return "resilience"
    return "demographics"


def summarize_domain(
    domain: str,
    observations: Sequence[Observation],
    sources: Sequence[SourceSummary],
    now: datetime | None = None,
) -> DataStatusSummary:
    """Build the freshness/provenance summary for a single domain panel."""
    reference = now or datetime.now(UTC)
    threshold = max_age_days_for(domain)

    if not observations:
        return DataStatusSummary(
            domain=domain,
            status=DataStatus.UNAVAILABLE,
            last_updated=None,
            observation_count=0,
            source_count=len(sources),
            max_age_days=threshold,
            age_days=None,
            message="No data is available for this area yet.",
        )

    statuses = [determine_status(obs, reference) for obs in observations]
    ages = [age_days(obs, reference) for obs in observations]
    oldest_age = max(ages)
    last_updated = max(effective_data_time(obs) for obs in observations)

    if DataStatus.CONFLICTING in statuses:
        status = DataStatus.CONFLICTING
        message = "Sources disagree for this area; figures are shown with their source."
    elif DataStatus.UNAVAILABLE in statuses:
        status = DataStatus.UNAVAILABLE
        message = "Some fields are unavailable for this area."
    elif DataStatus.UNVERIFIED in statuses:
        status = DataStatus.UNVERIFIED
        message = "This information has not been verified against a source."
    elif DataStatus.STALE in statuses:
        status = DataStatus.STALE
        message = f"The newest figure for this area is {oldest_age} days old."
    elif DataStatus.HISTORICAL in statuses:
        status = DataStatus.HISTORICAL
        message = "These figures describe a past period, not the present."
    elif DataStatus.APPROXIMATE in statuses:
        status = DataStatus.APPROXIMATE
        message = "These figures are approximate."
    else:
        status = DataStatus.CURRENT
        message = None

    return DataStatusSummary(
        domain=domain,
        status=status,
        last_updated=last_updated,
        observation_count=len(observations),
        source_count=len(sources),
        max_age_days=threshold,
        age_days=oldest_age,
        message=message,
    )


def freshness_window(domain: str) -> timedelta:
    """Return the freshness window for a domain as a timedelta."""
    return timedelta(days=max_age_days_for(domain))

    return "demographics"
