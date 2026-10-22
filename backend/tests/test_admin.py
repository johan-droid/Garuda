"""Tests for administrative endpoints and dataset ingestion.

Covers:
  - Authentication and authorization boundaries (verify_admin_key)
  - Operational counters (/api/v1/admin/stats)
  - Batch history (/api/v1/admin/imports)
  - Atomic batch import and transactional rollback (/api/v1/admin/import)
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import PlaceModel


def test_admin_stats_requires_authentication(client: TestClient) -> None:
    """Unauthenticated requests to admin routes must be rejected with 401."""
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_admin_stats_rejects_invalid_key(client: TestClient) -> None:
    """Requests with an invalid bearer token must be rejected with 403."""
    response = client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": "Bearer completely-wrong-admin-key"},
    )
    assert response.status_code == 403


def test_admin_stats_succeeds_with_valid_key(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Authorized admin requests return operational statistics."""
    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "places" in body
    assert "observations" in body


def test_admin_imports_list(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Admin can query recent import batches."""
    response = client.get("/api/v1/admin/imports", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "batches" in body
    assert isinstance(body["batches"], list)


def test_admin_import_batch_atomic_success_and_rollback(
    client: TestClient, db: Session, admin_headers: dict[str, str]
) -> None:
    """Valid batch is imported atomically; invalid batch is rejected and rolled back."""
    # 1. Valid batch
    valid_batch = {
        "domain": "demographics",
        "imported_by": "test-admin",
        "source": {
            "id": "src-test-admin",
            "publisher": "Test Publisher",
            "name": "Test Census Data",
            "access_mode": "api",
            "verification_status": "verified",
        },
        "places": [
            {
                "id": "IN-TEST-01",
                "canonical_name": "Test Place One",
                "place_type": "district",
                "parent_id": None,
                "latitude": 20.0,
                "longitude": 85.0,
                "geometry_available": False,
                "aliases": ["Test Place Alias"],
            }
        ],
        "observations": [
            {
                "field_name": "total_population",
                "value": 100000.0,
                "unit": "persons",
                "place_id": "IN-TEST-01",
                "source_id": "src-test-admin",
                "domain": "demographics",
                "quality_status": "current",
            }
        ],
    }

    response = client.post(
        "/api/v1/admin/import", json=valid_batch, headers=admin_headers
    )
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "completed"
    assert res["places_written"] == 1
    assert res["observations_written"] == 1

    # Verify place exists in database
    place = db.get(PlaceModel, "IN-TEST-01")
    assert place is not None
    assert place.canonical_name == "Test Place One"

    # 2. Invalid batch (mismatched domain in observation)
    invalid_batch = {
        "domain": "demographics",
        "imported_by": "test-admin",
        "source": {
            "id": "src-test-admin-2",
            "publisher": "Test Publisher",
            "name": "Test Health Data",
            "access_mode": "api",
            "verification_status": "verified",
        },
        "places": [
            {
                "id": "IN-TEST-02",
                "canonical_name": "Test Place Two",
                "place_type": "district",
                "parent_id": None,
            }
        ],
        "observations": [
            {
                "field_name": "outbreak_status",
                "value": "active",
                "place_id": "IN-TEST-02",
                "source_id": "src-test-admin-2",
                "domain": "health",  # Domain mismatch against batch domain 'demographics'
                "quality_status": "current",
            }
        ],
    }

    bad_response = client.post(
        "/api/v1/admin/import", json=invalid_batch, headers=admin_headers
    )
    assert bad_response.status_code == 400

    # Ensure transaction rolled back and place IN-TEST-02 was NOT persisted
    unwritten_place = db.get(PlaceModel, "IN-TEST-02")
    assert unwritten_place is None
