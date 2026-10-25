"""Live provider endpoints: IMD weather and NHM facility counts.

A 200 from these routes does not mean there is live data. The client reads
`status`: `unavailable` means the upstream is unconfigured, unreachable, or
refused us, and `coverage_note` says which. Nothing here may raise because an
upstream is missing — an unanswered question is an answer.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.common import DataStatus
from app.domain.contracts import Observation
from app.services.provider_adapters import IMDWeatherAdapter, NHMHealthAdapter
from seed_pilot import seed_database


@pytest.fixture(autouse=True)
def _setup_pilot_data(db: Session) -> None:
    """The place lookup these routes perform needs the pilot dataset."""
    seed_database(db)


def _get(client: TestClient, path: str) -> dict:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_weather_reports_unavailable_when_imd_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "IMD_API_BASE_URL", None)

    body = _get(client, "/api/v1/places/IN-OD-29/weather")

    assert body["domain"] == "weather_disasters"
    assert body["status"] == DataStatus.UNAVAILABLE.value
    # Not an exception: an honest, explained absence of data.
    assert "not configured" in (body["coverage_note"] or "")
    assert body["data_gaps"], "an unavailable panel must name what is missing"
    assert body["error"] is None


def test_weather_serves_observations_when_upstream_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)

    def succeed(self: IMDWeatherAdapter, place_id: str, **kwargs: object) -> list[Observation]:
        return [
            Observation(
                field_name="surface_temperature_celsius",
                value=31.8,
                unit="°C",
                place_id=place_id,
                source_id="src-imd",
                domain="weather_disasters",
                licence="GODL-India",
                quality_status=DataStatus.CURRENT,
                reference_period_end=now.date(),
                published_at=now,
                retrieved_at=now,
                notes="IMD observed surface temperature reading.",
            ),
            Observation(
                field_name="rainfall_daily_mm",
                value=4.6,
                unit="mm",
                place_id=place_id,
                source_id="src-imd",
                domain="weather_disasters",
                licence="GODL-India",
                quality_status=DataStatus.CURRENT,
                reference_period_end=now.date(),
                published_at=now,
                retrieved_at=now,
                notes="IMD 24-hour recorded precipitation.",
            ),
        ]

    monkeypatch.setattr(IMDWeatherAdapter, "fetch_observations", succeed)

    body = _get(client, "/api/v1/places/IN-OD-29/weather")

    assert body["status"] == DataStatus.CURRENT.value
    assert [o["field_name"] for o in body["observations"]] == [
        "surface_temperature_celsius",
        "rainfall_daily_mm",
    ]
    assert body["data_gaps"] == []
    assert body["observations"][0]["source_url"]


def test_weather_reports_unavailable_when_upstream_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(self: IMDWeatherAdapter, place_id: str, **kwargs: object) -> list[Observation]:
        raise RuntimeError("IMD upstream refused to connect")

    monkeypatch.setattr(IMDWeatherAdapter, "fetch_observations", fail)

    body = _get(client, "/api/v1/places/IN-OD-29/weather")

    assert body["status"] == DataStatus.UNAVAILABLE.value
    assert "refused to connect" in (body["coverage_note"] or "")
    assert body["data_gaps"]


def test_health_facilities_reports_unavailable_when_nhm_is_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "NHM_API_BASE_URL", None)

    body = _get(client, "/api/v1/places/IN-OD-29/health-facilities")

    assert body["domain"] == "health"
    assert body["status"] == DataStatus.UNAVAILABLE.value
    assert "not configured" in (body["coverage_note"] or "")
    assert body["data_gaps"]


def test_health_facilities_serves_observations_when_upstream_succeeds(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)

    def succeed(self: NHMHealthAdapter, place_id: str, **kwargs: object) -> list[Observation]:
        return [
            Observation(
                field_name="primary_health_centres",
                value=6.0,
                unit="facilities",
                place_id=place_id,
                source_id="src-mohfw-nhm",
                domain="health",
                licence="GODL-India",
                quality_status=DataStatus.CURRENT,
                reference_period_end=now.date(),
                published_at=now,
                retrieved_at=now,
                notes="NHM Odisha Public Health Infrastructure Register.",
            )
        ]

    monkeypatch.setattr(NHMHealthAdapter, "fetch_observations", succeed)

    body = _get(client, "/api/v1/places/IN-OD-29/health-facilities")

    assert body["status"] == DataStatus.CURRENT.value
    assert body["observations"][0]["field_name"] == "primary_health_centres"


def test_undated_live_reading_is_never_reported_current(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Provenance must not be mistaken for a date.

    The route attaches the provider's registered URL after judging freshness.
    Swapping that order would let `describes_a_point_in_time` see a link and
    call a reading with no stated observation time current.
    """
    now = datetime.now(UTC)

    def undated(self: IMDWeatherAdapter, place_id: str, **kwargs: object) -> list[Observation]:
        return [
            Observation(
                field_name="surface_temperature_celsius",
                value=31.8,
                unit="°C",
                place_id=place_id,
                source_id="src-imd",
                domain="weather_disasters",
                licence="GODL-India",
                quality_status=DataStatus.CURRENT,
                retrieved_at=now,
                notes="IMD reading with no stated observation time.",
            )
        ]

    monkeypatch.setattr(IMDWeatherAdapter, "fetch_observations", undated)

    body = _get(client, "/api/v1/places/IN-OD-29/weather")

    assert body["observations"][0]["source_url"], "provenance is still attached"
    assert body["observations"][0]["quality_status"] == DataStatus.UNVERIFIED.value
    assert body["status"] == DataStatus.UNVERIFIED.value


@pytest.mark.parametrize("path", ["/weather", "/health-facilities"])
def test_provider_endpoints_reject_an_unknown_place(client: TestClient, path: str) -> None:
    response = client.get(f"/api/v1/places/does-not-exist{path}")
    assert response.status_code == 404
    # Must be *our* place check answering, not FastAPI's router missing the path.
    assert "Place not found" in response.json()["error"]["message"]
