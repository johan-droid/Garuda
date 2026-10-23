"""Offline tests for the Sentinel-2 mosaic pipeline.

No network: every test builds synthetic arrays/tiles. Run with
`python3 -m pytest tools/imagery/tests -q` (needs rasterio + numpy).
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_composite as bc  # noqa: E402


def base_config(tmp_path: Path, **overrides) -> dict:
    cfg = {
        "region": "test-region",
        "bbox": [86.0, 20.0, 86.05, 20.05],
        "date_range": ["2026-01-01", "2026-02-01"],
        "stac_endpoint": "https://example.invalid/v1",
        "collection": "sentinel-2-l2a",
        "max_cloud_cover": 10,
        "max_scenes": 2,
        "ground_resolution_m": 10,
        "zoom_levels": [13, 14],
        "output_dir": str(tmp_path / "out"),
    }
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# grid math
# ---------------------------------------------------------------------------
def test_ground_resolution_is_converted_to_mercator_metres(tmp_path):
    grid = bc.build_dst_grid(base_config(tmp_path))
    lat = math.radians(20.025)
    # 10 ground metres need MORE mercator metres at this latitude, not fewer.
    assert grid["res_x"] == pytest.approx(10 / math.cos(lat), rel=1e-3)
    assert grid["res_y"] == pytest.approx(10 / math.cos(lat), rel=1e-3)


def test_merc_tile_index_known_points():
    assert bc.merc_tile_index(0.0, 0.0, 1) == (1, 1)
    assert bc.merc_tile_index(bc.MERC_MIN_M + 1, bc.MERC_MAX_M - 1, 0) == (0, 0)


# ---------------------------------------------------------------------------
# masking
# ---------------------------------------------------------------------------
def test_usable_mask_blocks_cloud_shadow_and_nodata():
    scl = np.array(
        [
            [0, 3, 8, 9],
            [10, 11, 4, 5],
            [6, 7, 2, 4],
            [4, 4, 4, 4],
        ],
        dtype=np.int16,
    )
    visual = np.full((3, 4, 4), 100, dtype=np.float32)
    counts: Counter[str] = Counter()

    usable = bc.usable_mask(visual, scl, np.zeros((4, 4), dtype=bool), counts)

    expected = np.array(
        [
            [False, False, False, False],
            [False, False, True, True],
            [True, True, True, True],
            [True, True, True, True],
        ]
    )
    np.testing.assert_array_equal(usable, expected)
    assert counts["nodata_pixels"] == 1
    assert counts["cloud_shadow_pixels"] == 1
    assert counts["cloud_medium_pixels"] == 1
    assert counts["cloud_high_pixels"] == 1
    assert counts["thin_cirrus_pixels"] == 1
    assert counts["snow_pixels"] == 1


def test_usable_mask_rejects_nan_and_respects_already_painted():
    visual = np.full((3, 3, 3), 100, dtype=np.float32)
    visual[:, 0, 0] = np.nan
    scl = np.full((3, 3), 4, dtype=np.int16)
    painted = np.zeros((3, 3), dtype=bool)
    painted[1, :] = True
    counts: Counter[str] = Counter()

    usable = bc.usable_mask(visual, scl, painted, counts)

    assert not usable[0, 0]
    assert not usable[1].any()
    assert usable[2].all()


def test_usable_mask_counts_only_unpainted_candidates():
    visual = np.full((3, 2, 2), 100, dtype=np.float32)
    scl = np.full((2, 2), 8, dtype=np.int16)
    painted = np.zeros((2, 2), dtype=bool)
    painted[0, 0] = True
    counts: Counter[str] = Counter()

    bc.usable_mask(visual, scl, painted, counts)

    assert counts["cloud_medium_pixels"] == 3


# ---------------------------------------------------------------------------
# tiles
# ---------------------------------------------------------------------------
def test_every_zoom_renders_correctly_addressed_seamless_tiles(tmp_path):
    cfg = base_config(tmp_path)
    grid = bc.build_dst_grid(cfg)
    h, w = grid["H"], grid["W"]

    # Horizontal ramp: one source column step is 255/(w-1).
    ramp = np.tile(np.linspace(0, 255, w, dtype=np.float32), (h, 1))
    rgb = np.stack([ramp, ramp, ramp]).astype(np.uint8)
    painted = np.ones((h, w), dtype=bool)

    out_root = tmp_path / "tiles"
    per_level, _files = bc.slice_tiles(rgb, painted, grid, cfg, out_root)

    for z in cfg["zoom_levels"]:
        level_dir = out_root / str(z)
        tiles = sorted(level_dir.glob("*/*.png"))
        assert tiles, f"no tiles generated for z{z}"
        for tile in tiles:
            with bc.rasterio.open(tile) as ds:
                assert (ds.width, ds.height, ds.count) == (256, 256, 4)
            assert (out_root / f"{z}/{tile.parent.name}/{tile.name}").exists()
        assert per_level[str(z)]["count"] == len(tiles)

    # Seam test at z13: adjacent tiles must continue the ramp. The old
    # fixed-256-crop implementation jumped by ~255 at every seam.
    z = 13
    level_dir = out_root / str(z)
    rows = sorted({p.parent for p in level_dir.glob("*/*.png")})
    for row_dir in rows:
        tiles = sorted(row_dir.glob("*.png"))
        if len(tiles) < 2:
            continue
        imgs = []
        for tile in tiles:
            with bc.rasterio.open(tile) as ds:
                imgs.append(ds.read())
        for left, right in zip(imgs, imgs[1:]):
            if left[3].min() == 0 or right[3].min() == 0:
                continue  # bbox edge tiles are legitimately partial
            step = 255 / (w - 1) * (2**14 / 2**z)
            got = float(
                right[0, :, 0].astype(int).mean() - left[0, :, 255].astype(int).mean()
            )
            assert abs(got - step) < 3, (
                f"z{z} seam jumps by {got:.1f}, expected ~{step:.1f}"
            )
        break


def test_gap_pixels_stay_transparent(tmp_path):
    cfg = base_config(tmp_path, zoom_levels=[14])
    grid = bc.build_dst_grid(cfg)
    h, w = grid["H"], grid["W"]
    rgb = np.full((3, h, w), 120, dtype=np.uint8)
    painted = np.ones((h, w), dtype=bool)
    painted[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = False

    canvas, tx0, ty0, _, _ = bc.render_level(rgb, painted, grid, 14)
    alpha = canvas[3]
    # Map the mosaic's centre into the tile-aligned canvas, accounting for the
    # canvas origin sitting north-west of the bbox.
    tsz = (bc.MERC_MAX_M - bc.MERC_MIN_M) / (1 << 14)
    px = tsz / 256
    canvas_left = bc.MERC_MIN_M + tx0 * tsz
    canvas_top = bc.MERC_MAX_M - ty0 * tsz
    cx = (grid["merc"][0] + grid["merc"][2]) / 2
    cy = (grid["merc"][1] + grid["merc"][3]) / 2
    ix = int((cx - canvas_left) / px)
    iy = int((canvas_top - cy) / px)
    assert alpha[iy, ix] == 0, "a fully unpainted area must be transparent"
    assert alpha.max() == 255, "painted pixels must be opaque"


# ---------------------------------------------------------------------------
# config / validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "overrides",
    [
        {"bbox": [90, 20, 80, 21]},
        {"bbox": [86, 20, 86, 21]},
        {"zoom_levels": [15]},
        {"region": ""},
    ],
)
def test_invalid_config_is_rejected(tmp_path, overrides):
    cfg = base_config(tmp_path, **overrides)
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises(bc.PipelineError):
        bc.load_config(path)


def test_source_assets_must_come_from_the_public_bucket():
    good = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/TCI.tif"
    assert bc.check_asset(good, "visual") == good
    for bad in (
        "http://sentinel-cogs.s3.us-west-2.amazonaws.com/a/TCI.tif",
        "https://evil.example.com/a/TCI.tif",
        "s3://sentinel-cogs/a/TCI.tif",
    ):
        with pytest.raises(bc.PipelineError):
            bc.check_asset(bad, "visual")


def test_missing_config_keys_are_rejected(tmp_path):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps({"region": "x"}))
    with pytest.raises(bc.PipelineError):
        bc.load_config(path)


def _write_valid_zero_zoom_output(tmp_path: Path) -> dict:
    cfg = base_config(tmp_path, zoom_levels=[0], bbox=[86.0, 20.0, 86.001, 20.001])
    out_root = Path(cfg["output_dir"]) / cfg["region"]
    canvas = np.zeros((4, 256, 256), dtype=np.uint8)
    canvas[:3] = 90
    canvas[3] = 255
    tile_path = out_root / "0" / "0" / "0.png"
    tile_path.parent.mkdir(parents=True)
    bc.write_png(tile_path, canvas)
    manifest = {
        "region": cfg["region"],
        "mosaic": {"bbox_wgs84": cfg["bbox"]},
        "files": {
            "0/0/0.png": {
                "size": tile_path.stat().st_size,
                "sha256": bc.sha256(tile_path),
                "non_transparent_pixels": 256 * 256,
            }
        },
        "tiles_per_level": {"0": {"count": 1, "non_transparent": 1}},
        "painted_pixels": 256 * 256,
        "total_pixels": 256 * 256,
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest))
    return cfg


def test_validate_accepts_a_correct_output(tmp_path):
    cfg = _write_valid_zero_zoom_output(tmp_path)
    assert bc.run_validate(cfg) == 0


def test_validate_rejects_missing_tile(tmp_path):
    cfg = _write_valid_zero_zoom_output(tmp_path)
    (Path(cfg["output_dir"]) / cfg["region"] / "0" / "0" / "0.png").unlink()
    assert bc.run_validate(cfg) == 1


def test_validate_rejects_tampered_tile(tmp_path):
    cfg = _write_valid_zero_zoom_output(tmp_path)
    tile = Path(cfg["output_dir"]) / cfg["region"] / "0" / "0" / "0.png"
    canvas = np.full((4, 256, 256), 7, dtype=np.uint8)
    bc.write_png(tile, canvas)
    assert bc.run_validate(cfg) == 1


def test_validate_rejects_wrong_tile_size(tmp_path):
    cfg = _write_valid_zero_zoom_output(tmp_path)
    tile = Path(cfg["output_dir"]) / cfg["region"] / "0" / "0" / "0.png"
    bc.write_png(tile, np.zeros((4, 128, 128), dtype=np.uint8))
    assert bc.run_validate(cfg) == 1
