"""Verification tests for BE-TASK-07, BE-TASK-08, and BE-TASK-09."""

import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.entities import ObservationModel
from app.services.cache import CATEGORY_TTL_SECONDS, DEFAULT_TTL_SECONDS, ttl_for
from app.services.observation_service import list_observations
from tests.factories import seed_dataset
from tools.list_routes import get_routes, main as list_routes_main


def test_task_07_cache_ttl_entries() -> None:
    """BE-TASK-07: Ensure history_culture and weather_disasters have domain-specific TTLs."""
    assert "history_culture" in CATEGORY_TTL_SECONDS
    assert "weather_disasters" in CATEGORY_TTL_SECONDS

    assert CATEGORY_TTL_SECONDS["history_culture"] == 86_400
    assert CATEGORY_TTL_SECONDS["weather_disasters"] == 1_800

    assert ttl_for("history_culture") == 86_400
    assert ttl_for("weather_disasters") == 1_800
    assert ttl_for("unknown_domain") == DEFAULT_TTL_SECONDS == 60


def test_task_08_pagination_total_count_without_stale(db: Session, client: TestClient) -> None:
    """BE-TASK-08: Ensure total count and pagination reflect non-stale observations when include_stale=False."""
    seed_dataset(db)
    now = datetime.now(UTC)

    # In seed_dataset, IN-OD-29 has 2 health observations (dengue_cases - 2d old, cholera_alert - 1d old),
    # which are within the 7-day threshold (DataStatus.CURRENT).
    # Add a stale health observation (retrieved 20 days ago, threshold is 7 days).
    stale_obs = ObservationModel(
        field_name="malaria_cases",
        value_numeric=42.0,
        unit="cases",
        place_id="IN-OD-29",
        source_id="src-mohfw",
        domain="health",
        source_url="https://example.invalid/mohfw/malaria",
        publisher="Ministry of Health & Family Welfare",
        retrieved_at=now - timedelta(days=20),
        licence="CC-BY-4.0",
        transformation_version="import-v1",
        quality_status="current",
    )
    db.add(stale_obs)
    db.commit()

    # 1. When include_stale=True, all 3 observations are counted
    items_stale, total_stale = list_observations(db, "IN-OD-29", domain="health", include_stale=True)
    assert total_stale == 3
    assert len(items_stale) == 3

    # 2. When include_stale=False, total count reflects non-stale only (2)
    items_no_stale, total_no_stale = list_observations(db, "IN-OD-29", domain="health", include_stale=False)
    assert total_no_stale == 2
    assert len(items_no_stale) == 2
    assert all(obs.field_name != "malaria_cases" for obs in items_no_stale)

    # 3. Pagination with limit=1, offset=0
    page1, total_p1 = list_observations(
        db, "IN-OD-29", domain="health", limit=1, offset=0, include_stale=False
    )
    assert total_p1 == 2
    assert len(page1) == 1

    # 4. Pagination with limit=1, offset=1
    page2, total_p2 = list_observations(
        db, "IN-OD-29", domain="health", limit=1, offset=1, include_stale=False
    )
    assert total_p2 == 2
    assert len(page2) == 1
    assert page1[0].field_name != page2[0].field_name

    # 5. Verify through the REST endpoint
    res_with_stale = client.get(
        "/api/v1/places/IN-OD-29/observations",
        params={"domain": "health", "include_stale": "true"},
    )
    assert res_with_stale.status_code == 200
    assert res_with_stale.json()["total"] == 3
    assert len(res_with_stale.json()["observations"]) == 3

    res_no_stale = client.get(
        "/api/v1/places/IN-OD-29/observations",
        params={"domain": "health", "include_stale": "false"},
    )
    assert res_no_stale.status_code == 200
    assert res_no_stale.json()["total"] == 2
    assert len(res_no_stale.json()["observations"]) == 2


def test_task_09_list_routes(capsys: pytest.CaptureFixture[str]) -> None:
    """BE-TASK-09: Ensure list_routes outputs all 22 registered API endpoints."""
    routes = get_routes()
    assert len(routes) == 22

    paths = [path for _, path in routes]

    # Places routes (10: search/profile/boundaries/reverse, environment-scenes,
    # live IMD weather, live NHM health-facilities)
    places_routes = [p for p in paths if p.startswith("/api/v1/places")]
    assert len(places_routes) == 10

    # Observations routes (3)
    obs_routes = [p for p in paths if p.startswith("/api/v1/observations")]
    assert len(obs_routes) == 3

    # Sources routes (3)
    sources_routes = [p for p in paths if p.startswith("/api/v1/sources")]
    assert len(sources_routes) == 3

    # Admin routes (3)
    admin_routes = [p for p in paths if p.startswith("/api/v1/admin")]
    assert len(admin_routes) == 3

    # Health routes (3)
    health_routes = [p for p in paths if p.startswith("/health")]
    assert len(health_routes) == 3

    # Test running main() function
    list_routes_main()
    captured = capsys.readouterr()
    output_lines = [line.strip() for line in captured.out.strip().splitlines() if line.strip()]
    assert len(output_lines) == 22

    # Test running as module: python3 -m tools.list_routes
    backend_dir = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "tools.list_routes"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    module_lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
    assert len(module_lines) == 22
