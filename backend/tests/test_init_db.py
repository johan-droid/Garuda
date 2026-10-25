"""Schema initialization must create every table the app serves from.

`make init-db` and the seed script both go through `app.db.init_db`, which
builds the schema from `Base.metadata`. A model that nothing imports is
invisible to that metadata, so its table is silently missing from a fresh
database - and the failure surfaces later as `no such table` at request time,
not at initialization.

Each check runs in a subprocess with a *clean* module registry, so it sees
only the tables `init_db`'s own imports register. A test that ran in-process
would pass on any new model, because the suite's conftest has already
imported them all.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Runs in a fresh interpreter: import init_db, build a database, report tables.
_PROBE = """
import json, sys
from pathlib import Path
sys.path.insert(0, {backend!r})
from sqlalchemy import create_engine, inspect
from app.db.init_db import init_db
engine = create_engine(f"sqlite:///{db}")
init_db(engine_override=engine)
print(json.dumps(sorted(inspect(engine).get_table_names())))
"""


def _init_db_tables(db_path: Path) -> set[str]:
    """Tables an `init_db` run produces, from a clean interpreter."""
    import json

    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(backend=str(REPO_ROOT / "backend"), db=db_path)],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO_ROOT),
    )
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def test_init_db_creates_the_saved_places_table(tmp_path: Path) -> None:
    """`make init-db` must produce the table the saved-places route reads."""
    tables = _init_db_tables(tmp_path / "init.db")

    assert "saved_places" in tables, (
        f"init_db did not create saved_places. Got: {sorted(tables)}. "
        "Nothing imports app.models.saved_place from a module init_db loads."
    )


def test_init_db_creates_every_table_the_orm_declares(tmp_path: Path) -> None:
    """No ORM-declared table may be missing from an initialized database."""
    import json

    # The full table set, including models init_db's imports do not reach.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, sys; sys.path.insert(0, {backend!r}); "
            "from app.db.session import Base; "
            "import app.models.entities, app.models.saved_place; "
            "print(json.dumps(sorted(Base.metadata.tables)))".format(
                backend=str(REPO_ROOT / "backend")
            ),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO_ROOT),
    )
    declared = set(json.loads(proc.stdout.strip().splitlines()[-1]))

    created = _init_db_tables(tmp_path / "init_all.db")
    assert declared <= created, f"init_db is missing tables: {sorted(declared - created)}"
