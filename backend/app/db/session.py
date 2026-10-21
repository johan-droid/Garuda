"""Database engine and session management.

Uses synchronous SQLAlchemy (the runtime has no `greenlet`, so async ORM
execution is unavailable). The session layer is written to be usable from
synchronous route handlers without leaking sessions.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _engine_kwargs() -> dict:
    """Build engine options appropriate for the configured backend."""
    if settings.is_sqlite:
        return {
            "connect_args": {"check_same_thread": False, "timeout": settings.DB_TIMEOUT},
            "pool_pre_ping": True,
        }
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_TIMEOUT,
        "pool_pre_ping": True,
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    }


engine: Engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
    **_engine_kwargs(),
)


if settings.is_sqlite and settings.DB_ENABLE_SQLITE_FK:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        """Enable foreign key enforcement and WAL for SQLite.

        SQLite disables foreign keys by default, which would silently break the
        referential integrity the schema relies on.
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session.

    The session is always closed, even if the handler raises.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts and background work.

    Commits on success, rolls back on failure.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def healthcheck() -> bool:
    """Return True when the database answers a trivial query."""
    from sqlalchemy import text

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
