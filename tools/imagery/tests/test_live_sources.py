"""Live anonymous-access tests. Skipped unless GARUDA_NETWORK_TESTS=1.

Run: `make test-imagery-live`

These prove the source hosts answer without credentials. They do not download
full scenes; the COG check is a bounded range request.
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("GARUDA_NETWORK_TESTS") != "1",
    reason="set GARUDA_NETWORK_TESTS=1 to run live source checks",
)

STAC = (
    "https://earth-search.aws.element84.com/v1/search?"
    "collections=sentinel-2-l2a&bbox=85.76,20.36,85.94,20.54"
    "&datetime=2025-12-01T00:00:00Z/2026-02-28T23:59:59Z&limit=1"
)


def _get(url: str, headers: dict[str, str] | None = None) -> urllib.request.addinfourl:
    # Some public hosts (Cloudflare) reject the default Python-urllib
    # User-Agent. Browsers send a real one; this is still anonymous.
    merged = {"User-Agent": "Mozilla/5.0 (compatible; GarudaImageryCheck/1.0)"}
    merged.update(headers or {})
    req = urllib.request.Request(url, headers=merged)
    return urllib.request.urlopen(req, timeout=60)


def test_stac_answers_without_credentials():
    with _get(STAC) as resp:
        assert resp.status == 200
        payload = json.loads(resp.read())
    assert payload["features"], "expected at least one Sentinel-2 scene"


def test_sentinel_cog_supports_anonymous_range_reads():
    stac_url = (
        "https://earth-search.aws.element84.com/v1/collections/"
        "sentinel-2-l2a/items/S2B_45QUC_20260225_0_L2A"
    )
    with _get(stac_url) as resp:
        item = json.loads(resp.read())
    href = item["assets"]["visual"]["href"]
    with _get(href, {"Range": "bytes=0-1023"}) as resp:
        assert resp.status == 206, "S3 must serve partial content for COG reads"
        head = resp.read()
    assert head[:4] in (b"II*\x00", b"MM\x00*"), "expected a TIFF header"


def test_gibs_tile_answers_without_credentials():
    url = (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/"
        "2/1/1.jpeg"
    )
    with _get(url) as resp:
        assert resp.status == 200
        assert len(resp.read(64)) > 0


def test_mapterhorn_terrain_answers_without_credentials():
    with _get("https://tiles.mapterhorn.com/0/0/0.webp") as resp:
        assert resp.status == 200
        assert resp.read(4) == b"RIFF"
