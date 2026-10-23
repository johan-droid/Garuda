"""Tests for Alembic database migrations."""

from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_heads_single_head() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ini_path = repo_root / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0001_initial_schema"


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ini_path = repo_root / "alembic.ini"
    test_db = tmp_path / "test_migration.db"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db}")

    # Upgrade to head
    command.upgrade(cfg, "head")

    # Downgrade to base
    command.downgrade(cfg, "base")

    # Re-upgrade to head
    command.upgrade(cfg, "head")
