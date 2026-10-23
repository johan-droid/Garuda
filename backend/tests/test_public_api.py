"""Public read API tests.

The public surface is unauthenticated by design: the data it exposes is
public information with published provenance. These tests pin down the
behaviour a client depends on:

  * a place with no data is reported as a gap, never as a set of zeros;
  * every observation carries its source, period, and freshness status;
  * only genuine official alerts appear in the alerts endpoint;
  * ETags allow conditional requests to be answered with `304`.
"""

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.common import DataStatus
from app.domain.contracts import Observation
from app.models.entities import ObservationModel, SourceModel
from app.services.freshness import determine_status
from tests.factories import seed_dataset


def test_search_finds_a_place_by_name(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get("/api/v1/places/search", params={"q": "odisha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["results"][0]["place"]["id"] == "IN-OD"
    assert body["results"][0]["match_type"] == "name"


def test_search_finds_a_place_by_alias(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get("/api/v1/places/search", params={"q": "orissa"})

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_empty_search_returns_an_empty_result_set_not_an_error(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/places/search", params={"q": ""})

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["total"] == 0


def test_search_rejects_an_unsupported_place_type(client: TestClient) -> None:
    response = client.get("/api/v1/places/search", params={"q": "x", "type": "planet"})

    assert response.status_code == 400


def test_profile_reports_data_gaps_instead_of_zeros(
    client: TestClient,
    db: Session,
) -> None:
    """A domain with no data must not look like a domain full of zeros."""
    seed_dataset(db)

    response = client.get("/api/v1/places/IN-OD/profile")

    assert response.status_code == 200
    panels = response.json()["panels"]
    services = panels["services"]
    assert services["status"] == "unavailable"
    assert services["observations"] == []
    assert services["data_gaps"], "an empty panel must explain the gap"


def test_undated_observation_is_never_current() -> None:
    """No reference period, no publication time, no source URL: not datable.

    Falling back to `retrieved_at` would make every freshly ingested value look
    current, which is how an undated fixture ends up on screen as an
    observation of the present.
    """
    undated = Observation(
        field_name="rainfall_daily_mm",
        value=4.6,
        unit="mm",
        place_id="IN-OD-29",
        source_id="src-imd",
        quality_status=DataStatus.CURRENT,
        retrieved_at=datetime.now(UTC),
    )
    assert determine_status(undated) == DataStatus.UNVERIFIED

    # A dated value is judged on that date, not on when it was ingested.
    dated = undated.model_copy(update={"reference_period_end": date.today()})
    assert determine_status(dated) == DataStatus.CURRENT

    old = undated.model_copy(update={"reference_period_end": date(2011, 2, 28)})
    assert determine_status(old) == DataStatus.STALE


def test_profile_returns_404_for_an_unknown_place(client: TestClient) -> None:
    response = client.get("/api/v1/places/does-not-exist/profile")

    assert response.status_code == 404


def test_location_responses_are_not_cacheable(client: TestClient, db: Session) -> None:
    """A response that answers a location query must not be stored by a cache."""
    seed_dataset(db)

    reverse = client.get("/api/v1/places/reverse", params={"lat": 20.2961, "lng": 85.8245})
    assert reverse.headers["cache-control"] == "no-store"

    profile = client.get("/api/v1/places/IN-OD/profile")
    assert profile.headers["cache-control"] == "no-store"


def test_profile_panels_carry_their_own_status(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    panels = client.get("/api/v1/places/IN-OD/profile").json()["panels"]

    assert set(panels) >= {"demographics", "health", "services"}
    for panel in panels.values():
        assert panel["status"]
        assert "error" in panel


def test_observations_carry_full_provenance(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get("/api/v1/places/IN-OD-29/observations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    observation = body["observations"][0]
    assert observation["source_id"] == "src-mohfw"
    assert observation["retrieved_at"]
    assert observation["quality_status"]
    assert observation["licence"] == "CC-BY-4.0"
    assert body["sources"], "the sources behind the observations must be listed"


def test_observations_can_be_filtered_by_domain(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    body = client.get(
        "/api/v1/places/IN-OD-29/observations", params={"domain": "demographics"}
    ).json()

    assert body["total"] == 0
    assert body["observations"] == []


def test_observations_reject_an_unknown_domain(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get(
        "/api/v1/places/IN-OD-29/observations", params={"domain": "astrology"}
    )

    assert response.status_code == 400


def test_observations_reject_an_inverted_period(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get(
        "/api/v1/places/IN-OD-29/observations",
        params={"period_start": "2026-01-01", "period_end": "2025-01-01"},
    )

    assert response.status_code == 400


def test_alerts_only_include_official_alerts(client: TestClient, db: Session) -> None:
    """Surveillance summaries are not alerts and must not be rendered as one."""
    seed_dataset(db)

    body = client.get("/api/v1/places/IN-OD-29/alerts").json()

    assert len(body["active_alerts"]) == 1
    alert = body["active_alerts"][0]
    assert alert["health_category"] == "official_alert"
    assert alert["issuing_authority"]
    assert alert["expired"] is False
    assert body["expired_count"] == 0


def test_expired_alerts_are_excluded_but_counted(client: TestClient, db: Session) -> None:
    seed_dataset(db)
    now = datetime.now(UTC)
    db.add(
        ObservationModel(
            field_name="measles_alert",
            value_text="Old alert",
            place_id="IN-OD-29",
            source_id="src-mohfw",
            domain="health",
            retrieved_at=now - timedelta(days=30),
            transformation_version="import-v1",
            quality_status="current",
            health_category="official_alert",
            issuing_authority="Directorate of Public Health, Odisha",
            affected_geography_level="district",
            valid_from=now - timedelta(days=30),
            valid_until=now - timedelta(days=1),
        )
    )
    db.commit()

    body = client.get("/api/v1/places/IN-OD-29/alerts").json()

    assert len(body["active_alerts"]) == 1
    assert body["expired_count"] == 1
    assert "measles_alert" not in {alert["field_name"] for alert in body["active_alerts"]}


def test_alerts_endpoint_reports_no_data_as_an_empty_list(
    client: TestClient,
    db: Session,
) -> None:
    seed_dataset(db)

    body = client.get("/api/v1/places/IN-OD/alerts").json()

    assert body["active_alerts"] == []
    assert body["expired_count"] == 0


def test_sources_register_is_public(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    source = body["sources"][0]
    assert source["id"] == "src-mohfw"
    assert source["licence"] == "CC-BY-4.0"
    assert source["verification_status"] == "verified"


def test_source_detail_returns_404_for_an_unknown_source(client: TestClient) -> None:
    response = client.get("/api/v1/sources/nope")

    assert response.status_code == 404


def test_cross_place_observations_can_be_filtered(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    body = client.get("/api/v1/observations", params={"domain": "health"}).json()

    assert body["total"] == 2
    assert body["filters"]["domain"] == "health"
    assert {observation["place_id"] for observation in body["observations"]} == {"IN-OD-29"}


def test_cross_place_observations_are_ordered_newest_first(
    client: TestClient,
    db: Session,
) -> None:
    seed_dataset(db)

    observations = client.get("/api/v1/observations").json()["observations"]
    retrieved = [observation["retrieved_at"] for observation in observations]

    assert retrieved == sorted(retrieved, reverse=True)


def test_etag_allows_a_304_response(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    first = client.get("/api/v1/places/search", params={"q": "odisha"})
    etag = first.headers["ETag"]
    assert etag

    second = client.get(
        "/api/v1/places/search",
        params={"q": "odisha"},
        headers={"If-None-Match": etag},
    )

    assert second.status_code == 304
    assert second.headers["ETag"] == etag
    assert second.content == b""


def test_etag_changes_when_the_data_changes(client: TestClient, db: Session) -> None:
    seed_dataset(db)

    first = client.get("/api/v1/sources")
    etag = first.headers["ETag"]

    db.add(
        SourceModel(
            id="src-census",
            publisher="Office of the Registrar General",
            name="Census of India",
            access_mode="bulk",
            verification_status="verified",
        )
    )
    db.commit()

    second = client.get("/api/v1/sources")

    assert second.headers["ETag"] != etag
    assert second.json()["total"] == 2
