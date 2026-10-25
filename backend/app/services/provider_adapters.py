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
    DOMAIN_ENVIRONMENT,
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
from app.services.circuit import CircuitBreaker, CircuitOpenError, breaker_for
from app.services.http_client import UnsafeURLError, fetch_json, validate_url

import json

logger = get_logger("garuda.providers")


class ProviderError(Exception):
    """Base exception for provider adapter errors."""


class ProviderUnavailableError(ProviderError):
    """Raised when an upstream provider fails, times out, or returns errors."""


class ProviderConfigurationError(ProviderError):
    """Raised when an adapter is not configured (e.g. missing base URL)."""


class ProviderTimeoutError(ProviderUnavailableError):
    """Raised when an upstream provider timed out."""


class ProviderRateLimitedError(ProviderError):
    """Raised when an upstream provider rate-limited the request."""


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
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
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
        # Shared per upstream, not per instance: routes build a new adapter on
        # every request, and a breaker that died with its adapter would never
        # accumulate enough failures to notice a persistently dead source.
        self._breaker: CircuitBreaker = breaker_for(f"{type(self).__name__}:{base_url}")

    @abstractmethod
    @abstractmethod
    def fetch_observations_for_bbox(
        self, west: float, south: float, east: float, north: float, *, raise_on_error: bool | None = None
    ) -> list[Observation]:
        """Fetch and return parsed observations for a bounding box."""
        ...

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
            raise ProviderConfigurationError(f"Upstream base URL is not configured for {self.__class__.__name__}.")
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

        SSRF protection: UnsafeURLError is NEVER swallowed and will be raised
        immediately. The address is validated *before* the breaker is
        consulted, so refusing a call can never hide a bad URL.

        The breaker is consulted once per request rather than per attempt:
        retries are what smooths a blip, the breaker is what stops us paying a
        dead upstream over and over.
        """
        validate_url(url)

        try:
            self._breaker.before_request()
        except CircuitOpenError as exc:
            # Re-raised as the typed error callers already expect, so the
            # adapters' graceful-degradation paths treat a refused call like
            # any other upstream failure instead of a new failure mode.
            raise ProviderUnavailableError(str(exc)) from exc

        try:
            payload = self._request_with_retries(url)
        except Exception:
            # One failure per request, counted only after the retry budget is
            # spent: a blip the retries absorbed must not open the breaker.
            self._breaker.record_failure()
            raise
        self._breaker.record_success()
        return payload

    def _request_with_retries(self, url: str) -> Any:
        """Run the retry/backoff loop for one upstream URL. Unchanged behaviour
        from the original `_fetch_json`, merely named so the breaker can wrap it.
        """
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
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < attempts - 1 and self.backoff_base > 0:
                    time.sleep(min(backoff, settings.UPSTREAM_BACKOFF_MAX_SECONDS))
                    backoff *= 2
                else:
                    raise ProviderTimeoutError(f"Upstream timed out after {attempts} attempt(s): {url}") from exc
            except httpx.NetworkError as exc:
                last_error = exc
                if attempt < attempts - 1 and self.backoff_base > 0:
                    time.sleep(min(backoff, settings.UPSTREAM_BACKOFF_MAX_SECONDS))
                    backoff *= 2
            except httpx.HTTPStatusError as exc:
                if exc.response is not None and exc.response.status_code == 429:
                    raise ProviderRateLimitedError(f"Upstream rate-limited the request: {url}") from exc
                last_error = exc
                if exc.response is not None and exc.response.status_code >= 500 and attempt < attempts - 1:
                    if self.backoff_base > 0:
                        time.sleep(min(backoff, settings.UPSTREAM_BACKOFF_MAX_SECONDS))
                        backoff *= 2
                    continue
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

    def fetch_observations_for_bbox(
        self, west: float, south: float, east: float, north: float, *, raise_on_error: bool | None = None
    ) -> list[Observation]:
        """IMD does not provide bbox-based observations; return unavailable."""
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if should_raise:
            raise ProviderUnavailableError("IMD does not support bbox queries")
        return self._unavailable_observations("bbox", error_reason="IMD does not support bbox queries")

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


class EarthSearchSentinelAdapter(BaseProviderAdapter):
    """Adapter for Earth Search STAC (Sentinel-2 L2A) scene metadata.

    Returns imagery *metadata* for the most recent cloud-free scene whose
    footprint covers the requested bounding box. It does not fetch imagery
    pixels in this path; pixel mosaics are built separately by the imagery
    tooling under `tools/imagery/`.

    Source: Element84 Earth Search STAC public API hosting Copernicus Sentinel-2
    L2A COGs on AWS Open Data. Sentinel data is Copernicus/ESA; the project
    must carry the standard Sentinel attribution.

    Anonymous access was verified during audit: a bounded search over the Khordha
    bbox returned `numberMatched` scenes without any key or account.

    Honesty constraints implemented here:
      * The returned observation describes the *latest available* scene, never a
        live image. The `scene_timestamp` is the acquisition time, and the panel
        must label the datum as observed/labelled accordingly.
      * `cloud_cover_percentage` is the scene-level cloud fraction reported by the
        STAC item, not a per-pixel cloud assessment for the pin.
      * `spatial_resolution_meters` is the nominal Sentinel-2 visible-band ground
        resolution (10 m), not a guarantee of cloud-free coverage at the pin.
      * If no scene covers the bbox within the requested window, the adapter
        returns an explicit `unavailable` observation with a notes field — never
        a guessed date or a zero cloud value.
    """

    SOURCE_ID = "src-esa-sentinel-stac"
    PUBLISHER = "Element84 (Earth Search STAC) / Copernicus Sentinel-2"
    SOURCE_NAME = "Earth Search Sentinel-2 L2A Scene Catalog"
    LICENCE = "Copernicus Sentinel data processed by Element84; Sentinel data © ESA/Copernicus"
    SENTINEL_ATTRIBUTION = (
        "Contains modified Copernicus Sentinel data 2025-2026. "
        "Sentinel data (Copernicus/ESA) licensed under the Copernicus Data Space "
        "licence; reproduced with attribution."
    )

    SPATIAL_RESOLUTION_METERS = 10.0

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        raise_on_error: bool = False,
        stac_endpoint: str | None = None,
        collection: str = "sentinel-2-l2a",
        max_cloud_cover: float = 40.0,
        max_scenes: int = 50,
        default_date_end: str = "2026-12-31T23:59:59Z",
    ) -> None:
        resolved_stac = (
            stac_endpoint
            or getattr(settings, "EARTH_SEARCH_STAC_ENDPOINT", None)
            or "https://earth-search.aws.element84.com/v1"
        )
        super().__init__(
            base_url=resolved_stac,
            client=client,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=1 if not raise_on_error else max_retries,
            backoff_base=backoff_base,
            raise_on_error=raise_on_error,
        )
        self.stac_endpoint = resolved_stac
        self.collection = collection
        self.max_cloud_cover = max_cloud_cover
        self.max_scenes = max_scenes
        self.default_date_end = default_date_end
        self.source_id = self.SOURCE_ID
        self.licence = self.LICENCE
        self.publisher = self.PUBLISHER
        self.source_name = self.SOURCE_NAME

    def fetch_sources(self) -> list[SourceSummary]:
        return [
            SourceSummary(
                source_id=self.source_id,
                publisher=self.publisher,
                name=self.source_name,
                url=self.stac_endpoint,
                licence=self.licence,
                reference_period=None,
                retrieved_at=datetime.now(UTC),
                verification_status=VerificationStatus.VERIFIED_WITH_LIMITS,
            )
        ]

    def fetch_observations(self, place_id: str, *, raise_on_error: bool | None = None) -> list[Observation]:
        raise NotImplementedError(
            "EarthSearchSentinelAdapter.fetch_observations is not used in the app path. "
            "Use fetch_observations_for_bbox with an explicit bounding box."
        )

    def fetch_observations_for_bbox(
        self, west: float, south: float, east: float, north: float, *, raise_on_error: bool | None = None
    ) -> list[Observation]:
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        try:
            scenes = self._search_scenes(west, south, east, north)
            return self._best_observation(scenes, west, south, east, north)
        except ProviderError:
            raise
        except Exception as exc:
            logger.warning(
                "Sentinel STAC upstream fetch failed",
                extra={
                    "extra_fields": {
                        "provider": self.__class__.__name__,
                        "bbox": [west, south, east, north],
                        "error": str(exc),
                    }
                },
            )
            if should_raise:
                raise ProviderUnavailableError(f"Sentinel STAC query failed for the requested area: {exc}") from exc
            return self._unavailable_observations("bbox", error_reason=str(exc), bbox=(west, south, east, north))

    def _search_scenes(self, west: float, south: float, east: float, north: float) -> list[dict]:
        url = self._build_stac_search_url(west, south, east, north)
        payload = self._fetch_json(url)
        if not isinstance(payload, dict):
            raise ProviderUnavailableError("Sentinel STAC returned a non-JSON response.")
        features = payload.get("features")
        if not isinstance(features, list):
            raise ProviderUnavailableError("Sentinel STAC response did not include a feature list.")
        return features

    def _build_stac_search_url(self, west: float, south: float, east: float, north: float) -> str:
        import urllib.parse

        params = urllib.parse.urlencode(
            {
                "collections": self.collection,
                "bbox": f"{west:.6f},{south:.6f},{east:.6f},{north:.6f}",
                "datetime": f"2025-01-01T00:00:00Z/{self.default_date_end}",
                "query": json.dumps({"eo:cloud_cover": {"lte": self.max_cloud_cover}}),
                "limit": self.max_scenes,
            }
        )
        return f"{self.stac_endpoint.rstrip('/')}/search?{params}"

    def _best_observation(
        self, scenes: list[dict], west: float, south: float, east: float, north: float
    ) -> list[Observation]:
        now = datetime.now(UTC)
        candidates = []
        for scene in scenes:
            item = self._as_item(scene)
            if item is None:
                continue
            if not self._footprint_covers(item["bbox"], west, south, east, north):
                continue
            candidates.append(item)

        if not candidates:
            return [
                Observation(
                    field_name="latest_sentinel2_scene",
                    value=None,
                    unit=None,
                    place_id="bbox",
                    source_id=self.source_id,
                    domain=DOMAIN_ENVIRONMENT,
                    licence=self.licence,
                    quality_status=DataStatus.UNAVAILABLE,
                    retrieved_at=now,
                    notes=self._no_scene_note(west, south, east, north),
                    satellite_mission="Sentinel-2 (ESA/Copernicus)",
                    resolution_meters=self.SPATIAL_RESOLUTION_METERS,
                    source_url=self.stac_endpoint,
                )
            ]

        candidates.sort(key=lambda c: (-c["datetime"].timestamp(), c["cloud_cover"]))
        best = candidates[0]
        return [
            Observation(
                field_name="latest_sentinel2_scene",
                value=best["scene_id"],
                unit=None,
                place_id="bbox",
                source_id=self.source_id,
                domain=DOMAIN_ENVIRONMENT,
                licence=self.licence,
                quality_status=DataStatus.CURRENT,
                retrieved_at=now,
                published_at=best["datetime"],
                reference_period_start=best["datetime"].date(),
                reference_period_end=best["datetime"].date(),
                notes=(
                    f"Latest available Sentinel-2 L2A scene covering the requested area. "
                    f"Acquisition date {best['datetime'].isoformat()}; scene-level cloud "
                    f"fraction {best['cloud_cover']:.1f}%. This is the most recent cloud-"
                    f"tolerant scene over the requested bbox, not a live image of the "
                    f"moment. Spatial resolution {self.SPATIAL_RESOLUTION_METERS:.0f} m "
                    f"(nominal visible bands). Sentinel data (Copernicus/ESA) reproduced "
                    f"with attribution."
                ),
                source_url=best["stac_href"],
                satellite_mission="Sentinel-2 (ESA/Copernicus)",
                resolution_meters=self.SPATIAL_RESOLUTION_METERS,
                cloud_cover_percentage=round(best["cloud_cover"], 2),
                scene_timestamp=best["datetime"].isoformat(),
            )
        ]

    def _as_item(self, scene: Any) -> dict | None:
        if not isinstance(scene, dict):
            return None
        props = scene.get("properties")
        if not isinstance(props, dict):
            return None
        dt = _parse_datetime(props.get("datetime"))
        if dt is None:
            return None
        cloud_raw = props.get("eo:cloud_cover")
        try:
            cloud = float(cloud_raw) if cloud_raw is not None else -1.0
        except (TypeError, ValueError):
            cloud = -1.0
        bbox = scene.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            return None
        try:
            bbox = [float(v) for v in bbox]
        except (TypeError, ValueError):
            return None
        scene_id = str(scene.get("id") or "").strip() or "unknown"
        stac_href = scene.get("href")
        if not isinstance(stac_href, str) or not stac_href:
            stac_href = f"{self.stac_endpoint.rstrip('/')}/collections/{self.collection}/items/{scene_id}"
        return {
            "scene_id": scene_id,
            "datetime": dt,
            "cloud_cover": cloud,
            "bbox": bbox,
            "stac_href": stac_href,
        }

    def _footprint_covers(self, bbox: list[float], west: float, south: float, east: float, north: float) -> bool:
        bw, bs, be, bn = bbox
        return bw <= west and bs <= south and be >= east and bn >= north

    def _no_scene_note(self, west: float, south: float, east: float, north: float) -> str:
        return (
            f"No Sentinel-2 L2A scene with cloud cover ≤ {self.max_cloud_cover:.0f}% "
            f"was found covering {west:.3f}°E–{east:.3f}°E, {south:.3f}°N–{north:.3f}°N "
            f"in the searched date window. Satellite imagery may still exist for this "
            f"area but was not returned by the public catalog within the requested "
            f"constraints; try widening the date window or cloud threshold."
        )

    def _unavailable_observations(
        self, place_id: str, error_reason: str = "", *, bbox: tuple[float, float, float, float] | None = None
    ) -> list[Observation]:
        now = datetime.now(UTC)
        note = (
            f"Sentinel STAC unavailable: {error_reason}"
            if error_reason
            else "Sentinel STAC imagery metadata unavailable."
        )
        return [
            Observation(
                field_name="latest_sentinel2_scene",
                value=None,
                unit=None,
                place_id=place_id,
                source_id=self.source_id,
                domain=DOMAIN_ENVIRONMENT,
                licence=self.licence,
                quality_status=DataStatus.UNAVAILABLE,
                retrieved_at=now,
                notes=note,
                satellite_mission="Sentinel-2 (ESA/Copernicus)",
                resolution_meters=self.SPATIAL_RESOLUTION_METERS,
                source_url=self.stac_endpoint,
            )
        ]


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

    def fetch_observations_for_bbox(
        self, west: float, south: float, east: float, north: float, *, raise_on_error: bool | None = None
    ) -> list[Observation]:
        """NHM does not provide bbox-based observations; return unavailable."""
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if should_raise:
            raise ProviderUnavailableError("NHM does not support bbox queries")
        return self._unavailable_observations("bbox", error_reason="NHM does not support bbox queries")

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
