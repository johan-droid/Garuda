"""Unit tests for the upstream provider adapter layer.

Validates:
  * Strict SSRF prevention (passing private IPs raises `UnsafeURLError`).
  * Field mapping and provenance attribution into canonical domain contracts.
  * Dependency injection of clients and base URLs with zero real network traffic.
  * Graceful degradation on upstream timeouts and HTTP errors.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch
import pytest

import httpx

from app.core.config import settings
from app.domain.common import (
    DOMAIN_HEALTH,
    DOMAIN_WEATHER_DISASTERS,
    DataStatus,
    GeographyLevel,
    HealthCategory,
    VerificationStatus,
)
from app.domain.contracts import HealthObservation, Observation, SourceSummary
from app.services.http_client import UnsafeURLError
from app.services.provider_adapters import (
    BaseProviderAdapter,
    IMDWeatherAdapter,
    NHMHealthAdapter,
    ProviderConfigurationError,
    ProviderError,
    ProviderUnavailableError,
)

# Use public test IP to avoid DNS resolution during unit tests
TEST_PUBLIC_BASE = "https://8.8.8.8/weather"
TEST_HEALTH_BASE = "https://8.8.8.8/health"


def _make_mock_client(handler: Any) -> httpx.Client:
    """Create an httpx.Client wired to a MockTransport with zero real network calls."""
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


# -----------------------------------------------------------------------------
# 1. Base Class Protocol & Abstract Method Tests
# -----------------------------------------------------------------------------


def test_base_provider_adapter_is_abstract() -> None:
    """BaseProviderAdapter cannot be instantiated directly."""
    assert issubclass(ProviderUnavailableError, ProviderError)
    assert issubclass(ProviderConfigurationError, ProviderError)
    with pytest.raises(TypeError):
        BaseProviderAdapter()  # type: ignore[abstract]


# -----------------------------------------------------------------------------
# 2. SSRF Protection Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "private_url",
    [
        "http://127.0.0.1:8000/weather",
        "http://localhost:5000/data",
        "http://192.168.1.1/api/v1/weather",
        "http://10.0.0.1/weather",
        "http://172.16.0.1/weather",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_imd_adapter_ssrf_protection_private_ip(private_url: str) -> None:
    """Passing private, loopback, or metadata addresses MUST raise UnsafeURLError."""
    adapter = IMDWeatherAdapter(base_url=private_url)
    with pytest.raises(UnsafeURLError):
        adapter.fetch_observations("IN-OD-29")


@pytest.mark.parametrize(
    "private_url",
    [
        "http://127.0.0.1/health",
        "http://192.168.0.100/health",
        "http://10.200.1.1/nhm",
    ],
)
def test_nhm_adapter_ssrf_protection_private_ip(private_url: str) -> None:
    """NHMHealthAdapter enforces SSRF validation identically."""
    adapter = NHMHealthAdapter(base_url=private_url)
    with pytest.raises(UnsafeURLError):
        adapter.fetch_observations("IN-OD-29")


def test_adapter_rejects_non_http_schemes() -> None:
    """File, FTP, or other non-HTTP schemes fail SSRF check."""
    adapter = IMDWeatherAdapter(base_url="ftp://8.8.8.8/weather")
    with pytest.raises(UnsafeURLError, match="Only http and https"):
        adapter.fetch_observations("IN-OD-29")


# -----------------------------------------------------------------------------
# 3. IMD Weather Adapter - Ingestion & Field Mapping Tests
# -----------------------------------------------------------------------------


def test_imd_weather_adapter_successful_dict_payload() -> None:
    """Ingests flat dictionary payload and maps to canonical Observation objects."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("IN-OD-29")
        assert request.headers.get("User-Agent") == settings.UPSTREAM_USER_AGENT
        payload = {
            "surface_temperature_celsius": 31.8,
            "rainfall_daily_mm": 4.6,
            "cyclone_preparedness_advisory": (
                "NDMA Coastal Advisory: Pre-monsoon disaster response protocol active."
            ),
        }
        return httpx.Response(200, json=payload)

    client = _make_mock_client(handler)
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE, client=client)

    observations = adapter.fetch_observations("IN-OD-29")
    assert len(observations) == 3

    obs_by_field = {obs.field_name: obs for obs in observations}

    # 1. Temperature
    temp = obs_by_field["surface_temperature_celsius"]
    assert isinstance(temp, Observation)
    assert temp.value == 31.8
    assert temp.unit == "°C"
    assert temp.place_id == "IN-OD-29"
    assert temp.domain == DOMAIN_WEATHER_DISASTERS
    assert temp.source_id == "src-imd"
    assert temp.licence == "GODL-India"
    assert temp.quality_status == DataStatus.CURRENT

    # 2. Rainfall
    rain = obs_by_field["rainfall_daily_mm"]
    assert rain.value == 4.6
    assert rain.unit == "mm"
    assert rain.place_id == "IN-OD-29"
    assert rain.domain == DOMAIN_WEATHER_DISASTERS
    assert rain.source_id == "src-imd"
    assert rain.licence == "GODL-India"
    assert rain.quality_status == DataStatus.CURRENT

    # 3. Cyclone preparedness advisory
    adv = obs_by_field["cyclone_preparedness_advisory"]
    assert adv.value == "NDMA Coastal Advisory: Pre-monsoon disaster response protocol active."
    assert adv.unit is None
    assert adv.place_id == "IN-OD-29"
    assert adv.domain == DOMAIN_WEATHER_DISASTERS
    assert adv.source_id == "src-imd"
    assert adv.licence == "GODL-India"
    assert adv.quality_status == DataStatus.CURRENT


def test_imd_weather_adapter_records_list_payload() -> None:
    """Parses records list with field aliases, timestamps, and reference periods."""
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "metadata": {"source": "IMD Bhubaneswar"},
            "records": [
                {
                    "field_name": "temp_c",
                    "value": 32.2,
                    "unit": "°C",
                    "published_at": "2026-10-22T06:00:00Z",
                    "reference_period_start": "2026-10-22",
                    "reference_period_end": "2026-10-22",
                },
                {
                    "field_name": "daily_rainfall_mm",
                    "value": 5.2,
                    "unit": "mm",
                },
                {
                    "field_name": "cyclone_advisory",
                    "value": "Coastal alert active for Puri and Khordha.",
                },
            ],
        }
        return httpx.Response(200, json=payload)

    client = _make_mock_client(handler)
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE, client=client)

    observations = adapter.fetch_observations("IN-OD-BBSR")
    assert len(observations) == 3

    obs_by_field = {obs.field_name: obs for obs in observations}
    assert "surface_temperature_celsius" in obs_by_field
    temp = obs_by_field["surface_temperature_celsius"]
    assert temp.value == 32.2
    assert temp.published_at == datetime(2026, 10, 22, 6, 0, tzinfo=UTC)

    assert "rainfall_daily_mm" in obs_by_field
    assert obs_by_field["rainfall_daily_mm"].value == 5.2

    assert "cyclone_preparedness_advisory" in obs_by_field
    assert "Coastal alert" in str(obs_by_field["cyclone_preparedness_advisory"].value)


def test_imd_weather_adapter_fetch_sources() -> None:
    """Verifies source attribution summary for IMD."""
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE)
    sources = adapter.fetch_sources()

    assert len(sources) == 1
    src = sources[0]
    assert isinstance(src, SourceSummary)
    assert src.source_id == "src-imd"
    assert "India Meteorological Department" in src.publisher
    assert src.licence == "GODL-India"
    assert src.verification_status == VerificationStatus.VERIFIED


# -----------------------------------------------------------------------------
# 4. NHM Health Adapter - Health Observations & Surveillance Tests
# -----------------------------------------------------------------------------


def test_nhm_health_adapter_facility_counts_and_surveillance() -> None:
    """Parses facility counts and surveillance figures into HealthObservation objects."""
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "place_id": "IN-OD-29",
            "primary_health_centres": 34,
            "community_health_centres": 10,
            "sub_centres": 218,
            "district_hospitals": 2,
            "dengue_cases": 142,
            "cholera_cases": 18,
        }
        return httpx.Response(200, json=payload)

    client = _make_mock_client(handler)
    adapter = NHMHealthAdapter(base_url=TEST_HEALTH_BASE, client=client)

    observations = adapter.fetch_observations("IN-OD-29")
    assert len(observations) == 6

    obs_by_field = {obs.field_name: obs for obs in observations}

    # Verify all are HealthObservation instances
    for obs in observations:
        assert isinstance(obs, HealthObservation)
        assert obs.domain == DOMAIN_HEALTH
        assert obs.source_id == "src-mohfw-nhm"
        assert obs.licence == "GODL-India"
        assert obs.place_id == "IN-OD-29"
        assert obs.quality_status == DataStatus.CURRENT
        assert obs.health_category == HealthCategory.ROUTINE_SURVEILLANCE
        assert obs.issuing_authority != ""
        assert obs.affected_geography_level == GeographyLevel.DISTRICT

    # Verify facility counts
    assert obs_by_field["primary_health_centres"].value == 34.0
    assert obs_by_field["primary_health_centres"].unit == "facilities"

    assert obs_by_field["community_health_centres"].value == 10.0
    assert obs_by_field["community_health_centres"].unit == "facilities"

    # Verify disease surveillance codes
    dengue = obs_by_field["dengue_cases"]
    assert isinstance(dengue, HealthObservation)
    assert dengue.value == 142.0
    assert dengue.unit == "cases"
    assert dengue.disease_code == "A90"

    cholera = obs_by_field["cholera_cases"]
    assert isinstance(cholera, HealthObservation)
    assert cholera.value == 18.0
    assert cholera.unit == "cases"
    assert cholera.disease_code == "A00"


def test_nhm_health_adapter_records_list_with_official_alert() -> None:
    """Parses records list containing official health notice with validity window."""
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {
            "records": [
                {
                    "field_name": "cholera_water_safety_alert",
                    "value": "Heightened waterborne disease precautions active.",
                    "unit": None,
                    "health_category": "official_alert",
                    "issuing_authority": "Directorate of Public Health, Government of Odisha",
                    "affected_geography_level": "district",
                    "severity": "high",
                    "disease_code": "A00",
                    "valid_from": "2026-10-20T00:00:00Z",
                    "valid_until": "2026-10-27T00:00:00Z",
                    "prevention_link": "https://www.who.int/news-room/fact-sheets/detail/cholera",
                    "prevention_link_date": "2026-10-20",
                }
            ]
        }
        return httpx.Response(200, json=payload)

    client = _make_mock_client(handler)
    adapter = NHMHealthAdapter(base_url=TEST_HEALTH_BASE, client=client)

    observations = adapter.fetch_observations("IN-OD-29")
    assert len(observations) == 1

    alert = observations[0]
    assert isinstance(alert, HealthObservation)
    assert alert.field_name == "cholera_water_safety_alert"
    assert alert.health_category == HealthCategory.OFFICIAL_ALERT
    assert alert.issuing_authority == "Directorate of Public Health, Government of Odisha"
    assert alert.severity == "high"
    assert alert.disease_code == "A00"
    assert alert.valid_from == datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
    assert alert.valid_until == datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
    assert alert.prevention_link == "https://www.who.int/news-room/fact-sheets/detail/cholera"
    assert not alert.is_expired(now=datetime(2026, 10, 22, 0, 0, tzinfo=UTC))


def test_nhm_health_adapter_fetch_sources() -> None:
    """Verifies source attribution summary for NHM."""
    adapter = NHMHealthAdapter(base_url=TEST_HEALTH_BASE)
    sources = adapter.fetch_sources()

    assert len(sources) == 1
    src = sources[0]
    assert isinstance(src, SourceSummary)
    assert src.source_id == "src-mohfw-nhm"
    assert "National Health Mission" in src.publisher
    assert src.licence == "GODL-India"
    assert src.verification_status == VerificationStatus.VERIFIED


# -----------------------------------------------------------------------------
# 5. Upstream Timeout & HTTP Error Handling Tests
# -----------------------------------------------------------------------------


def test_upstream_timeout_graceful_unavailable() -> None:
    """When upstream times out, returns canonical UNAVAILABLE observations by default."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out connecting to upstream.")

    client = _make_mock_client(handler)
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE, client=client, max_retries=0)

    # Default: raise_on_error=False
    observations = adapter.fetch_observations("IN-OD-29")
    assert len(observations) == 3
    for obs in observations:
        assert obs.quality_status == DataStatus.UNAVAILABLE
        assert obs.value is None
        assert "timed out" in (obs.notes or "").lower()


def test_upstream_timeout_raises_when_configured() -> None:
    """When raise_on_error=True, timeout raises ProviderUnavailableError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out.")

    client = _make_mock_client(handler)
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE, client=client, max_retries=0, raise_on_error=True)

    with pytest.raises(ProviderUnavailableError, match="timed out"):
        adapter.fetch_observations("IN-OD-29")


def test_upstream_http_503_error_handling() -> None:
    """HTTP 5xx server errors return UNAVAILABLE status gracefully or raise."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    client = _make_mock_client(handler)
    adapter = NHMHealthAdapter(base_url=TEST_HEALTH_BASE, client=client, max_retries=0)

    # Graceful fallback: returns unavailable health observations
    observations = adapter.fetch_observations("IN-OD-29", raise_on_error=False)
    assert len(observations) >= 1
    assert all(o.quality_status == DataStatus.UNAVAILABLE for o in observations)

    # When raise_on_error=True: raises ProviderUnavailableError
    with pytest.raises(ProviderUnavailableError):
        adapter.fetch_observations("IN-OD-29", raise_on_error=True)


def test_upstream_http_404_error_handling() -> None:
    """HTTP 404 client error raises or returns unavailable status."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Place Not Found")

    client = _make_mock_client(handler)
    adapter = IMDWeatherAdapter(base_url=TEST_PUBLIC_BASE, client=client, max_retries=0)

    observations = adapter.fetch_observations("IN-UNKNOWN", raise_on_error=False)
    assert all(o.quality_status == DataStatus.UNAVAILABLE for o in observations)

    with pytest.raises(ProviderUnavailableError):
        adapter.fetch_observations("IN-UNKNOWN", raise_on_error=True)


# -----------------------------------------------------------------------------
# 6. Dependency Injection & Offline Safety Tests
# -----------------------------------------------------------------------------


def test_adapter_without_configured_url_makes_zero_network_calls() -> None:
    """Unconfigured adapter makes zero network calls and returns unavailable observations."""
    with patch.object(settings, "IMD_API_BASE_URL", None), patch.object(settings, "NHM_API_BASE_URL", None):
        imd = IMDWeatherAdapter(base_url=None)
        nhm = NHMHealthAdapter(base_url=None)

        # In unconfigured mode, returns unavailable observations without network calls
        imd_obs = imd.fetch_observations("IN-OD-29")
        assert len(imd_obs) == 3
        assert all(o.quality_status == DataStatus.UNAVAILABLE for o in imd_obs)

        nhm_obs = nhm.fetch_observations("IN-OD-29")
        assert len(nhm_obs) >= 1
        assert all(o.quality_status == DataStatus.UNAVAILABLE for o in nhm_obs)

        # If raise_on_error is set to True, raises ProviderConfigurationError
        with pytest.raises(ProviderConfigurationError):
            imd.fetch_observations("IN-OD-29", raise_on_error=True)

        with pytest.raises(ProviderConfigurationError):
            nhm.fetch_observations("IN-OD-29", raise_on_error=True)


def test_adapter_retry_recovers_after_transient_failure() -> None:
    """Adapter retries transient 500 failure and succeeds on subsequent attempt."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="Temporary upstream glitch")
        return httpx.Response(200, json={"surface_temperature_celsius": 30.5})

    client = _make_mock_client(handler)
    # Using backoff_base=0.001 to run instantly in test
    adapter = IMDWeatherAdapter(
        base_url=TEST_PUBLIC_BASE,
        client=client,
        max_retries=2,
        backoff_base=0.001,
        raise_on_error=True,
    )

    observations = adapter.fetch_observations("IN-OD-29")
    assert call_count == 2
    assert len(observations) == 1
    assert observations[0].field_name == "surface_temperature_celsius"
    assert observations[0].value == 30.5
