"""Tests for Alembic database migrations."""

from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

# Registered here, at import time, so the metadata below carries every table.
# `saved_place` is not reachable from `app.models.entities`, and a test that
# imported it only inside a function would still pass while the migration
# autogenerate path silently skipped the table.
import app.models.entities  # noqa: F401
import app.models.saved_place  # noqa: F401


def test_alembic_heads_single_head() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ini_path = repo_root / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    # Single head, and named rather than counted: a second head would mean a
    # merge revision is needed, and a bare count would pass on a branch.
    assert heads == ["0002_saved_places"]


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ini_path = repo_root / "alembic.ini"
    test_db = tmp_path / "test_migration.db"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db}")

    # Upgrade to head
    command.upgrade(cfg, "head")

    # The migrations must produce every table the ORM declares, or a
    # deployment upgraded by Alembic would be missing tables that a fresh
    # `create_all` deployment has. Compared against the live metadata, not a
    # hardcoded list, so a new model fails here instead of at runtime.
    from sqlalchemy import create_engine, inspect

    from app.db.session import Base

    import app.models.saved_place  # noqa: F401  (registers the table)

    migrated = set(inspect(create_engine(f"sqlite:///{test_db}")).get_table_names())
    declared = set(Base.metadata.tables)
    assert declared <= migrated, f"migration is missing tables: {sorted(declared - migrated)}"

    # Downgrade to base
    command.downgrade(cfg, "base")

    # Re-upgrade to head
    command.upgrade(cfg, "head")
