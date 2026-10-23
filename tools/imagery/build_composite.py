#!/usr/bin/env python3
"""Build a bounded Sentinel-2 L2A true-colour mosaic as XYZ PNG tiles.

Zero-credential pipeline: every HTTP request hits an anonymous, public
endpoint (Earth Search STAC v1 + the `sentinel-cogs` S3 bucket).
No API key, no OAuth, no paid data, no proprietary SDK.

Usage
-----
  python3 tools/imagery/build_composite.py \
      --config tools/imagery/regions/odisha-test.json

Outputs, under `<output_dir>/<region>/`:
  * `z/y/x.png` XYZ tiles (RGBA, transparent where no usable imagery)
  * `manifest.json`  provenance, masks, checksums, licences, tool versions

Also:
  * `--validate` re-verify an existing output directory and manifest
  * `--cache-dir DIR` persist downloaded band windows between runs
  * `--allow-gaps` keep transparent gaps instead of refusing incomplete cover

Determinism: scene ordering, masks, stretch, and tile slicing are pure
functions of the JSON config plus HTTP content; fixed content reproduces
byte-identical tiles (`--validate` checks this via sha256).

Honesty guarantees (non-negotiable):
  * no fabricated pixels: unusable pixels are transparent, never invented.
  * cloud/cloud-shadow/nodata pixel counts land in the manifest.
  * missing coverage is recorded as `gap_pixels`, never silently painted.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import platform
import re
import shutil
import sys
import urllib.parse
import urllib.request
import warnings
from collections import Counter
from pathlib import Path

# Bounded, documented network behaviour applied before rasterio loads GDAL.
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
import rasterio.transform  # noqa: E402
from rasterio.crs import CRS  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.vrt import WarpedVRT  # noqa: E402
from rasterio.warp import reproject  # noqa: E402

EARTH_SEARCH_DEFAULT = "https://earth-search.aws.element84.com/v1"
SENTINEL_COLLECTION = "sentinel-2-l2a"
# Only anonymous HTTPS COGs from this bucket are accepted as pixels. A hostile
# or misconfigured STAC response must not redirect the pipeline elsewhere.
SENTINEL_COG_HOST = "sentinel-cogs.s3.us-west-2.amazonaws.com"
SENTINEL_DATA_LICENCE = (
    "Sentinel Data Legal Notice — free, full and open; reproduction, "
    "distribution, communication to the public, adaptation permitted with "
    "attribution. https://sentinels.copernicus.eu/documents/247904/690755/"
    "Sentinel_Data_Legal_Notice"
)
SENTINEL_ATTRIBUTION_TEMPLATE = "Contains modified Copernicus Sentinel data {years}"

# SCL class ids that must NOT be painted with imagery.
# 0 nodata | 1 saturated | 2 dark | 3 cloud-shadow | 4 vegetation | 5 soil
# 6 water | 7 unclass | 8 cloud-medium | 9 cloud-high | 10 thin cirrus | 11 snow
BLOCKED_SCL = {
    0: "nodata",
    1: "saturated",
    3: "cloud_shadow",
    8: "cloud_medium",
    9: "cloud_high",
    10: "thin_cirrus",
    11: "snow",
}


class PipelineError(RuntimeError):
    """Explicit, user-friendly pipeline failure."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# web-mercator math
# ---------------------------------------------------------------------------
R_WGS84 = 6378137.0
MERC_MIN_M = -20037508.342789244
MERC_MAX_M = 20037508.342789244


def wgs84_to_merc(lon: float, lat: float) -> tuple[float, float]:
    x = math.radians(lon) * R_WGS84
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R_WGS84
    return x, y


def merc_tile_index(x: float, y: float, z: int) -> tuple[int, int]:
    """WebMercator metres -> slippy-map (tx, ty), NW origin."""
    scale = (MERC_MAX_M - MERC_MIN_M) / (1 << z)
    tx = int((x - MERC_MIN_M) // scale)
    ty = int((MERC_MAX_M - y) // scale)
    n = 1 << z
    return max(0, min(n - 1, tx)), max(0, min(n - 1, ty))


# ---------------------------------------------------------------------------
# STAC
# ---------------------------------------------------------------------------
def stac_search(cfg: dict) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "collections": cfg["collection"],
            "bbox": ",".join(f"{v:.6f}" for v in cfg["bbox"]),
            "datetime": (
                f"{cfg['date_range'][0]}T00:00:00Z/{cfg['date_range'][1]}T23:59:59Z"
            ),
            "query": json.dumps({"eo:cloud_cover": {"lte": cfg["max_cloud_cover"]}}),
            "limit": 200,
        }
    )
    url = f"{cfg['stac_endpoint'].rstrip('/')}/search?{params}"
    log(f"STAC search: {url[:110]}…")
    with urllib.request.urlopen(url, timeout=60) as resp:
        payload = json.loads(resp.read())
    feats = payload.get("features", [])
    log(f"  -> {len(feats)} scenes under {cfg['max_cloud_cover']}% cloud")
    # Deterministic priority: least cloud first, then oldest first (a stable
    # tiebreak; compositing order itself is pure and reproducible).
    feats.sort(
        key=lambda f: (
            f["properties"].get("eo:cloud_cover", -1),
            f["properties"].get("datetime", ""),
        )
    )
    if len(feats) > int(cfg["max_scenes"]):
        log(f"  -> kept first {cfg['max_scenes']} by (cloud ↑, date ↑)")
    return feats[: int(cfg["max_scenes"])]


def check_asset(href: str, role: str) -> str:
    """Reject anything that is not an anonymous HTTPS COG on the public bucket."""
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme != "https" or parsed.hostname != SENTINEL_COG_HOST:
        raise PipelineError(
            f"{role} asset is not an anonymous https://{SENTINEL_COG_HOST} URL: {href}"
        )
    return href


# ---------------------------------------------------------------------------
# output grid
# ---------------------------------------------------------------------------
def build_dst_grid(cfg: dict) -> dict:
    """WebMercator output grid honouring `ground_resolution_m` at bbox centre.

    WebMercator stretches distances by 1/cos(lat) relative to WGS84 ground
    metres, so a ground resolution needs the inverse correction (divide by
    cos). Documented, not hidden: see docs/imagery-pipeline.md.
    """
    west, south, east, north = (float(v) for v in cfg["bbox"])
    lat_mid = math.radians((south + north) / 2)
    ground_res = float(cfg["ground_resolution_m"])
    # 1 mercator metre = cos(lat) ground metres, so ground -> mercator divides.
    merc_res = ground_res / math.cos(lat_mid)

    x_left, y_top = wgs84_to_merc(west, north)
    x_right, y_bottom = wgs84_to_merc(east, south)
    # exact integer-friendly resolutions keep tile slicing on integer pixels
    W = max(1, int(round((x_right - x_left) / merc_res)))
    H = max(1, int(round((y_top - y_bottom) / merc_res)))
    res_x = (x_right - x_left) / W
    res_y = (y_top - y_bottom) / H
    transform = rasterio.transform.from_origin(x_left, y_top, res_x, res_y)
    z14_merc_px = (MERC_MAX_M - MERC_MIN_M) / (1 << 14) / 256
    return {
        "transform": transform,
        "W": W,
        "H": H,
        "res_x": res_x,
        "res_y": res_y,
        "merc_res": (res_x + res_y) / 2,
        "ground_res_m": ground_res,
        "lat_mid": lat_mid,
        "z14_ground_res_m": z14_merc_px * math.cos(lat_mid),
        "wgs84": [west, south, east, north],
        "merc": [x_left, y_bottom, x_right, y_top],
    }


# ---------------------------------------------------------------------------
# per-scene reads
# ---------------------------------------------------------------------------
def read_scene_grid(href: str, dst_grid: dict, *, resampling: Resampling) -> np.ndarray:
    """Read a scene COG warped *directly* onto the output EPSG:3857 grid.

    WarpedVRT performs the CRS warp on the fly; together with the COG
    layout this downloads only the range of bytes actually needed.
    Returned shape: (bands, H, W).
    """
    with (
        rasterio.open(href) as base,
        WarpedVRT(
            base,
            crs=CRS.from_epsg(3857),
            transform=dst_grid["transform"],
            width=dst_grid["W"],
            height=dst_grid["H"],
            resampling=resampling,
        ) as vrt,
    ):
        return vrt.read()


# ---------------------------------------------------------------------------
# source-window cache
# ---------------------------------------------------------------------------
def cache_paths(cache: Path | None, key: str) -> tuple[Path, Path, Path]:
    base = cache / key
    return base / "visual.npy", base / "scl.npy", base / "meta.json"


def cache_load(
    cache: Path | None, key: str
) -> tuple[np.ndarray, np.ndarray, dict] | None:
    if cache is None:
        return None
    vis_p, scl_p, meta_p = cache_paths(cache, key)
    if meta_p.exists() and vis_p.exists() and scl_p.exists():
        return np.load(vis_p), np.load(scl_p), json.loads(meta_p.read_text())
    return None


def cache_store(
    cache: Path | None, key: str, vis: np.ndarray, scl: np.ndarray, meta: dict
) -> None:
    if cache is None:
        return
    vis_p, scl_p, meta_p = cache_paths(cache, key)
    vis_p.parent.mkdir(parents=True, exist_ok=True)
    np.save(vis_p, vis)
    np.save(scl_p, scl)
    meta_p.write_text(json.dumps(meta))


# ---------------------------------------------------------------------------
# composite
# ---------------------------------------------------------------------------
def usable_mask(
    visual: np.ndarray,
    scl: np.ndarray,
    painted: np.ndarray,
    counts: Counter[str],
) -> np.ndarray:
    """Pixels a scene may paint: finite RGB, allowed SCL class, not already painted.

    `visual` is (3, H, W); `scl` is (H, W) or (1, H, W). Masked classes are
    counted only where this scene would otherwise contribute (not already
    painted), so counters describe excluded candidates rather than raw overlap.
    """
    if scl.ndim == 3 and scl.shape[0] == 1:
        scl = scl[0]
    usable = np.isfinite(visual).all(axis=0)
    for scl_id, label in BLOCKED_SCL.items():
        hit = (scl == scl_id) & ~painted
        counts[f"{label}_pixels"] += int(hit.sum())
        usable &= scl != scl_id
    usable &= ~painted
    return usable


def build_composite(cfg: dict, dst_grid: dict):
    composite = np.full((3, dst_grid["H"], dst_grid["W"]), np.nan, dtype=np.float32)
    painted = np.zeros((dst_grid["H"], dst_grid["W"]), dtype=bool)
    mask_counts: Counter[str] = Counter()
    scenes_meta: list[dict] = []
    cache = Path(cfg["cache_dir"]) if cfg.get("cache_dir") else None

    feats = stac_search(cfg)
    if not feats:
        raise PipelineError(
            f"No {cfg['collection']} scenes matched date_range={cfg['date_range']} "
            f"with cloud_cover ≤ {cfg['max_cloud_cover']}%."
        )

    log("")
    total_px = dst_grid["H"] * dst_grid["W"]
    for feat in feats:
        props = feat["properties"]
        scene_id = feat["id"]
        scene_years = props["datetime"][:4]
        try:
            visual_href = check_asset(feat["assets"]["visual"]["href"], "visual")
            scl_href = check_asset(feat["assets"]["scl"]["href"], "scl")
        except KeyError as exc:
            raise PipelineError(f"scene {scene_id} is missing asset {exc}") from exc
        meta = {
            "stac_href": f"{cfg['stac_endpoint'].rstrip('/')}/collections/{cfg['collection']}/items/{scene_id}",
            "visual_href": visual_href,
            "scl_href": scl_href,
            "datetime": props["datetime"],
            "eo:cloud_cover": props.get("eo:cloud_cover", -1),
            "proj:epsg": props.get("proj:epsg"),
            "bbox": feat["bbox"],
            "attribution": SENTINEL_ATTRIBUTION_TEMPLATE.format(years=scene_years),
        }

        cached = cache_load(cache, scene_id)
        if cached is None:
            log(
                f"scene {scene_id} ({props['datetime'][:10]}, cc={meta['eo:cloud_cover']:.2f}%) → reading TCI + SCL"
            )
            visual = read_scene_grid(
                feat["assets"]["visual"]["href"],
                dst_grid,
                resampling=Resampling.bilinear,
            ).astype(np.float32)
            scl = read_scene_grid(
                feat["assets"]["scl"]["href"], dst_grid, resampling=Resampling.nearest
            ).astype(np.int16)
        else:
            visual, scl, meta_cached = cached
            meta = {**meta, **meta_cached}
            log(f"scene {scene_id} ← restored from cache")

        usable = usable_mask(visual, scl, painted, mask_counts)
        if int(usable.sum()) == 0:
            log("    contributed 0 usable pixels — skipping")
            continue
        composite[:, usable] = visual[:, usable]
        painted |= usable
        cache_store(cache, scene_id, visual, scl, meta)
        log(f"    painted {int(usable.sum()):,} px")
        scenes_meta.append({**meta, "painted_pixels": int(usable.sum())})

    gaps = int((~painted).sum())
    if gaps / total_px > 0.01 and not cfg.get("allow_gaps"):
        raise PipelineError(
            f"Refusing to ship: {gaps:,}/{total_px:,} px unpainted "
            f"({gaps / total_px:.1%}). Rerun with --allow-gaps or adjust bbox/date_range."
        )
    mask_counts["gap_pixels"] = gaps
    return composite, painted, dict(mask_counts), scenes_meta


def stretch_to_uint8(
    composite: np.ndarray, painted: np.ndarray
) -> tuple[np.ndarray, dict]:
    """Per-band 2nd–98th percentile stretch, using only actually-painted pixels."""
    if not painted.any():
        raise PipelineError("No pixels painted by any scene — nothing to stretch.")
    out = np.zeros_like(composite, dtype=np.uint8)
    bands_info = {}
    for b in range(3):
        vals = composite[b][painted]
        p2, p98 = (float(np.nanpercentile(vals, 2)), float(np.nanpercentile(vals, 98)))
        if p98 <= p2:
            raise PipelineError(
                "Degenerate colour range — source imagery unusable.",
            )
        lo = np.where(painted, composite[b], p2)
        scaled = np.clip((lo - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
        out[b] = scaled
        bands_info[f"band{b}"] = {"p2": p2, "p98": p98}
    return out, bands_info


# ---------------------------------------------------------------------------
# tile slicing
# ---------------------------------------------------------------------------
def render_level(
    rgb: np.ndarray, painted: np.ndarray, dst_grid: dict, z: int
) -> tuple[np.ndarray, int, int, int, int]:
    """Reproject the mosaic onto a tile-aligned RGBA canvas for one zoom level.

    Each zoom needs its own resampling: a z13 tile covers ~522 source pixels at
    Odisha's latitude, not 256. RGB is averaged only over painted pixels
    (weighted by the mask) so transparent gaps never bleed dark halo colours
    into their neighbours. Alpha is the mask's fractional coverage.

    Returns (rgba canvas, tx0, ty0, tx1, ty1); canvas is (4, H, W) uint8.
    """
    tsz = (MERC_MAX_M - MERC_MIN_M) / (1 << z)
    px = tsz / 256
    minx, miny, maxx, maxy = dst_grid["merc"]
    tx0, ty0 = merc_tile_index(minx, maxy, z)
    tx1, ty1 = merc_tile_index(maxx, miny, z)

    dst_transform = rasterio.transform.from_origin(
        MERC_MIN_M + tx0 * tsz,
        MERC_MAX_M - ty0 * tsz,
        px,
        px,
    )
    cw = (tx1 - tx0 + 1) * 256
    ch = (ty1 - ty0 + 1) * 256

    mask = painted.astype(np.float32)
    weighted = rgb.astype(np.float32) * mask[np.newaxis, :, :]
    dst_rgb = np.zeros((3, ch, cw), dtype=np.float32)
    dst_cov = np.zeros((1, ch, cw), dtype=np.float32)
    common = {
        "src_transform": dst_grid["transform"],
        "src_crs": CRS.from_epsg(3857),
        "dst_transform": dst_transform,
        "dst_crs": CRS.from_epsg(3857),
        "resampling": Resampling.average,
    }
    reproject(source=weighted, destination=dst_rgb, **common)
    reproject(source=mask[np.newaxis, :, :], destination=dst_cov, **common)

    coverage = np.maximum(dst_cov, 1e-6)
    canvas_rgb = np.clip(np.where(dst_cov > 0, dst_rgb / coverage, 0), 0, 255)
    canvas_alpha = np.clip(np.rint(dst_cov[0] * 255), 0, 255)
    canvas = np.concatenate(
        [canvas_rgb.astype(np.uint8), canvas_alpha.astype(np.uint8)[np.newaxis, :, :]],
        axis=0,
    )
    return canvas, tx0, ty0, tx1, ty1


def slice_tiles(
    rgb: np.ndarray, painted: np.ndarray, dst_grid: dict, cfg: dict, out_root: Path
) -> tuple[dict, dict]:
    files: dict[str, dict] = {}
    per_level: dict[str, dict] = {}
    for z in cfg["zoom_levels"]:
        canvas, tx0, ty0, tx1, ty1 = render_level(rgb, painted, dst_grid, int(z))
        n_tiles = n_non_transparent = 0
        level_dir = out_root / str(z)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                sx = (tx - tx0) * 256
                sy = (ty - ty0) * 256
                tile = canvas[:, sy : sy + 256, sx : sx + 256]
                if tile.shape != (4, 256, 256):
                    raise PipelineError(f"tile {z}/{ty}/{tx} has shape {tile.shape}")
                rel = level_dir / f"{ty}" / f"{tx}.png"
                rel.parent.mkdir(parents=True, exist_ok=True)
                write_png(rel, tile)
                non_transparent = int((tile[3] > 0).sum())
                files[f"{z}/{ty}/{tx}.png"] = {
                    "size": rel.stat().st_size,
                    "sha256": sha256(rel),
                    "non_transparent_pixels": non_transparent,
                }
                n_tiles += 1
                if non_transparent > 0:
                    n_non_transparent += 1
        per_level[str(z)] = {"count": n_tiles, "non_transparent": n_non_transparent}
        log(f"tiles z{z}: {n_tiles} ({n_non_transparent} contain imagery)")
    return per_level, files


def write_png(path: Path, canvas: np.ndarray) -> None:
    h, w = canvas.shape[1], canvas.shape[2]
    # XYZ tiles are addressed by path, not georeferencing — no CRS/transform.
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=w,
        height=h,
        count=4,
        dtype="uint8",
    ) as dst:
        dst.write(canvas)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
REQUIRED_KEYS = (
    "region",
    "bbox",
    "date_range",
    "stac_endpoint",
    "collection",
    "max_cloud_cover",
    "max_scenes",
    "ground_resolution_m",
    "zoom_levels",
    "output_dir",
)


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text())
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise PipelineError(f"Config {path} is missing keys: {missing}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(cfg["region"])):
        raise PipelineError(
            f"region {cfg['region']!r} must be a filename-safe slug "
            "(letters, digits, dot, underscore, hyphen)"
        )
    w, s, e, n = cfg["bbox"]
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise PipelineError(f"bbox {cfg['bbox']} is not a valid [w,s,e,n] lon/lat box")
    if max(cfg["zoom_levels"]) > 14:
        raise PipelineError(
            "zoom_levels beyond 14 upscales the native 10 m data — set 14 as the ceiling"
        )
    return cfg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_build(cfg: dict) -> int:
    out_root = Path(cfg["output_dir"]) / cfg["region"]
    started = datetime.datetime.now(datetime.UTC).isoformat()

    dst_grid = build_dst_grid(cfg)
    log(
        f"mosaic grid: {dst_grid['W']}×{dst_grid['H']} px, ground "
        f"{dst_grid['ground_res_m']} m (hardware mercator {dst_grid['merc_res']:.2f} m/px)"
    )

    composite, painted, mask_counts, scenes_meta = build_composite(cfg, dst_grid)
    years = sorted({s["datetime"][:4] for s in scenes_meta})
    year_str = years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}"
    attribution = SENTINEL_ATTRIBUTION_TEMPLATE.format(years=year_str)

    rgb, bands_info = stretch_to_uint8(composite, painted)

    if out_root.exists():
        log(f"clearing previous output: {out_root}")
        shutil.rmtree(out_root)

    per_level, files = slice_tiles(rgb, painted, dst_grid, cfg, out_root)

    manifest = {
        "region": cfg["region"],
        "generated_at": started,
        "config": {k: v for k, v in cfg.items() if k != "cache_dir"},
        "scenes": scenes_meta,
        "mosaic": {
            "bbox_wgs84": list(cfg["bbox"]),
            "shape": [dst_grid["H"], dst_grid["W"]],
            "ground_res_m": dst_grid["ground_res_m"],
            "merc_res_m": round(dst_grid["merc_res"], 4),
            # Native Sentinel-2 TCI is 10 m; z14 pixels are ~8.9 m ground here,
            # i.e. a mild upsample. z15+ would invent detail.
            "z14_ground_res_m": round(dst_grid["z14_ground_res_m"], 3),
        },
        "stretch": bands_info,
        "mask_counts": mask_counts,
        "painted_pixels": int(painted.sum()),
        "total_pixels": int(dst_grid["H"] * dst_grid["W"]),
        "tiles_per_level": per_level,
        "files": files,
        "licences": [
            {
                "title": "Sentinel-2 L2A via AWS Open Data (Earth Search v1)",
                "source": cfg["stac_endpoint"],
                "licence": SENTINEL_DATA_LICENCE,
                "attribution": attribution,
                "modified": True,
            }
        ],
        "attribution_display": attribution,
        "tools": {
            "python": platform.python_version(),
            "rasterio": rasterio.__version__,
            "numpy": np.__version__,
        },
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2))
    size_mb = sum(f["size"] for f in files.values()) / 1e6
    log(
        f"\n{len(files)} tiles · {size_mb:.1f} MB · painted "
        f"{manifest['painted_pixels']:,}/{manifest['total_pixels']:,} px"
    )
    log(f"manifest: {out_root / 'manifest.json'}")
    log(f"attribution: {attribution}")
    return 0


def run_validate(cfg: dict) -> int:
    out_root = Path(cfg["output_dir"]) / cfg["region"]
    man_path = out_root / "manifest.json"
    if not man_path.exists():
        log("FAIL — no manifest.json (apply pipeline first)")
        return 1
    man = json.loads(man_path.read_text())
    grid = build_dst_grid(cfg)
    errs: list[str] = []

    if man.get("region") != cfg["region"]:
        errs.append(f"manifest region {man.get('region')!r} ≠ config {cfg['region']!r}")
    man_bbox = [float(v) for v in man.get("mosaic", {}).get("bbox_wgs84", [])]
    cfg_bbox = [float(v) for v in cfg["bbox"]]
    if man_bbox != cfg_bbox:
        errs.append(f"manifest bbox {man_bbox} ≠ config {cfg_bbox}")

    for z in cfg["zoom_levels"]:
        tx0, ty0 = merc_tile_index(grid["merc"][0], grid["merc"][3], z)
        tx1, ty1 = merc_tile_index(grid["merc"][2], grid["merc"][1], z)
        seen = 0
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                rel = f"{z}/{ty}/{tx}.png"
                p = out_root / rel
                ref = man.get("files", {}).get(rel)
                if not p.exists():
                    errs.append(f"missing tile {rel}")
                    continue
                seen += 1
                if ref is None:
                    errs.append(f"tile {rel} absent from manifest")
                    continue
                got = sha256(p)
                if ref.get("sha256") != got:
                    errs.append(f"checksum mismatch {rel}")
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        with rasterio.open(p) as ds:
                            if (ds.width, ds.height) != (256, 256):
                                errs.append(
                                    f"{rel}: {ds.width}×{ds.height}, expected 256×256"
                                )
                            elif ds.count != 4 or ds.dtypes[0] != "uint8":
                                errs.append(
                                    f"{rel}: expected 4×uint8 RGBA, got {ds.count}×{ds.dtypes[0]}"
                                )
                            else:
                                alpha = ds.read(4)
                    painted = int((alpha > 0).sum())
                    if painted != ref.get("non_transparent_pixels"):
                        errs.append(
                            f"{rel}: {painted} non-transparent px ≠ manifest "
                            f"{ref.get('non_transparent_pixels')}"
                        )
                except Exception as exc:  # noqa: BLE001 - any unreadable tile is a failure
                    errs.append(f"unreadable tile {rel}: {exc}")
        ref_level = man.get("tiles_per_level", {}).get(str(z))
        if ref_level is None or ref_level.get("count") != seen:
            errs.append(f"level {z}: manifest count {ref_level} ≠ on-disk {seen}")
    for e in errs[:10]:
        log("FAIL " + e)
    if errs:
        log(f"FAIL — {len(errs)} validation error(s)")
        return 1
    log(
        f"OK — levels {cfg['zoom_levels']} verified (checksums, RGBA 256², alpha); "
        f"painted {man['painted_pixels']:,}/{man['total_pixels']:,} px"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--allow-gaps", action="store_true")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    if args.cache_dir:
        cfg["cache_dir"] = args.cache_dir
    if args.allow_gaps:
        cfg["allow_gaps"] = True

    return run_validate(cfg) if args.validate else run_build(cfg)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PipelineError as exc:
        log(f"pipeline error: {exc}")
        sys.exit(1)
