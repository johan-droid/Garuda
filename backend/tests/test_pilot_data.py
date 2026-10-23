"""Tests for Project Garuda Khordha Pilot dataset and endpoints.

Covers:
  - Boundaries GeoJSON endpoint (/api/v1/places/boundaries)
  - Reverse geocoding endpoint (/api/v1/places/reverse)
  - Source diagnostics endpoint (/api/v1/sources/diagnostics)
  - Seeded observations across all required domains:
      * Demographics (Census 2011)
      * Health facilities (MoHFW/NHM) & surveillance (IDSP NCDC)
      * Health alerts (active & expired, WHO prevention link)
      * Services & Education (UDISE+, drinking water %, electrification %)
      * History & Culture (ASI heritage monuments, Chilika Ramsar)
      * Environment (ISRO Bhuvan forest cover %, water spread, AQI baseline)
      * Weather & Disasters (IMD observation, NDMA advisory)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from seed_pilot import seed_database


@pytest.fixture(autouse=True)
def _setup_pilot_data(db: Session) -> None:
    """Populate test database with full pilot dataset before each test."""
    seed_database(db)


# =============================================================================
# 1. BOUNDARIES ENDPOINT (/api/v1/places/boundaries)
# =============================================================================

def test_boundaries_returns_full_pilot_feature_collection(client: TestClient) -> None:
    response = client.get("/api/v1/places/boundaries")
    assert response.status_code == 200

    body = response.json()
    assert body["type"] == "FeatureCollection"
    features = body["features"]
    assert len(features) == 10

    feature_ids = {f["id"] for f in features}
    expected_ids = {
        "IN-OD",
        "IN-OD-29",
        "IN-OD-BBSR",
        "IN-OD-JAT",
        "IN-OD-KHD",
        "IN-OD-BEG",
        "IN-OD-BAN",
        "IN-OD-BOL",
        "IN-OD-CHI",
        "IN-OD-TAN",
    }
    assert feature_ids == expected_ids


def test_boundaries_filter_by_place_type(client: TestClient) -> None:
    response = client.get("/api/v1/places/boundaries", params={"place_type": "subdistrict"})
    assert response.status_code == 200

    features = response.json()["features"]
    assert len(features) == 8
    for f in features:
        assert f["properties"]["place_type"] == "subdistrict"
        assert f["properties"]["parent_id"] == "IN-OD-29"


def test_boundaries_filter_by_parent_id(client: TestClient) -> None:
    response = client.get("/api/v1/places/boundaries", params={"parent_id": "IN-OD-29"})
    assert response.status_code == 200

    features = response.json()["features"]
    assert len(features) == 8


def test_boundaries_have_valid_polygon_geometries(client: TestClient) -> None:
    response = client.get("/api/v1/places/boundaries")
    assert response.status_code == 200

    for feat in response.json()["features"]:
        geom = feat["geometry"]
        assert geom["type"] in ("Polygon", "MultiPolygon")
        coords = geom["coordinates"][0]
        # Polygon ring must be closed (first == last)
        assert coords[0] == coords[-1]
        assert len(coords) >= 4
        # Verify coordinates are [lng, lat] with realistic Odisha ranges
        for lng, lat in coords:
            assert 80.0 <= lng <= 89.0
            assert 17.0 <= lat <= 23.0


# =============================================================================
# 2. REVERSE GEOCODING ENDPOINT (/api/v1/places/reverse)
# =============================================================================

@pytest.mark.parametrize(
    ("lat", "lng", "expected_place_id", "expected_subdistrict"),
    [
        (20.2961, 85.8245, "IN-OD-BBSR", "Bhubaneswar"),
        (20.1633, 85.7067, "IN-OD-JAT", "Jatni"),
        (20.1800, 85.6150, "IN-OD-KHD", "Khordha Town"),
        (20.2100, 85.4600, "IN-OD-BEG", "Begunia"),
        (20.1800, 85.2800, "IN-OD-BOL", "Bolagarh"),
        (19.9200, 85.4000, "IN-OD-TAN", "Tangi"),
        (19.7800, 85.2500, "IN-OD-CHI", "Chilika"),
        (19.7800, 85.1000, "IN-OD-BAN", "Banapur"),
    ],
)
def test_reverse_geocode_enclosing_subdistricts(
    client: TestClient, lat: float, lng: float, expected_place_id: str, expected_subdistrict: str
) -> None:
    response = client.get("/api/v1/places/reverse", params={"lat": lat, "lng": lng})
    assert response.status_code == 200

    body = response.json()
    assert body["place"]["id"] == expected_place_id
    assert body["match_type"] == "enclosing"
    assert body["distance_km"] == 0.0
    assert body["hierarchy"]["state"] == "Odisha"
    assert body["hierarchy"]["district"] == "Khordha"
    assert body["hierarchy"]["subdistrict"] == expected_subdistrict
    # A pin inside a supported polygon must be marked as covered, with no
    # caveat attached.
    assert body["inside_coverage"] is True
    assert body["coverage_note"] is None


def test_reverse_geocode_resolves_district_when_outside_a_block(client: TestClient) -> None:
    # Inside the Khordha pilot district outline but outside every block polygon.
    response = client.get("/api/v1/places/reverse", params={"lat": 19.65, "lng": 85.15})
    assert response.status_code == 200

    body = response.json()
    assert body["place"]["id"] == "IN-OD-29"
    assert body["match_type"] == "enclosing"
    assert body["inside_coverage"] is True
    assert body["hierarchy"]["district"] == "Khordha"


def test_reverse_geocode_outside_all_polygons_falls_back_to_nearest(client: TestClient) -> None:
    # New Delhi coordinates - well outside Odisha
    response = client.get("/api/v1/places/reverse", params={"lat": 28.6139, "lng": 77.2090})
    assert response.status_code == 200

    body = response.json()
    assert body["match_type"] == "nearest"
    assert body["distance_km"] > 500.0  # At least 500 km away
    assert body["place"]["id"] is not None
    # The nearest boundary is a reference, not the unit containing the pin.
    assert body["inside_coverage"] is False
    assert body["coverage_note"]
    assert "outside" in body["coverage_note"].lower()
    assert "do not describe" in body["coverage_note"]


def test_reverse_geocode_validates_coordinate_bounds(client: TestClient) -> None:
    # Invalid latitude > 90
    response = client.get("/api/v1/places/reverse", params={"lat": 95.0, "lng": 85.0})
    assert response.status_code == 422

    # Invalid longitude < -180
    response = client.get("/api/v1/places/reverse", params={"lat": 20.0, "lng": -190.0})
    assert response.status_code == 422


# =============================================================================
# 3. SOURCE DIAGNOSTICS ENDPOINT (/api/v1/sources/diagnostics)
# =============================================================================

def test_source_diagnostics_reports_all_registered_sources(client: TestClient) -> None:
    response = client.get("/api/v1/sources/diagnostics")
    assert response.status_code == 200

    body = response.json()
    assert body["total_sources"] >= 7
    assert body["healthy_sources"] >= 7
    assert body["checked_at"] is not None

    source_ids = {s["source_id"] for s in body["sources"]}
    expected_sources = {
        "src-census-2011",
        "src-mohfw-nhm",
        "src-idsp-ncdc",
        "src-udise-plus",
        "src-asi",
        "src-imd",
        "src-isro-bhuvan",
    }
    assert expected_sources.issubset(source_ids)

    for src in body["sources"]:
        assert src["health"] == "healthy"
        assert src["records_served"] > 0
        assert src["ttl_seconds"] > 0
        assert src["last_fetch"] is not None
        assert src["error_status"] is None


def test_source_diagnostics_ttls_match_data_domain_policies(client: TestClient) -> None:
    response = client.get("/api/v1/sources/diagnostics")
    assert response.status_code == 200

    by_id = {s["source_id"]: s for s in response.json()["sources"]}
    # Census 2011 demographics: 1 day (86400s)
    assert by_id["src-census-2011"]["ttl_seconds"] == 86400
    # Outbreak surveillance: 5 minutes (300s)
    assert by_id["src-idsp-ncdc"]["ttl_seconds"] == 300
    # Facilities: 6 hours (21600s)
    assert by_id["src-mohfw-nhm"]["ttl_seconds"] == 21600
    assert by_id["src-udise-plus"]["ttl_seconds"] == 21600
    # Heritage: 7 days (604800s)
    assert by_id["src-asi"]["ttl_seconds"] == 604800


# =============================================================================
# 4. SEEDED OBSERVATIONS ACROSS ALL REQUIRED DOMAINS
# =============================================================================

def test_demographics_observations(client: TestClient) -> None:
    # Query Khordha District observations
    response = client.get("/api/v1/places/IN-OD-29/observations", params={"domain": "demographics"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    assert obs_map["total_population"]["value"] == 2251673.0
    assert obs_map["male_population"]["value"] == 1167114.0
    assert obs_map["female_population"]["value"] == 1084559.0
    assert obs_map["literacy_rate"]["value"] == 86.88
    assert obs_map["sex_ratio"]["value"] == 929.0
    assert obs_map["total_households"]["value"] == 493522.0

    for obs in obs_map.values():
        assert obs["quality_status"] == "historical"
        assert obs["source_id"] == "src-census-2011"


def test_health_facilities_and_surveillance(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-29/observations", params={"domain": "health"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    # NHM facilities
    assert obs_map["primary_health_centres"]["value"] == 34.0
    assert obs_map["community_health_centres"]["value"] == 10.0
    assert obs_map["sub_centres"]["value"] == 218.0
    assert obs_map["district_hospitals"]["value"] == 2.0

    # IDSP surveillance
    assert obs_map["dengue_cases"]["value"] == 142.0
    assert obs_map["cholera_cases"]["value"] == 18.0


def test_health_alerts_active_and_expired(client: TestClient) -> None:
    # 1. Active alerts only (default)
    response = client.get("/api/v1/places/IN-OD-29/alerts")
    assert response.status_code == 200
    body = response.json()

    active_alerts = body["active_alerts"]
    assert len(active_alerts) == 1
    alert = active_alerts[0]
    assert alert["field_name"] == "cholera_water_safety_alert"
    assert alert["issuing_authority"] == "Directorate of Public Health, Government of Odisha"
    assert alert["severity"] == "high"
    assert alert["prevention_link"] == "https://www.who.int/news-room/fact-sheets/detail/cholera"
    assert alert["expired"] is False
    assert body["expired_count"] == 1

    # 2. Include expired alerts
    response_with_expired = client.get("/api/v1/places/IN-OD-29/alerts", params={"include_expired": True})
    assert response_with_expired.status_code == 200
    all_alerts = response_with_expired.json()["active_alerts"]
    assert len(all_alerts) == 2

    expired_alert = next(a for a in all_alerts if a["field_name"] == "pre_monsoon_diarrhea_advisory")
    assert expired_alert["expired"] is True
    assert expired_alert["issuing_authority"] == "District Surveillance Unit, Khordha"
    assert expired_alert["prevention_link"] == "https://www.who.int/emergencies/disease-outbreak-news"


def test_services_and_education_observations(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-29/observations", params={"domain": "services"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    assert obs_map["schools_total"]["value"] == 2185.0
    assert obs_map["schools_primary"]["value"] == 1412.0
    assert obs_map["schools_secondary"]["value"] == 532.0
    assert obs_map["drinking_water_access_pct"]["value"] == 94.6
    assert obs_map["electrification_pct"]["value"] == 98.2


def test_history_and_culture_observations(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-BBSR/observations", params={"domain": "history_culture"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    assert "Lingaraj Temple" in obs_map["heritage_site_lingaraj"]["value"]
    assert "Udayagiri and Khandagiri" in obs_map["heritage_site_khandagiri_udayagiri"]["value"]
    assert "Dhauli Shanti Stupa" in obs_map["heritage_site_dhauli"]["value"]

    # Chilika wetland heritage
    res_chi = client.get("/api/v1/places/IN-OD-CHI/observations", params={"domain": "history_culture"})
    assert res_chi.status_code == 200
    chi_obs = {o["field_name"]: o for o in res_chi.json()["observations"]}
    assert "Ramsar Wetland" in chi_obs["heritage_site_chilika_ramsar"]["value"]


def test_environment_observations(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-29/observations", params={"domain": "environment"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    assert obs_map["forest_cover_pct"]["value"] == 21.84
    assert obs_map["chilika_water_spread_area_sq_km"]["value"] == 1165.0
    assert obs_map["air_quality_index_baseline"]["value"] == 64.0


def test_weather_and_disasters_observations(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-29/observations", params={"domain": "weather_disasters"})
    assert response.status_code == 200

    obs_map = {o["field_name"]: o for o in response.json()["observations"]}
    assert obs_map["surface_temperature_celsius"]["value"] == 31.8
    assert obs_map["rainfall_daily_mm"]["value"] == 4.6
    assert "NDMA / OSDMA Coastal Advisory" in obs_map["cyclone_preparedness_advisory"]["value"]


def test_place_profile_includes_populated_panels(client: TestClient) -> None:
    response = client.get("/api/v1/places/IN-OD-29/profile")
    assert response.status_code == 200

    panels = response.json()["panels"]
    # Census 2011 is reference-dated, so its figures are historical - not current.
    assert panels["demographics"]["status"] == "historical"
    assert len(panels["demographics"]["observations"]) > 0

    assert panels["health"]["status"] == "unverified"
    assert len(panels["health"]["observations"]) > 0

    # These panels are populated by undated pilot fixtures. An undated value is
    # never `current`, however recently it was ingested.
    for domain in ("services", "environment", "history_culture", "weather_disasters"):
        assert panels[domain]["status"] == "unverified", domain
        assert len(panels[domain]["observations"]) > 0, domain

    assert all(panel["status"] != "current" for panel in panels.values())
