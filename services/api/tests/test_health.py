"""Health probe tests.

The distinction the probes encode:

  * liveness answers "is the process running?" and must not depend on the
    database, so a database outage never causes a restart loop.
  * readiness answers "can this instance serve data?" and must fail when the
    database is unreachable.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_liveness_never_touches_the_database(client: TestClient) -> None:
    """The liveness probe stays green while the database is down."""
    with patch("app.api.routes.health.healthcheck", return_value=False):
        response = client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "alive"
    assert "database" not in body


def test_readiness_reports_ready_when_the_database_answers(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"]["ok"] is True


def test_readiness_returns_503_when_the_database_is_down(client: TestClient) -> None:
    with patch("app.api.routes.health.healthcheck", return_value=False):
        response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"]["ok"] is False


def test_health_snapshot_reports_degraded_when_the_database_is_down(
    client: TestClient,
) -> None:
    with patch("app.api.routes.health.healthcheck", return_value=False):
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["ok"] is False


def test_health_responses_are_never_mistaken_for_public_health_data(
    client: TestClient,
) -> None:
    """Every probe carries the note that disambiguates it from health data."""
    for path in ("/health", "/health/live", "/health/ready"):
        body = client.get(path).json()
        assert body["note"] == "This is application health, not public-health data."


def test_health_probes_are_exempt_from_rate_limiting(client: TestClient) -> None:
    """Probes stay reachable under load."""
    with patch("app.core.ratelimit.settings.RATE_LIMIT_ENABLED", True):
        for _ in range(30):
            assert client.get("/health/live").status_code == 200


def test_health_probes_live_at_the_root_not_under_the_version_prefix(
    client: TestClient,
) -> None:
    """An orchestrator must not have to know the API version."""
    assert client.get("/health/live").status_code == 200
    assert client.get("/api/v1/health/live").status_code == 404


def test_openapi_documents_the_versioned_routes() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/places/search" in paths
    assert "/api/v1/sources" in paths
    assert "/api/v1/admin/import" in paths
    assert "/health/ready" in paths
