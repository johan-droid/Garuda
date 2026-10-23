"""Tests for environment scenes endpoint and EarthSearchSentinelAdapter."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.common import DOMAIN_ENVIRONMENT
from app.domain.contracts import GetLatestObservationStatus
from app.services.provider_adapters import (
    EarthSearchSentinelAdapter,
    ProviderUnavailableError,
)
from tests.factories import seed_dataset

SAMPLE_STAC_SCENE = {
    "id": "S2B_45QUC_20260205_0_L2A",
    "href": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2B_45QUC_20260205_0_L2A",
    "bbox": [85.0, 19.5, 86.5, 20.8],
    "properties": {
        "datetime": "2026-02-05T05:02:58Z",
        "eo:cloud_cover": 0.29,
    },
}

OLDER_STAC_SCENE = {
    "id": "S2A_45QUC_20260115_0_L2A",
    "href": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/S2A_45QUC_20260115_0_L2A",
    "bbox": [85.0, 19.5, 86.5, 20.8],
    "properties": {
        "datetime": "2026-01-15T05:00:00Z",
        "eo:cloud_cover": 0.10,
    },
}


def test_environment_scenes_returns_404_for_unknown_place(client: TestClient, db: Session) -> None:
    """Unknown place ID returns 404."""
    seed_dataset(db)
    response = client.get("/api/v1/places/NONEXISTENT-PLACE-ID/environment-scenes")
    assert response.status_code == 404
    assert "not found" in response.json()["error"]["message"].lower()


def test_environment_scenes_success_with_mocked_stac(client: TestClient, db: Session) -> None:
    """When STAC returns scenes covering the place, returns the latest scene metadata."""
    seed_dataset(db)
    stac_payload = {"features": [SAMPLE_STAC_SCENE]}

    def mock_fetch(url: str, **kwargs: object) -> dict:
        return stac_payload

    with patch.object(EarthSearchSentinelAdapter, "_fetch_json", side_effect=mock_fetch):
        response = client.get("/api/v1/places/IN-OD-29/environment-scenes")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()
    assert data["field_name"] == "latest_sentinel2_scene"
    assert data["status"] == GetLatestObservationStatus.CURRENT.value
    assert data["observation"] is not None
    obs = data["observation"]
    assert obs["value"] == "S2B_45QUC_20260205_0_L2A"
    assert obs["domain"] == DOMAIN_ENVIRONMENT
    assert obs["satellite_mission"] == "Sentinel-2 (ESA/Copernicus)"
    assert obs["resolution_meters"] == 10.0
    assert obs["cloud_cover_percentage"] == 0.29
    assert obs["scene_timestamp"] == "2026-02-05T05:02:58+00:00"
    assert "Sentinel data (Copernicus/ESA) reproduced with attribution." in obs["notes"]


def test_environment_scenes_picks_latest_scene_over_older_scene() -> None:
    """Adapter prioritizes newer acquisition datetime."""
    adapter = EarthSearchSentinelAdapter()
    # OLDER_STAC_SCENE has lower cloud cover (0.10 vs 0.29) but is older
    scenes = [OLDER_STAC_SCENE, SAMPLE_STAC_SCENE]
    observations = adapter._best_observation(scenes, 85.5, 20.0, 85.7, 20.2)
    assert len(observations) == 1
    assert observations[0].value == "S2B_45QUC_20260205_0_L2A"


def test_environment_scenes_empty_when_no_scene_covers_bbox(client: TestClient, db: Session) -> None:
    """When no scenes cover the bounding box, returns UNAVAILABLE status without failing."""
    seed_dataset(db)
    stac_payload = {"features": []}

    with patch.object(EarthSearchSentinelAdapter, "_fetch_json", return_value=stac_payload):
        response = client.get("/api/v1/places/IN-OD-29/environment-scenes")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()
    assert data["status"] == GetLatestObservationStatus.UNAVAILABLE.value
    assert data["observation"] is None
    assert "No Sentinel-2" in (data["unavailable_reason"] or "")
    assert "no_sentinel_scene" in data["data_gaps"]


def test_environment_scenes_handles_upstream_failure_gracefully(client: TestClient, db: Session) -> None:
    """When raise_on_error is False (default), provider failure returns UNAVAILABLE."""
    seed_dataset(db)
    with patch.object(
        EarthSearchSentinelAdapter,
        "fetch_observations_for_bbox",
        side_effect=ProviderUnavailableError("Connection refused by upstream STAC"),
    ):
        response = client.get("/api/v1/places/IN-OD-29/environment-scenes")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == GetLatestObservationStatus.UNAVAILABLE.value
    assert "Connection refused" in (data["unavailable_reason"] or "")


def test_environment_scenes_propagates_error_when_configured(client: TestClient, db: Session) -> None:
    """When raise_on_error is True, provider failure propagates."""
    seed_dataset(db)
    with patch.object(
        EarthSearchSentinelAdapter,
        "fetch_observations_for_bbox",
        side_effect=ProviderUnavailableError("Connection refused by upstream STAC"),
    ):
        with pytest.raises(ProviderUnavailableError):
            client.get("/api/v1/places/IN-OD-29/environment-scenes?raise_on_error=true")
