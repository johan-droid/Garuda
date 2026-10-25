"""Derived satellite indicators: NDVI and water extent.

These are *derived* values, not measurements. NDVI and NDWI are ratios of
Sentinel-2 bands, so the number is only as good as the bands behind it - which
is why every indicator this module produces carries the scene it came from.

Band references (Sentinel-2 MSI, the collection this project uses):
  * B03 - green, 10 m
  * B04 - red, 10 m
  * B08 - near infrared, 10 m

  NDVI = (B08 - B04) / (B08 + B04)   vegetation vigour, +1 healthy canopy
  NDWI = (B03 - B08) / (B03 + B08)   open water, +1 water

Both are undefined where the denominator is zero. That is reported as `None`,
never as `0` - a zero denominator is not a zero index, and serving one would
invent a reading.

This module is deliberately free of rasterio and numpy. The arithmetic is over
single pixel values, and reading a Cloud-Optimised GeoTIFF belongs to the
imagery pipeline (`tools/imagery/`), which is where GDAL lives. The backend
stays GDAL-free; `cog_band_reader()` in the route is what makes that explicit
rather than silent.
"""

from datetime import UTC, datetime
from typing import Any, Callable, Sequence

from pydantic import BaseModel

from app.domain.common import DataStatus, RecordType
from app.domain.contracts import EnvironmentIndicator, SceneMetadata

# Sentinel-2 MSI band asset keys, as Earth Search STAC names them.
BAND_ASSET_KEYS = {"B03": "green", "B04": "red", "B08": "nir"}

SENTINEL2_MISSION = "Sentinel-2 (ESA/Copernicus)"


class IndicatorSpec(BaseModel):
    """What an indicator is, independent of any one scene."""

    field_name: str
    label: str
    bands: list[str]
    formula: str
    unit: str | None = None
    mission: str = SENTINEL2_MISSION
    record_type: RecordType = RecordType.OBSERVATION


INDICATOR_SPECS: list[IndicatorSpec] = [
    IndicatorSpec(
        field_name="ndvi",
        label="Normalised Difference Vegetation Index",
        bands=["B08", "B04"],
        formula="(B08 - B04) / (B08 + B04)",
        unit=None,
    ),
    IndicatorSpec(
        field_name="water_extent",
        label="Normalised Difference Water Index",
        bands=["B03", "B08"],
        formula="(B03 - B08) / (B03 + B08)",
        unit=None,
    ),
]


def ndvi_value(nir: float | None, red: float | None) -> float | None:
    """Normalised difference vegetation index, or None when undefined."""
    if nir is None or red is None:
        return None
    denominator = nir + red
    if denominator == 0:
        return None
    return (nir - red) / denominator


def ndwi_value(green: float | None, nir: float | None) -> float | None:
    """Normalised difference water index, or None when undefined."""
    if green is None or nir is None:
        return None
    denominator = green + nir
    if denominator == 0:
        return None
    return (green - nir) / denominator


def _band_value(assets: dict[str, Any], band: str, reader: Callable[[str, str], Any]) -> float | None:
    """Read one band for one pixel, or None if the asset or the read failed.

    The reader gets both the href and the band name: a COG filename does not
    reliably identify its band, so the band must be passed rather than parsed.
    """
    asset_key = BAND_ASSET_KEYS.get(band)
    if asset_key is None:
        return None
    href = assets.get(asset_key)
    if not isinstance(href, str) or not href:
        return None
    try:
        raw = reader(href, band)
    except Exception:  # noqa: BLE001 - an unreadable COG is a missing band
        return None
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def compute_indicators(
    scene: dict[str, Any],
    reader: Callable[[str, str], Any] | None = None,
) -> list[EnvironmentIndicator]:
    """Derive every indicator for one scene.

    `reader(href, band)` turns one band asset href into a single pixel value.
    It is None when the deployment cannot read Cloud-Optimised GeoTIFFs, which
    is the default here - the backend ships no GDAL. In that case each indicator is reported
    `unavailable` with a reason naming the missing capability, rather than
    served as a default or a guess.
    """
    scene_meta = _scene_metadata(scene)
    assets = scene.get("assets")
    assets = assets if isinstance(assets, dict) else {}

    if reader is None:
        reason = (
            "Band pixels are not readable in this deployment: the backend ships no "
            "GDAL/rasterio. The scene is reported so the imagery pipeline can derive "
            "the indicator offline."
        )
        return [_unavailable(spec, scene_meta, reason) for spec in INDICATOR_SPECS]

    results: list[EnvironmentIndicator] = []
    for spec in INDICATOR_SPECS:
        values = {band: _band_value(assets, band, reader) for band in spec.bands}
        value = _derive(spec.field_name, values)
        if value is None:
            missing = [b for b, v in values.items() if v is None]
            if missing:
                reason = (
                    f"Band(s) {', '.join(missing)} could not be read for scene "
                    f"{scene_meta.scene_id}. No indicator is reported rather than a "
                    f"partial or default value."
                )
            else:
                reason = (
                    f"The {spec.field_name} denominator is zero for scene "
                    f"{scene_meta.scene_id}; the index is undefined, not zero."
                )
            results.append(_unavailable(spec, scene_meta, reason))
            continue
        results.append(
            EnvironmentIndicator(
                field_name=spec.field_name,
                label=spec.label,
                status=DataStatus.CURRENT,
                value=value,
                unit=spec.unit,
                bands=list(spec.bands),
                formula=spec.formula,
                scene=scene_meta,
            )
        )
    return results


def _derive(field_name: str, values: dict[str, float | None]) -> float | None:
    if field_name == "ndvi":
        return ndvi_value(values.get("B08"), values.get("B04"))
    if field_name == "water_extent":
        return ndwi_value(values.get("B03"), values.get("B08"))
    return None


def _scene_metadata(scene: dict[str, Any]) -> SceneMetadata:
    raw_date = scene.get("datetime")
    parsed = _parse_datetime(raw_date)
    cloud = scene.get("cloud_cover")
    resolution = scene.get("resolution_meters")
    return SceneMetadata(
        scene_id=str(scene.get("scene_id") or "unknown"),
        acquisition_date=parsed,
        resolution_meters=float(resolution) if resolution is not None else None,
        cloud_cover_percentage=float(cloud) if cloud is not None else None,
        satellite_mission=scene.get("satellite_mission") or SENTINEL2_MISSION,
        source_url=scene.get("source_url"),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _unavailable(
    spec: IndicatorSpec, scene: SceneMetadata, reason: str
) -> EnvironmentIndicator:
    return EnvironmentIndicator(
        field_name=spec.field_name,
        label=spec.label,
        status=DataStatus.UNAVAILABLE,
        value=None,
        unit=spec.unit,
        bands=list(spec.bands),
        formula=spec.formula,
        unavailable_reason=reason,
        scene=scene,
    )


def describe_sequence(values: Sequence[float | None]) -> float | None:
    """Mean of a sequence, ignoring missing samples.

    Used by the imagery pipeline when it derives an indicator over a window
    rather than a single pixel. An empty sequence is None, not zero.
    """
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)
