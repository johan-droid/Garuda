"""Typed upstream provider adapter layer for external data sources.

Connects the SSRF-safe outbound HTTP client (`app.services.http_client`) to
strongly-typed domain models (`Observation`, `HealthObservation`, `SourceSummary`).

Guarantees:
  * Strict SSRF safety: private and loopback destinations are rejected.
  * Dependency injection: base URLs and HTTP clients are injectable; live
    network calls are disabled unless explicitly configured.
  * Provenance and attribution: every ingested observation is mapped to a
    registered source ID, citable license, and domain.
  * Graceful degradation: transport failures can either return canonical
    unavailable observations or raise typed provider exceptions.
"""

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.common import (
    DOMAIN_HEALTH,
    DOMAIN_WEATHER_DISASTERS,
    DataStatus,
    GeographyLevel,
    HealthCategory,
    VerificationStatus,
)
from app.domain.contracts import (
    HealthObservation,
    Observation,
    SourceSummary,
)
from app.services.http_client import UnsafeURLError, fetch_json, validate_url

logger = get_logger("garuda.providers")


class ProviderError(Exception):
    """Base exception for provider adapter errors."""


class ProviderUnavailableError(ProviderError):
    """Raised when an upstream provider fails, times out, or returns errors."""


class ProviderConfigurationError(ProviderError):
    """Raised when an adapter is not configured (e.g. missing base URL)."""


def _parse_date(value: Any) -> date | None:
    """Safely parse a date value from various formats."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    """Safely parse an ISO datetime string into UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


class BaseProviderAdapter(ABC):
    """Abstract base class for upstream data provider adapters."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        raise_on_error: bool = False,
    ) -> None:
        self.base_url = base_url
        self.client = client
        self.timeout = timeout if timeout is not None else float(settings.UPSTREAM_TIMEOUT_SECONDS)
        self.user_agent = user_agent or settings.UPSTREAM_USER_AGENT
        self.max_retries = max_retries if max_retries is not None else settings.UPSTREAM_MAX_RETRIES
        self.backoff_base = backoff_base if backoff_base is not None else settings.UPSTREAM_BACKOFF_BASE_SECONDS
        self.raise_on_error = raise_on_error

    @abstractmethod
    def fetch_observations(self, place_id: str, *, raise_on_error: bool | None = None) -> list[Observation]:
        """Fetch and return parsed observations for a given place ID."""
        ...

    @abstractmethod
    def fetch_sources(self) -> list[SourceSummary]:
        """Return registered source attribution summary for this provider."""
        ...

    def _build_url(self, place_id: str) -> str:
        """Construct the upstream endpoint URL for a place."""
        if not self.base_url:
            raise ProviderConfigurationError(
                f"Upstream base URL is not configured for {self.__class__.__name__}."
            )
        base = self.base_url.strip()
        if "{place_id}" in base:
            return base.format(place_id=place_id)
        if base.endswith(f"/{place_id}"):
            return base
        if base.endswith(".json") or "?" in base:
            return base
        return f"{base.rstrip('/')}/observations/{place_id}"

    def _fetch_json(self, url: str) -> Any:
        """Fetch and parse upstream JSON document with retries and SSRF checks.

        SSRF protection: UnsafeURLError is NEVER swallowed and will be raised immediately.
        HTTP errors and timeouts are retried up to max_retries.
        """
        validate_url(url)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        attempts = 1 + max(0, self.max_retries)
        backoff = self.backoff_base
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                return fetch_json(url, client=self.client, headers=headers)
            except UnsafeURLError:
                # SSRF violation must fail immediately without retrying or masking
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < attempts - 1 and self.backoff_base > 0:
                    time.sleep(min(backoff, settings.UPSTREAM_BACKOFF_MAX_SECONDS))
                    backoff *= 2
            except httpx.HTTPError as exc:
                last_error = exc
                break
            except Exception as exc:
                last_error = exc
                break

        raise ProviderUnavailableError(f"Failed to fetch data from '{url}': {last_error}") from last_error


class IMDWeatherAdapter(BaseProviderAdapter):
    """Adapter for India Meteorological Department (IMD) weather observations.

    Fetches structured station readings and advisories, mapping them to canonical
    `Observation` objects:
      * `surface_temperature_celsius` (°C)
      * `rainfall_daily_mm` (mm)
      * `cyclone_preparedness_advisory`
    """

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        raise_on_error: bool = False,
        source_id: str = "src-imd",
        licence: str = "GODL-India",
        publisher: str = "India Meteorological Department (IMD), Ministry of Earth Sciences",
        source_name: str = "National Weather Forecasting Centre & Regional Meteorological Centre Bhubaneswar",
    ) -> None:
        resolved_base_url = base_url or settings.IMD_API_BASE_URL
        super().__init__(
            base_url=resolved_base_url,
            client=client,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            backoff_base=backoff_base,
            raise_on_error=raise_on_error,
        )
        self.source_id = source_id
        self.licence = licence
        self.publisher = publisher
        self.source_name = source_name

    def fetch_sources(self) -> list[SourceSummary]:
        """Return SourceSummary attribution for IMD."""
        return [
            SourceSummary(
                source_id=self.source_id,
                publisher=self.publisher,
                name=self.source_name,
                url=self.base_url or "https://mausam.imd.gov.in",
                licence=self.licence,
                reference_period=None,
                retrieved_at=datetime.now(UTC),
                verification_status=VerificationStatus.VERIFIED,
            )
        ]

    def fetch_observations(self, place_id: str, *, raise_on_error: bool | None = None) -> list[Observation]:
        """Fetch weather observations for place_id and parse into canonical records."""
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        try:
            if not self.base_url:
                raise ProviderConfigurationError("IMD API base URL is not configured.")
            url = self._build_url(place_id)
            payload = self._fetch_json(url)
            return self._parse_payload(payload, place_id)
        except UnsafeURLError:
            raise
        except Exception as exc:
            logger.warning(
                "IMD upstream fetch failed",
                extra={
                    "extra_fields": {
                        "provider": "IMDWeatherAdapter",
                        "place_id": place_id,
                        "error": str(exc),
                    }
                },
            )
            if should_raise:
                if isinstance(exc, ProviderError):
                    raise
                raise ProviderUnavailableError(f"IMD weather fetch failed for {place_id}: {exc}") from exc
            return self._unavailable_observations(place_id, error_reason=str(exc))

    def _unavailable_observations(self, place_id: str, error_reason: str = "") -> list[Observation]:
        """Return canonical observations marked as UNAVAILABLE."""
        now = datetime.now(UTC)
        note = f"Upstream unavailable: {error_reason}" if error_reason else "Data unavailable from upstream"
        return [
            Observation(
                field_name="surface_temperature_celsius",
                value=None,
                unit="°C",
                place_id=place_id,
                source_id=self.source_id,
                quality_status=DataStatus.UNAVAILABLE,
                licence=self.licence,
                domain=DOMAIN_WEATHER_DISASTERS,
                retrieved_at=now,
                notes=note,
            ),
            Observation(
                field_name="rainfall_daily_mm",
                value=None,
                unit="mm",
                place_id=place_id,
                source_id=self.source_id,
                quality_status=DataStatus.UNAVAILABLE,
                licence=self.licence,
                domain=DOMAIN_WEATHER_DISASTERS,
                retrieved_at=now,
                notes=note,
            ),
            Observation(
                field_name="cyclone_preparedness_advisory",
                value=None,
                unit=None,
                place_id=place_id,
                source_id=self.source_id,
                quality_status=DataStatus.UNAVAILABLE,
                licence=self.licence,
                domain=DOMAIN_WEATHER_DISASTERS,
                retrieved_at=now,
                notes=note,
            ),
        ]

    def _parse_payload(self, payload: Any, place_id: str) -> list[Observation]:
        """Parse raw upstream payload into canonical IMD weather observations."""
        now = datetime.now(UTC)
        results: list[Observation] = []

        if isinstance(payload, dict) and "records" in payload and isinstance(payload["records"], list):
            records = payload["records"]
        elif isinstance(payload, list):
            records = payload
        else:
            records = None

        if records is not None:
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                raw_name = str(rec.get("field_name", "")).strip().lower()
                val = rec.get("value")
                unit = rec.get("unit")
                notes = rec.get("notes")
                published_at = _parse_datetime(rec.get("published_at"))
                ref_start = _parse_date(rec.get("reference_period_start"))
                ref_end = _parse_date(rec.get("reference_period_end"))

                # Canonical mapping
                if raw_name in {"surface_temperature_celsius", "temperature", "temp_c", "temperature_celsius"}:
                    results.append(
                        Observation(
                            field_name="surface_temperature_celsius",
                            value=float(val) if val is not None else None,
                            unit=unit or "°C",
                            place_id=place_id,
                            source_id=self.source_id,
                            domain=DOMAIN_WEATHER_DISASTERS,
                            licence=self.licence,
                            quality_status=DataStatus.CURRENT if val is not None else DataStatus.UNAVAILABLE,
                            retrieved_at=now,
                            published_at=published_at,
                            reference_period_start=ref_start,
                            reference_period_end=ref_end,
                            notes=notes or "IMD observed surface temperature reading.",
                        )
                    )
                elif raw_name in {"rainfall_daily_mm", "rainfall", "rain_mm", "rainfall_mm", "daily_rainfall_mm"}:
                    results.append(
                        Observation(
                            field_name="rainfall_daily_mm",
                            value=float(val) if val is not None else None,
                            unit=unit or "mm",
                            place_id=place_id,
                            source_id=self.source_id,
                            domain=DOMAIN_WEATHER_DISASTERS,
                            licence=self.licence,
                            quality_status=DataStatus.CURRENT if val is not None else DataStatus.UNAVAILABLE,
                            retrieved_at=now,
                            published_at=published_at,
                            reference_period_start=ref_start,
                            reference_period_end=ref_end,
                            notes=notes or "IMD 24-hour recorded precipitation.",
                        )
                    )
                elif raw_name in {"cyclone_preparedness_advisory", "cyclone_advisory", "advisory", "storm_advisory"}:
                    results.append(
                        Observation(
                            field_name="cyclone_preparedness_advisory",
                            value=str(val) if val is not None else None,
                            unit=None,
                            place_id=place_id,
                            source_id=self.source_id,
                            domain=DOMAIN_WEATHER_DISASTERS,
                            licence=self.licence,
                            quality_status=DataStatus.CURRENT if val is not None else DataStatus.UNAVAILABLE,
                            retrieved_at=now,
                            published_at=published_at,
                            reference_period_start=ref_start,
                            reference_period_end=ref_end,
                            notes=notes or "IMD / NDMA severe weather coastal directive.",
                        )
                    )
            return results

        # Fallback: Dictionary containing flat key-value pairs or nested objects
        data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            return self._unavailable_observations(place_id, error_reason="Unrecognized payload structure")

        # Temperature
        temp_val = (
            data.get("surface_temperature_celsius")
            if data.get("surface_temperature_celsius") is not None
            else data.get("temperature")
            if data.get("temperature") is not None
            else data.get("temperature_celsius")
            if data.get("temperature_celsius") is not None
            else data.get("temp_c")
        )
        if temp_val is not None:
            results.append(
                Observation(
                    field_name="surface_temperature_celsius",
                    value=float(temp_val),
                    unit="°C",
                    place_id=place_id,
                    source_id=self.source_id,
                    domain=DOMAIN_WEATHER_DISASTERS,
                    licence=self.licence,
                    quality_status=DataStatus.CURRENT,
                    retrieved_at=now,
                    notes="IMD observed surface temperature reading.",
                )
            )

        # Rainfall
        rain_val = (
            data.get("rainfall_daily_mm")
            if data.get("rainfall_daily_mm") is not None
            else data.get("rainfall")
            if data.get("rainfall") is not None
            else data.get("rainfall_mm")
            if data.get("rainfall_mm") is not None
            else data.get("rain_mm")
        )
        if rain_val is not None:
            results.append(
                Observation(
                    field_name="rainfall_daily_mm",
                    value=float(rain_val),
                    unit="mm",
                    place_id=place_id,
                    source_id=self.source_id,
                    domain=DOMAIN_WEATHER_DISASTERS,
                    licence=self.licence,
                    quality_status=DataStatus.CURRENT,
                    retrieved_at=now,
                    notes="IMD 24-hour recorded precipitation.",
                )
            )

        # Cyclone preparedness advisory
        adv_val = (
            data.get("cyclone_preparedness_advisory")
            if data.get("cyclone_preparedness_advisory") is not None
            else data.get("cyclone_advisory")
            if data.get("cyclone_advisory") is not None
            else data.get("advisory")
        )
        if adv_val is not None:
            results.append(
                Observation(
                    field_name="cyclone_preparedness_advisory",
                    value=str(adv_val),
                    unit=None,
                    place_id=place_id,
                    source_id=self.source_id,
                    domain=DOMAIN_WEATHER_DISASTERS,
                    licence=self.licence,
                    quality_status=DataStatus.CURRENT,
                    retrieved_at=now,
                    notes="IMD / NDMA severe weather coastal directive.",
                )
            )

        if not results:
            return self._unavailable_observations(place_id, error_reason="No matching weather fields found")

        return results


class NHMHealthAdapter(BaseProviderAdapter):
    """Adapter for National Health Mission (NHM) / MoHFW health observations.

    Fetches health surveillance (e.g. `dengue_cases`, `cholera_cases`) or public
    facility counts (e.g. `primary_health_centres`, `community_health_centres`),
    mapping them into strongly-typed `HealthObservation` objects.
    """

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        raise_on_error: bool = False,
        source_id: str = "src-mohfw-nhm",
        licence: str = "GODL-India",
        publisher: str = "Ministry of Health & Family Welfare / National Health Mission Odisha",
        source_name: str = "Health Management Information System & Public Health Facility Directory",
    ) -> None:
        resolved_base_url = base_url or settings.NHM_API_BASE_URL
        super().__init__(
            base_url=resolved_base_url,
            client=client,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            backoff_base=backoff_base,
            raise_on_error=raise_on_error,
        )
        self.source_id = source_id
        self.licence = licence
        self.publisher = publisher
        self.source_name = source_name

    def fetch_sources(self) -> list[SourceSummary]:
        """Return SourceSummary attribution for NHM."""
        return [
            SourceSummary(
                source_id=self.source_id,
                publisher=self.publisher,
                name=self.source_name,
                url=self.base_url or "https://nrhmorissa.gov.in",
                licence=self.licence,
                reference_period=None,
                retrieved_at=datetime.now(UTC),
                verification_status=VerificationStatus.VERIFIED,
            )
        ]

    def fetch_observations(self, place_id: str, *, raise_on_error: bool | None = None) -> list[Observation]:
        """Fetch health observations for place_id and parse into HealthObservation records."""
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        try:
            if not self.base_url:
                raise ProviderConfigurationError("NHM API base URL is not configured.")
            url = self._build_url(place_id)
            payload = self._fetch_json(url)
            return self._parse_payload(payload, place_id)
        except UnsafeURLError:
            raise
        except Exception as exc:
            logger.warning(
                "NHM upstream fetch failed",
                extra={
                    "extra_fields": {
                        "provider": "NHMHealthAdapter",
                        "place_id": place_id,
                        "error": str(exc),
                    }
                },
            )
            if should_raise:
                if isinstance(exc, ProviderError):
                    raise
                raise ProviderUnavailableError(f"NHM health fetch failed for {place_id}: {exc}") from exc
            return self._unavailable_observations(place_id, error_reason=str(exc))

    def _unavailable_observations(self, place_id: str, error_reason: str = "") -> list[Observation]:
        """Return canonical health observations marked as UNAVAILABLE."""
        now = datetime.now(UTC)
        note = f"Upstream unavailable: {error_reason}" if error_reason else "Data unavailable from upstream"
        return [
            HealthObservation(
                field_name="primary_health_centres",
                value=None,
                unit="facilities",
                place_id=place_id,
                source_id=self.source_id,
                quality_status=DataStatus.UNAVAILABLE,
                licence=self.licence,
                domain=DOMAIN_HEALTH,
                retrieved_at=now,
                notes=note,
                health_category=HealthCategory.ROUTINE_SURVEILLANCE,
                issuing_authority=self.publisher,
                affected_geography_level=GeographyLevel.DISTRICT,
            ),
            HealthObservation(
                field_name="dengue_cases",
                value=None,
                unit="cases",
                place_id=place_id,
                source_id=self.source_id,
                quality_status=DataStatus.UNAVAILABLE,
                licence=self.licence,
                domain=DOMAIN_HEALTH,
                retrieved_at=now,
                notes=note,
                health_category=HealthCategory.ROUTINE_SURVEILLANCE,
                issuing_authority=self.publisher,
                affected_geography_level=GeographyLevel.DISTRICT,
                disease_code="A90",
            ),
        ]

    def _parse_payload(self, payload: Any, place_id: str) -> list[Observation]:
        """Parse raw upstream payload into typed HealthObservation records."""
        now = datetime.now(UTC)
        results: list[Observation] = []

        if isinstance(payload, dict) and "records" in payload and isinstance(payload["records"], list):
            records = payload["records"]
        elif isinstance(payload, list):
            records = payload
        else:
            records = None

        if records is not None:
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                field_name = str(rec.get("field_name", "")).strip()
                if not field_name:
                    continue

                val = rec.get("value")
                unit = rec.get("unit")
                notes = rec.get("notes")
                authority = rec.get("issuing_authority") or self.publisher
                disease_code = rec.get("disease_code")

                # Health category
                raw_cat = rec.get("health_category")
                try:
                    category = HealthCategory(raw_cat) if raw_cat else HealthCategory.ROUTINE_SURVEILLANCE
                except ValueError:
                    category = HealthCategory.ROUTINE_SURVEILLANCE

                # Affected geography
                raw_geo = rec.get("affected_geography_level")
                try:
                    geo_level = GeographyLevel(raw_geo) if raw_geo else GeographyLevel.DISTRICT
                except ValueError:
                    geo_level = GeographyLevel.DISTRICT

                if not unit:
                    if "cases" in field_name:
                        unit = "cases"
                    elif "centre" in field_name or "facility" in field_name or "hospital" in field_name:
                        unit = "facilities"

                if not disease_code:
                    if "dengue" in field_name:
                        disease_code = "A90"
                    elif "cholera" in field_name:
                        disease_code = "A00"

                value: float | str | None = None
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    value = float(val)
                elif val is not None:
                    value = str(val)

                obs = HealthObservation(
                    field_name=field_name,
                    value=value,
                    unit=unit,
                    place_id=place_id,
                    source_id=self.source_id,
                    domain=DOMAIN_HEALTH,
                    licence=self.licence,
                    quality_status=DataStatus.CURRENT if val is not None else DataStatus.UNAVAILABLE,
                    retrieved_at=now,
                    published_at=_parse_datetime(rec.get("published_at")),
                    reference_period_start=_parse_date(rec.get("reference_period_start")),
                    reference_period_end=_parse_date(rec.get("reference_period_end")),
                    notes=notes or f"NHM official {category.value} data.",
                    health_category=category,
                    issuing_authority=authority,
                    affected_geography_level=geo_level,
                    severity=rec.get("severity"),
                    disease_code=disease_code,
                    valid_from=_parse_datetime(rec.get("valid_from")),
                    valid_until=_parse_datetime(rec.get("valid_until")),
                    prevention_link=rec.get("prevention_link"),
                    prevention_link_date=_parse_date(rec.get("prevention_link_date")),
                )
                results.append(obs)
            return results

        # Fallback: Dictionary of facility counts or surveillance
        data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            return self._unavailable_observations(place_id, error_reason="Unrecognized payload structure")

        # Facilities
        facility_fields = [
            ("primary_health_centres", "facilities", "Primary Health Centres"),
            ("community_health_centres", "facilities", "Community Health Centres"),
            ("sub_centres", "facilities", "Health Sub-Centres"),
            ("district_hospitals", "facilities", "District Hospitals"),
        ]
        for field, unit, label in facility_fields:
            val = data.get(field)
            if val is not None:
                results.append(
                    HealthObservation(
                        field_name=field,
                        value=float(val) if isinstance(val, (int, float)) else str(val),
                        unit=unit,
                        place_id=place_id,
                        source_id=self.source_id,
                        domain=DOMAIN_HEALTH,
                        licence=self.licence,
                        quality_status=DataStatus.CURRENT,
                        retrieved_at=now,
                        notes=f"NHM Public Health Infrastructure: {label}.",
                        health_category=HealthCategory.ROUTINE_SURVEILLANCE,
                        issuing_authority=self.publisher,
                        affected_geography_level=GeographyLevel.DISTRICT,
                    )
                )

        # Surveillance
        surveillance_fields = [
            ("dengue_cases", "cases", "A90", "Dengue surveillance confirmed/probable cases"),
            ("cholera_cases", "cases", "A00", "Acute diarrheal culture-positive cholera cases"),
        ]
        for field, unit, code, desc in surveillance_fields:
            val = data.get(field)
            if val is not None:
                results.append(
                    HealthObservation(
                        field_name=field,
                        value=float(val) if isinstance(val, (int, float)) else str(val),
                        unit=unit,
                        place_id=place_id,
                        source_id=self.source_id,
                        domain=DOMAIN_HEALTH,
                        licence=self.licence,
                        quality_status=DataStatus.CURRENT,
                        retrieved_at=now,
                        notes=desc,
                        health_category=HealthCategory.ROUTINE_SURVEILLANCE,
                        issuing_authority=self.publisher,
                        affected_geography_level=GeographyLevel.DISTRICT,
                        disease_code=code,
                    )
                )

        if not results:
            return self._unavailable_observations(place_id, error_reason="No matching health fields found")

        return results
