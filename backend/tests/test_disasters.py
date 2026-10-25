"""Disaster records: the forecast / alert / observation distinction.

Three kinds of statement travel through the same panel, and they must not be
judged by the same rule:

  * An **observation** is a measurement, and is judged on its own date.
  * A **forecast** is a projection. However recently it was issued, it is not
    a measurement of the present, so it must never be labelled `current`.
  * An **alert** carries a validity window, and past `valid_until` it is
    expired - which is `unavailable`, not a stale advisory still in force.

These tests pin all three, plus the route that serves them and the NDMA
adapter that produces them.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.common import DataStatus, DOMAIN_WEATHER_DISASTERS
from app.domain.contracts import DisasterObservation, Observation, RecordType
from app.services.freshness import determine_status, summarize_domain

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def _observation(**kwargs) -> Observation:
    base = {
        "field_name": "rainfall_daily_mm",
        "value": 12.5,
        "place_id": "IN-OD-29",
        "source_id": "src-imd",
        "domain": DOMAIN_WEATHER_DISASTERS,
        "quality_status": DataStatus.CURRENT,
        "retrieved_at": NOW,
    }
    base.update(kwargs)
    return Observation(**base)


def _disaster(**kwargs) -> DisasterObservation:
    base = {
        "field_name": "cyclone_warning",
        "value": "Cyclone warning: preparatory action advised",
        "place_id": "IN-OD-29",
        "source_id": "src-ndma",
        "domain": DOMAIN_WEATHER_DISASTERS,
        "quality_status": DataStatus.CURRENT,
        "retrieved_at": NOW,
        "record_type": RecordType.ALERT,
        "issuing_authority": "National Disaster Management Authority (NDMA)",
        "severity": "orange",
        "affected_geography_level": "district",
    }
    base.update(kwargs)
    return DisasterObservation(**base)


class TestForecastIsNeverCurrent:
    def test_a_fresh_forecast_is_not_labelled_current(self) -> None:
        """A forecast issued a minute ago is still not a measurement of now."""
        forecast = _disaster(
            field_name="flood_forecast",
            record_type=RecordType.FORECAST,
            published_at=NOW - timedelta(minutes=1),
        )

        assert determine_status(forecast, NOW) == DataStatus.FORECAST

    def test_a_forecast_with_no_dates_is_still_not_current(self) -> None:
        """Even undated, a forecast must not fall through to unverified-as-current."""
        forecast = _disaster(
            field_name="flood_forecast",
            record_type=RecordType.FORECAST,
            published_at=None,
        )

        assert determine_status(forecast, NOW) == DataStatus.FORECAST

    def test_a_forecast_is_never_reported_as_current_by_the_panel_summary(self) -> None:
        """A panel made only of forecasts must not badge as current."""
        forecast = _disaster(
            field_name="flood_forecast",
            record_type=RecordType.FORECAST,
            published_at=NOW - timedelta(hours=2),
        )

        summary = summarize_domain(DOMAIN_WEATHER_DISASTERS, [forecast], [], NOW)

        assert summary.status != DataStatus.CURRENT
        assert summary.status == DataStatus.FORECAST

    def test_a_stored_forecast_status_is_authoritative(self) -> None:
        """A forecast stored as FORECAST stays FORECAST rather than being recomputed."""
        forecast = _disaster(
            field_name="flood_forecast",
            record_type=RecordType.FORECAST,
            quality_status=DataStatus.FORECAST,
        )

        assert determine_status(forecast, NOW) == DataStatus.FORECAST


class TestAlertExpiry:
    def test_an_alert_inside_its_window_is_judged_on_its_dates(self) -> None:
        """A bulletin always carries an issue time, so it is dated and current."""
        alert = _disaster(
            valid_from=NOW - timedelta(hours=6),
            valid_until=NOW + timedelta(hours=18),
            published_at=NOW - timedelta(hours=6),
        )

        assert determine_status(alert, NOW) == DataStatus.CURRENT

    def test_an_in_window_alert_with_no_issue_time_is_unverified(self) -> None:
        """A window says when it applies, not when it was issued.

        The shared rule is that a value with no reference period and no
        publication time is undated, and an undated value is never current.
        That rule is deliberately left alone here - an advisory with a window
        but no issue time is reported unverified rather than guessed current.
        """
        alert = _disaster(
            valid_from=NOW - timedelta(hours=6),
            valid_until=NOW + timedelta(hours=18),
            published_at=None,
        )

        assert determine_status(alert, NOW) == DataStatus.UNVERIFIED

    def test_an_alert_past_valid_until_is_unavailable(self) -> None:
        """An expired advisory is not an advisory still in force."""
        alert = _disaster(
            valid_from=NOW - timedelta(days=4),
            valid_until=NOW - timedelta(days=1),
            published_at=NOW - timedelta(days=4),
        )

        assert determine_status(alert, NOW) == DataStatus.UNAVAILABLE

    def test_an_expired_alert_is_never_current(self) -> None:
        """Expiry must win over a fresh issue time."""
        alert = _disaster(
            valid_until=NOW - timedelta(minutes=1),
            published_at=NOW - timedelta(minutes=1),
        )

        assert determine_status(alert, NOW) == DataStatus.UNAVAILABLE

    def test_an_alert_without_a_window_is_judged_like_an_observation(self) -> None:
        """No window means no expiry rule; the ordinary freshness rule applies."""
        alert = _disaster(valid_from=None, valid_until=None)

        assert determine_status(alert, NOW) == DataStatus.UNVERIFIED

    def test_an_alert_can_report_its_own_expiry(self) -> None:
        """The contract carries the window, so a caller can ask directly."""
        live = _disaster(valid_until=NOW + timedelta(hours=6))
        expired = _disaster(valid_until=NOW - timedelta(hours=6))

        assert live.is_expired(NOW) is False
        assert expired.is_expired(NOW) is True
        assert live.valid_until is not None and expired.valid_until is not None

    def test_a_naive_valid_until_is_treated_as_utc(self) -> None:
        """A naive timestamp must not raise when compared to an aware one."""
        alert = _disaster(valid_until=datetime(2026, 10, 20, 12, 0))

        assert determine_status(alert, NOW) == DataStatus.UNAVAILABLE


class TestObservationIsJudgedOnItsOwnDate:
    def test_a_recent_observation_is_current(self) -> None:
        assert determine_status(_observation(published_at=NOW - timedelta(days=1)), NOW) == DataStatus.CURRENT

    def test_an_old_observation_is_stale(self) -> None:
        old = _observation(published_at=NOW - timedelta(days=30))

        assert determine_status(old, NOW) == DataStatus.STALE

    def test_an_undated_observation_is_unverified(self) -> None:
        """No period and no link means the age is unknowable."""
        assert determine_status(_observation(published_at=None), NOW) == DataStatus.UNVERIFIED

    def test_the_record_type_defaults_to_observation(self) -> None:
        """An ordinary observation carries no special rule."""
        assert _observation().record_type == RecordType.OBSERVATION


class TestNdmaAdapter:
    def _adapter(self, base_url=None):
        from app.services.ndma_adapter import NDMADisasterAdapter

        return NDMADisasterAdapter(base_url=base_url)

    def test_unconfigured_adapter_reports_unavailable_and_does_not_raise(self) -> None:
        """No base URL means no outbound call, and never a server error."""
        adapter = self._adapter(base_url=None)

        observations = adapter.fetch_observations("IN-OD-29")

        assert observations
        assert all(o.quality_status == DataStatus.UNAVAILABLE for o in observations)

    def test_failed_upstream_degrades_to_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = self._adapter(base_url="https://ndma.example.gov.in")

        def boom(_url):
            raise RuntimeError("upstream down")

        monkeypatch.setattr(adapter, "_fetch_json", boom)

        observations = adapter.fetch_observations("IN-OD-29")

        assert observations
        assert all(o.quality_status == DataStatus.UNAVAILABLE for o in observations)
        # The reason travels with the record rather than being swallowed.
        assert "upstream down" in (observations[0].notes or "")

    def test_parsed_payload_carries_its_record_type_and_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter = self._adapter(base_url="https://ndma.example.gov.in")
        payload = {
            "records": [
                {
                    "field_name": "cyclone_warning",
                    "value": "Pre-cyclone watch for the Odisha coast",
                    "record_type": "alert",
                    "issuing_authority": "NDMA",
                    "severity": "orange",
                    "valid_from": "2026-10-25T00:00:00+00:00",
                    "valid_until": "2026-10-26T18:00:00+00:00",
                },
                {
                    "field_name": "flood_forecast",
                    "value": "River discharge expected to rise",
                    "record_type": "forecast",
                },
            ]
        }
        monkeypatch.setattr(adapter, "_fetch_json", lambda _url: payload)

        observations = adapter.fetch_observations("IN-OD-29")

        by_field = {o.field_name: o for o in observations}
        assert by_field["cyclone_warning"].record_type == RecordType.ALERT
        assert by_field["cyclone_warning"].valid_until is not None
        assert by_field["flood_forecast"].record_type == RecordType.FORECAST

    def test_the_adapter_names_its_source(self) -> None:
        sources = self._adapter(base_url="https://ndma.example.gov.in").fetch_sources()

        assert sources
        assert sources[0].publisher
        assert sources[0].url


class TestDisastersRoute:
    PATH = "/api/v1/places/IN-OD-29/disasters"

    @pytest.fixture(autouse=True)
    def _seed_place(self, db):
        from app.models.entities import PlaceModel, SourceModel

        db.add(SourceModel(id="src-ndma", publisher="NDMA", name="NDMA Bulletins", url="https://ndma.gov.in"))
        db.add(
            PlaceModel(
                id="IN-OD-29",
                canonical_name="Khordha",
                place_type="district",
                geometry_available=True,
                search_text="khordha",
            )
        )
        db.commit()

    def test_unknown_place_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/places/IN-NOPE/disasters").status_code == 404

    def test_unconfigured_upstream_is_an_explained_unavailable_not_a_500(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The route must answer honestly when NDMA is not configured."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "NDMA_API_BASE_URL", None)

        response = client.get(self.PATH)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unavailable"
        # The absence is explained, not silent.
        assert body["coverage_note"] or body["data_gaps"]

    def test_the_route_reports_a_forecast_as_a_forecast(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A forecast reaching the API must not come back as current."""
        from app.api.routes import disasters as disasters_route
        from app.services import ndma_adapter

        adapter = ndma_adapter.NDMADisasterAdapter(base_url="https://ndma.example.gov.in")
        monkeypatch.setattr(
            adapter,
            "_fetch_json",
            lambda _url: {
                "records": [
                    {
                        "field_name": "flood_forecast",
                        "value": "River discharge expected to rise",
                        "record_type": "forecast",
                        "published_at": "2026-10-25T11:59:00+00:00",
                    }
                ]
            },
        )
        # Patch where the route looks the class up, not where it is defined.
        monkeypatch.setattr(disasters_route, "NDMADisasterAdapter", lambda *a, **k: adapter)

        body = client.get(self.PATH).json()

        assert body["status"] != "current"
        assert body["observations"][0]["record_type"] == "forecast"

    def test_the_route_reports_an_expired_alert_as_unavailable(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.routes import disasters as disasters_route
        from app.services import ndma_adapter

        adapter = ndma_adapter.NDMADisasterAdapter(base_url="https://ndma.example.gov.in")
        monkeypatch.setattr(
            adapter,
            "_fetch_json",
            lambda _url: {
                "records": [
                    {
                        "field_name": "cyclone_warning",
                        "value": "Pre-cyclone watch",
                        "record_type": "alert",
                        "issuing_authority": "NDMA",
                        "valid_until": "2020-01-01T00:00:00+00:00",
                    }
                ]
            },
        )
        monkeypatch.setattr(disasters_route, "NDMADisasterAdapter", lambda *a, **k: adapter)

        body = client.get(self.PATH).json()

        assert body["status"] == "unavailable"
