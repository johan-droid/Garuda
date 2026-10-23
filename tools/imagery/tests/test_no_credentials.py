"""Guard: no credential may be required or bundled anywhere in the globe stack.

Scans pipeline sources and the built frontend (when present) for common secret
shapes and for `VITE_*` secret variables. This is a heuristic, not a proof:
it catches the mistakes this project is most likely to make.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRONTEND_SRC = REPO / "frontend" / "src"
FRONTEND_DIST = REPO / "frontend" / "dist"
PIPELINE = REPO / "tools" / "imagery"

SECRET_PATTERNS = {
    "VITE secret env var": re.compile(r"VITE_[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)"),
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "URL-embedded credentials": re.compile(r"https?://[^/\s:@]+:[^/\s@]+@"),
}

ANONYMOUS_HOSTS = (
    "gibs.earthdata.nasa.gov",
    "tiles.mapterhorn.com",
    "earth-search.aws.element84.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
)


def _files() -> list[Path]:
    files = list(FRONTEND_SRC.rglob("*")) + list(PIPELINE.rglob("*.py"))
    files += list(PIPELINE.glob("*.txt")) + list(PIPELINE.glob("*.json"))
    files += list(PIPELINE.glob("regions/*.json"))
    if FRONTEND_DIST.exists():
        files += list(FRONTEND_DIST.rglob("*.js"))
        files += list(FRONTEND_DIST.rglob("*.html"))
    return [f for f in files if f.is_file() and "__pycache__" not in f.parts]


def test_no_credential_shapes_in_sources_or_bundle():
    hits: list[str] = []
    for path in _files():
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{label}: {path.relative_to(REPO)}")
    assert not hits, "credential-shaped strings found:\n" + "\n".join(hits)


def test_runtime_sources_are_the_anonymous_endpoints():
    config = (FRONTEND_SRC / "cesium" / "config.ts").read_text()
    pipeline = (PIPELINE / "build_composite.py").read_text()
    for host in ANONYMOUS_HOSTS:
        assert host in config or host in pipeline, f"{host} is not referenced"


def test_no_authentication_headers_or_credentials_in_pipeline():
    text = (PIPELINE / "build_composite.py").read_text()
    for forbidden in (
        "Authorization",
        "AWS_ACCESS_KEY",
        "AWS_SECRET",
        "api_key",
        "apikey",
    ):
        assert forbidden not in text, f"pipeline references {forbidden}"
