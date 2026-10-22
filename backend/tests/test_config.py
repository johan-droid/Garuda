"""Unit tests for Garuda core configuration and validators."""

from pathlib import Path

import pytest

from app.core.config import Settings, _DEFAULT_SQLITE_PATH


def test_sqlite_path_anchored_to_project_root() -> None:
    """BE-TASK-01: Verify default SQLite database is anchored to project root."""
    expected_root = Path(__file__).resolve().parents[2]
    expected_db_path = (expected_root / "garuda_local.db").resolve()

    assert _DEFAULT_SQLITE_PATH == expected_db_path
    assert _DEFAULT_SQLITE_PATH.name == "garuda_local.db"


def test_default_database_url_uses_anchored_path() -> None:
    """BE-TASK-01: Default DATABASE_URL uses f'sqlite:///{_DEFAULT_SQLITE_PATH}'."""
    settings = Settings(DATABASE_URL=f"sqlite:///{_DEFAULT_SQLITE_PATH}")
    assert settings.DATABASE_URL == f"sqlite:///{_DEFAULT_SQLITE_PATH}"


def test_database_url_relative_default_normalized() -> None:
    """BE-TASK-01: Relative sqlite default URLs are normalized to project root path."""
    settings_rel = Settings(DATABASE_URL="sqlite:///./garuda_local.db")
    assert settings_rel.DATABASE_URL == f"sqlite:///{_DEFAULT_SQLITE_PATH}"

    settings_short = Settings(DATABASE_URL="sqlite:///garuda_local.db")
    assert settings_short.DATABASE_URL == f"sqlite:///{_DEFAULT_SQLITE_PATH}"


def test_database_url_custom_paths_preserved() -> None:
    """Custom SQLite or PostgreSQL paths are not modified."""
    custom_pg = "postgresql://user:pass@localhost:5432/garuda_db"
    settings_pg = Settings(DATABASE_URL=custom_pg)
    assert settings_pg.DATABASE_URL == custom_pg

    custom_sqlite = "sqlite:////tmp/custom.db"
    settings_sqlite = Settings(DATABASE_URL=custom_sqlite)
    assert settings_sqlite.DATABASE_URL == custom_sqlite


def test_allowed_origins_json_string() -> None:
    """BE-TASK-05: ALLOWED_ORIGINS accepts JSON array string."""
    settings = Settings(
        ALLOWED_ORIGINS='["http://localhost:5173", "https://garuda.internal"]',
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "https://garuda.internal",
    ]


def test_allowed_origins_comma_separated_string() -> None:
    """BE-TASK-05: ALLOWED_ORIGINS accepts comma-separated string."""
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:5173,https://garuda.internal",
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "https://garuda.internal",
    ]


def test_allowed_origins_comma_separated_with_spaces() -> None:
    """BE-TASK-05: ALLOWED_ORIGINS trims whitespace in comma-separated string."""
    settings = Settings(
        ALLOWED_ORIGINS=" http://localhost:5173 , https://garuda.internal ",
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "https://garuda.internal",
    ]


def test_allowed_origins_list_input() -> None:
    """BE-TASK-05: ALLOWED_ORIGINS accepts an existing list."""
    settings = Settings(
        ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"],
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_allowed_origins_from_cors_origins_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """BE-TASK-05: CORS_ORIGINS from environment does not fail with SettingsError."""
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,https://garuda.internal")
    settings = Settings()
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "https://garuda.internal",
    ]


def test_allowed_origins_from_cors_origins_json_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """BE-TASK-05: CORS_ORIGINS JSON string from environment parses correctly."""
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
    settings = Settings()
    assert settings.ALLOWED_ORIGINS == ["http://localhost:5173"]
