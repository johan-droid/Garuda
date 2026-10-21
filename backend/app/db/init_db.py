"""Database schema initialization.

Creates all tables registered with SQLAlchemy DeclarativeBase metadata.
"""

import sys
from pathlib import Path

# Ensure services/api is on sys.path if invoked as standalone script
API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlalchemy.engine import Engine

import app.models.entities  # noqa: F401  (registers all entity mappings)
from app.db.session import Base, engine


def init_db(engine_override: Engine | None = None) -> None:
    """Create all tables in the configured database."""
    target_engine = engine_override or engine
    Base.metadata.create_all(bind=target_engine)


if __name__ == "__main__":
    init_db()
    print("Database schema initialized successfully.")
