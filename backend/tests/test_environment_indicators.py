"""Satellite indicators: NDVI and water extent, with explicit scene metadata.

Only scene *metadata* was served before this, so a reader could see when an
image was taken but not what it showed. These tests pin the two indicators the
pilot needs and, more importantly, that neither is ever reported without the
scene it came from.

The honesty constraints under test:

  * An indicator is meaningless without its scene. Every record carries the
    acquisition date, resolution and cloud cover, so a figure can never be
    shown as though it were current for the area.
  * No scene covering the area is an `unavailable` with a reason, not a zero.
  * Band pixels that cannot be read are an `unavailable` naming the missing
    capability - never a guessed or default value.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.domain.common import DataStatus
from app.domain.contracts import RecordType
from app.services import indicators as indicators_module

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)

SCENE = {
    "scene_id": "S2B_45QUC_20260205_0_L2A",
    "datetime": "2026-02-05T05:02:58Z",
    "cloud_cover": 12.5,
    "resolution_meters": 10.0,
    "source_url": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/x",
    "satellite_mission": "Sentinel-2 (ESA/Copernicus)",
    "assets": {
        "red": "https://example.invalid/B04.tif",
        "nir": "https://example.invalid/B08.tif",
        "green": "https://example.invalid/B03.tif",
    },
}


class TestNdviMath:
    def test_ndvi_is_the_normalised_difference_of_nir_and_red(self) -> None:
        # NIR reflects strongly over vegetation, red is absorbed, so a healthy
        # canopy sits near +0.8. Hand-derived: (0.8 - 0.1) / (0.8 + 0.1).
        assert indicators_module.ndvi_value(nir=0.8, red=0.1) == pytest.approx(0.7778, abs=1e-4)

    def test_bare_soil_sits_near_zero(self) -> None:
        assert indicators_module.ndvi_value(nir=0.2, red=0.2) == pytest.approx(0.0, abs=1e-9)

    def test_water_is_negative(self) -> None:
        # Water absorbs NIR, so NIR < red and the index goes negative.
        assert indicators_module.ndvi_value(nir=0.05, red=0.1) == pytest.approx(-0.3333, abs=1e-4)

    def test_a_zero_denominator_is_none_not_an_exception(self) -> None:
        """Both bands zero is undefined; it must not raise and must not read as 0."""
        assert indicators_module.ndvi_value(nir=0.0, red=0.0) is None

    def test_a_missing_band_is_none(self) -> None:
        assert indicators_module.ndvi_value(nir=None, red=0.1) is None


class TestWaterExtentMath:
    def test_ndwi_is_the_normalised_difference_of_green_and_nir(self) -> None:
        # Open water: green reflects, NIR is absorbed. (0.3 - 0.02) / (0.3 + 0.02).
        assert indicators_module.ndwi_value(green=0.3, nir=0.02) == pytest.approx(0.875, abs=1e-4)

    def test_vegetation_is_negative_for_water_extent(self) -> None:
        assert indicators_module.ndwi_value(green=0.1, nir=0.8) == pytest.approx(-0.7778, abs=1e-4)

    def test_a_zero_denominator_is_none(self) -> None:
        assert indicators_module.ndwi_value(green=0.0, nir=0.0) is None


class TestIndicatorSpecs:
    def test_each_indicator_names_the_bands_it_uses(self) -> None:
        """A reader must be able to see which bands feed which figure."""
        by_field = {s.field_name: s for s in indicators_module.INDICATOR_SPECS}

        assert by_field["ndvi"].bands == ["B08", "B04"]
        assert by_field["water_extent"].bands == ["B03", "B08"]

    def test_each_indicator_states_its_formula(self) -> None:
        by_field = {s.field_name: s for s in indicators_module.INDICATOR_SPECS}
        assert "B08" in by_field["ndvi"].formula and "B04" in by_field["ndvi"].formula

    def test_the_specs_are_sentinel2_records(self) -> None:
        """The indicators are derived, not measured - they must say so."""
        for spec in indicators_module.INDICATOR_SPECS:
            assert spec.record_type == RecordType.OBSERVATION
            assert spec.mission


class TestComputeIndicators:
    def test_a_readable_scene_yields_a_value_per_indicator(self) -> None:
        # The reader is given the band name, because a COG filename does not
        # reliably identify which band it holds.
        values = {"B08": 0.8, "B04": 0.1, "B03": 0.3}

        def reader(href: str, band: str):
            return values[band]

        results = indicators_module.compute_indicators(SCENE, reader=reader)

        assert len(results) == 2
        assert all(r.status == DataStatus.CURRENT for r in results)
        assert all(r.value is not None for r in results)
        by_field = {r.field_name: r.value for r in results}
        assert by_field["ndvi"] == pytest.approx(0.7778, abs=1e-4)
        # NDWI = (green - nir) / (green + nir) = (0.3 - 0.8) / 1.1
        assert by_field["water_extent"] == pytest.approx(-0.4545, abs=1e-4)

    def test_every_indicator_carries_its_scene_metadata(self) -> None:
        """A figure with no scene behind it is not a figure this system serves."""

        def reader(href: str, band: str):
            return 0.5

        results = indicators_module.compute_indicators(SCENE, reader=reader)

        for result in results:
            assert result.scene is not None
            assert result.scene.acquisition_date is not None
            assert result.scene.resolution_meters == 10.0
            assert result.scene.cloud_cover_percentage == 12.5
            assert result.scene.scene_id == SCENE["scene_id"]

    def test_unreadable_bands_are_an_explained_unavailable(self) -> None:
        """No reader means no pixels; that is stated, not papered over."""
        results = indicators_module.compute_indicators(SCENE, reader=None)

        assert results
        assert all(r.status == DataStatus.UNAVAILABLE for r in results)
        assert all(r.value is None for r in results)
        assert all(r.unavailable_reason for r in results)

    def test_a_reader_that_fails_is_an_explained_unavailable(self) -> None:
        def reader(href: str, band: str):
            raise OSError("COG not readable")

        results = indicators_module.compute_indicators(SCENE, reader=reader)

        assert all(r.status == DataStatus.UNAVAILABLE for r in results)
        assert all(r.value is None for r in results)

    def test_missing_band_asset_is_an_explained_unavailable(self) -> None:
        scene = {**SCENE, "assets": {"red": "https://example.invalid/B04.tif"}}

        results = indicators_module.compute_indicators(scene, reader=lambda href, band: 0.5)

        assert all(r.status == DataStatus.UNAVAILABLE for r in results)


class TestEnvironmentIndicatorsRoute:
    PATH = "/api/v1/places/IN-OD-29/environment-indicators"

    @pytest.fixture(autouse=True)
    def _seed_place(self, db):
        from app.models.entities import PlaceModel, SourceModel

        db.add(
            SourceModel(
                id="src-esa-sentinel-stac",
                publisher="Element84 / Copernicus Sentinel-2",
                name="Earth Search Sentinel-2 L2A",
                url="https://earth-search.aws.element84.com/v1",
            )
        )
        db.add(
            PlaceModel(
                id="IN-OD-29",
                canonical_name="Khordha",
                place_type="district",
                geometry_available=True,
                search_text="khordha",
                # Without coordinates the route answers "no geocoded
                # coordinates" and never reaches the scene lookup.
                latitude=20.1812,
                longitude=85.6174,
            )
        )
        db.commit()

    def test_unknown_place_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/places/IN-NOPE/environment-indicators").status_code == 404

    def test_no_scene_covering_the_area_is_an_explained_unavailable(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.routes import environment_indicators as route

        monkeypatch.setattr(
            route, "latest_scene_assets", lambda *a, **k: None, raising=False
        )

        response = client.get(self.PATH)

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unavailable"
        assert body["unavailable_reason"]
        assert body["indicators"] == []

    def test_a_scene_with_unreadable_bands_is_unavailable_not_a_guess(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.routes import environment_indicators as route

        monkeypatch.setattr(route, "latest_scene_assets", lambda *a, **k: SCENE, raising=False)
        monkeypatch.setattr(route, "cog_band_reader", lambda: None, raising=False)

        body = client.get(self.PATH).json()

        assert body["status"] == "unavailable"
        assert body["scene"]["scene_id"] == SCENE["scene_id"]
        assert all(i["value"] is None for i in body["indicators"])
        assert all(i["unavailable_reason"] for i in body["indicators"])

    def test_a_scene_with_readable_bands_serves_the_indicators(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.api.routes import environment_indicators as route

        monkeypatch.setattr(route, "latest_scene_assets", lambda *a, **k: SCENE, raising=False)
        monkeypatch.setattr(
            route,
            "cog_band_reader",
            lambda: (lambda href, band: 0.5),
            raising=False,
        )

        body = client.get(self.PATH).json()

        assert body["status"] == "current"
        assert len(body["indicators"]) == 2
        assert all(i["value"] is not None for i in body["indicators"])
        # The scene travels with the figures.
        assert body["scene"]["resolution_meters"] == 10.0
        assert body["scene"]["cloud_cover_percentage"] == 12.5

    def test_the_route_is_not_cached(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """An indicator is only true of the scene it came from."""
        from app.api.routes import environment_indicators as route

        monkeypatch.setattr(route, "latest_scene_assets", lambda *a, **k: None, raising=False)

        assert client.get(self.PATH).headers["cache-control"] == "no-store"
