"""NDMA hazard bulletins: alerts, forecasts, and observed events.

The National Disaster Management Authority publishes advisories and
observations, but there is no stable public JSON API. This adapter therefore
keeps the same contract as the other providers - a base URL that is *off by
default*, an honest `unavailable` when it is unset, and a parser that maps
whatever structure does arrive onto canonical records - without pretending a
feed exists.

The distinction this adapter exists to preserve is `record_type`:

  * `alert`     - a warning with a validity window. Past `valid_until` it is
                  expired and served as `unavailable`, never as a warning
                  still in force.
  * `forecast`  - a projection. Never `current`, however recently issued.
  * `observation` - a recorded event, judged on its own date.

An upstream that omits `record_type` is read as an alert, because a hazard
bulletin with a validity window and an issuing authority is an advisory; the
caller can override it per record.
"""

from datetime import UTC, datetime
from typing import Any, cast

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.common import (
    DOMAIN_WEATHER_DISASTERS,
    DataStatus,
    GeographyLevel,
    RecordType,
    VerificationStatus,
)
from app.domain.contracts import DisasterObservation, Observation, SourceSummary
from app.services.provider_adapters import (
    BaseProviderAdapter,
    ProviderConfigurationError,
    ProviderUnavailableError,
    UnsafeURLError,
    _parse_datetime,
)

logger = get_logger("garuda.providers")

DEFAULT_BASE_URL = "https://ndma.gov.in"

# Field names this adapter understands, with the record type each one is.
# Anything else is still ingested, typed as an alert with no window.
FIELD_RECORD_TYPES: dict[str, RecordType] = {
    "cyclone_warning": RecordType.ALERT,
    "cyclone_alert": RecordType.ALERT,
    "flood_warning": RecordType.ALERT,
    "flood_advisory": RecordType.ALERT,
    "heat_wave_advisory": RecordType.ALERT,
    "earthquake_advisory": RecordType.ALERT,
    "landslide_warning": RecordType.ALERT,
    "tsunami_alert": RecordType.ALERT,
    "flood_forecast": RecordType.FORECAST,
    "cyclone_forecast": RecordType.FORECAST,
    "rainfall_forecast": RecordType.FORECAST,
    "discharge_forecast": RecordType.FORECAST,
    "observed_rainfall": RecordType.OBSERVATION,
    "observed_wind": RecordType.OBSERVATION,
    "seismic_event": RecordType.OBSERVATION,
}

_RECORD_TYPES: dict[str, RecordType] = {t.value: t for t in RecordType}


class NDMADisasterAdapter(BaseProviderAdapter):
    """Adapter for NDMA hazard bulletins and advisories."""

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        max_retries: int | None = None,
        backoff_base: float | None = None,
        raise_on_error: bool = False,
        source_id: str = "src-ndma",
        licence: str = "GODL-India",
        publisher: str = "National Disaster Management Authority (NDMA), Ministry of Home Affairs",
        source_name: str = "NDMA Bulletins, Advisories & Observed Hazard Events",
    ) -> None:
        resolved_base_url = base_url or settings.NDMA_API_BASE_URL
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
        """Return SourceSummary attribution for NDMA."""
        return [
            SourceSummary(
                source_id=self.source_id,
                publisher=self.publisher,
                name=self.source_name,
                url=self.base_url or DEFAULT_BASE_URL,
                licence=self.licence,
                reference_period=None,
                retrieved_at=datetime.now(UTC),
                verification_status=VerificationStatus.VERIFIED,
            )
        ]

    def fetch_observations(self, place_id: str, *, raise_on_error: bool | None = None) -> list[Observation]:
        """Fetch hazard records for a place, or an explained absence.

        Declared as `list[Observation]` to satisfy the base contract; the
        concrete records are `DisasterObservation`, and `PanelResponse` keeps
        their extra fields via `SerializeAsAny`.
        """
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        try:
            if not self.base_url:
                raise ProviderConfigurationError("NDMA API base URL is not configured.")
            url = self._build_url(place_id)
            payload = self._fetch_json(url)
            return _as_observations(self._parse_payload(payload, place_id))
        except UnsafeURLError:
            raise
        except Exception as exc:
            logger.warning(
                "NDMA upstream fetch failed",
                extra={
                    "extra_fields": {
                        "provider": "NDMADisasterAdapter",
                        "place_id": place_id,
                        "error": str(exc),
                    }
                },
            )
            if should_raise:
                if isinstance(exc, ProviderUnavailableError):
                    raise
                raise ProviderUnavailableError(f"NDMA fetch failed for {place_id}: {exc}") from exc
            return _as_observations(self._unavailable_observations(place_id, error_reason=str(exc)))

    def fetch_observations_for_bbox(
        self, west: float, south: float, east: float, north: float, *, raise_on_error: bool | None = None
    ) -> list[Observation]:
        """NDMA bulletins are not bbox-queryable; return unavailable."""
        should_raise = self.raise_on_error if raise_on_error is None else raise_on_error
        if should_raise:
            raise ProviderUnavailableError("NDMA does not support bbox queries")
        return _as_observations(
            self._unavailable_observations("bbox", error_reason="NDMA does not support bbox queries")
        )

    def _unavailable_observations(self, place_id: str, error_reason: str = "") -> list[DisasterObservation]:
        """Return canonical records marked UNAVAILABLE, with the reason attached."""
        now = datetime.now(UTC)
        note = f"Upstream unavailable: {error_reason}" if error_reason else "Data unavailable from upstream"
        return [
            self._record(
                field_name="cyclone_warning",
                value=None,
                place_id=place_id,
                quality_status=DataStatus.UNAVAILABLE,
                record_type=RecordType.ALERT,
                notes=note,
                retrieved_at=now,
            ),
            self._record(
                field_name="flood_forecast",
                value=None,
                place_id=place_id,
                quality_status=DataStatus.UNAVAILABLE,
                record_type=RecordType.FORECAST,
                notes=note,
                retrieved_at=now,
            ),
        ]

    def _record(
        self,
        *,
        field_name: str,
        value: float | str | None,
        place_id: str,
        quality_status: DataStatus,
        record_type: RecordType,
        retrieved_at: datetime,
        published_at: datetime | None = None,
        reference_period_start: Any = None,
        reference_period_end: Any = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        issuing_authority: str | None = None,
        severity: str | None = None,
        affected_geography_level: GeographyLevel | None = None,
        notes: str | None = None,
    ) -> DisasterObservation:
        """Build one canonical disaster record."""
        return DisasterObservation(
            field_name=field_name,
            value=value,
            unit=None,
            place_id=place_id,
            source_id=self.source_id,
            domain=DOMAIN_WEATHER_DISASTERS,
            licence=self.licence,
            quality_status=quality_status,
            record_type=record_type,
            retrieved_at=retrieved_at,
            published_at=published_at,
            reference_period_start=reference_period_start,
            reference_period_end=reference_period_end,
            valid_from=valid_from,
            valid_until=valid_until,
            issuing_authority=issuing_authority or self.publisher,
            severity=severity,
            affected_geography_level=affected_geography_level,
            notes=notes,
        )

    def _parse_payload(self, payload: Any, place_id: str) -> list[DisasterObservation]:
        """Parse an upstream payload into canonical disaster records."""
        now = datetime.now(UTC)
        results: list[DisasterObservation] = []

        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
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
                record_type = _resolve_record_type(rec.get("record_type"), field_name)
                severity = rec.get("severity")
                value = _coerce_value(rec.get("value"))
                results.append(
                    self._record(
                        field_name=field_name,
                        value=value,
                        place_id=place_id,
                        # Stored as the kind of statement, not as freshness:
                        # freshness is recomputed at read time, and a forecast
                        # stored `current` would be served as current.
                        quality_status=DataStatus.CURRENT,
                        record_type=record_type,
                        retrieved_at=now,
                        published_at=_parse_datetime(rec.get("published_at")),
                        reference_period_start=_parse_datetime(rec.get("reference_period_start")),
                        reference_period_end=_parse_datetime(rec.get("reference_period_end")),
                        valid_from=_parse_datetime(rec.get("valid_from")),
                        valid_until=_parse_datetime(rec.get("valid_until")),
                        issuing_authority=rec.get("issuing_authority"),
                        severity=str(severity) if severity is not None else None,
                        affected_geography_level=_resolve_geography_level(rec.get("affected_geography_level")),
                        notes=rec.get("notes") or _default_note(field_name, record_type),
                    )
                )
            return results

        # Flat / nested fallback: a single advisory object rather than a list.
        data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            return self._unavailable_observations(place_id, error_reason="Unrecognized payload structure")

        field_name = str(data.get("field_name") or "cyclone_warning").strip() or "cyclone_warning"
        record_type = _resolve_record_type(data.get("record_type"), field_name)
        return [
            self._record(
                field_name=field_name,
                value=str(data.get("value")) if data.get("value") is not None else None,
                place_id=place_id,
                quality_status=DataStatus.CURRENT,
                record_type=record_type,
                retrieved_at=now,
                published_at=_parse_datetime(data.get("published_at")),
                valid_from=_parse_datetime(data.get("valid_from")),
                valid_until=_parse_datetime(data.get("valid_until")),
                issuing_authority=data.get("issuing_authority"),
                severity=str(data.get("severity")) if data.get("severity") is not None else None,
                affected_geography_level=_resolve_geography_level(data.get("affected_geography_level")),
                notes=data.get("notes") or _default_note(field_name, record_type),
            )
        ]


def _as_observations(records: list[DisasterObservation]) -> list[Observation]:
    """Widen disaster records to the base type the adapter contract returns.

    `list` is invariant, so `list[DisasterObservation]` is not a
    `list[Observation]` even though the element type is a subtype. The
    concrete type is preserved at runtime and `PanelResponse` serialises it
    through `SerializeAsAny`, so this is a typing-only widening.
    """
    return cast(list[Observation], records)


def _coerce_value(value: Any) -> float | str | None:
    """Keep a numeric reading numeric and leave text as text.

    A hazard bulletin is mostly prose, so a value is only a number when the
    upstream actually sent one - `"3"` from a CSV-ish feed is still a string
    and must not become `3.0`.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return float(value)
    return str(value)


def _resolve_record_type(raw: Any, field_name: str) -> RecordType:
    """Read a record's type, defaulting to the field's own convention.

    A bulletin that does not say what kind of statement it is gets the type
    its field name implies, and an unrecognised field gets `alert` - the
    cautious reading for a hazard feed, since it is the type that carries a
    validity window and therefore an expiry.
    """
    if raw:
        resolved = _RECORD_TYPES.get(str(raw).strip().lower())
        if resolved is not None:
            return resolved
    return FIELD_RECORD_TYPES.get(field_name.strip().lower(), RecordType.ALERT)


def _resolve_geography_level(raw: Any) -> GeographyLevel | None:
    if not raw:
        return None
    try:
        return GeographyLevel(str(raw).strip().lower())
    except ValueError:
        return None


def _default_note(field_name: str, record_type: RecordType) -> str:
    """Say plainly what kind of statement the record is."""
    if record_type == RecordType.FORECAST:
        return f"NDMA forecast for {field_name}: a projection, not a measurement of the present."
    if record_type == RecordType.ALERT:
        return f"NDMA advisory for {field_name}, issued with a validity window."
    return f"NDMA observed record for {field_name}."
