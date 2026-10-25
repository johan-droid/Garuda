"""Shared fixtures for the Garuda API test suite."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Point the app at a unique temporary database directory and a known admin key
# before the application package is imported.
_TEST_DIR = tempfile.TemporaryDirectory(prefix="garuda_test_")
_TEST_DB = Path(_TEST_DIR.name) / "garuda_test.db"

os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ADMIN_API_KEY"] = "test-admin-key-0123456789"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-0123456789"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_KEY = "test-admin-key-0123456789"


def _reset_database() -> None:
    """Delete every row so each test starts from a known state."""
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Create the schema once for the whole test session."""
    import app.models.entities  # noqa: F401  (registers the mappers)

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        _TEST_DIR.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolated_breakers() -> Iterator[None]:
    """Breakers are process-wide (as the cache is), so reset them per test.

    Several adapter tests deliberately drive an upstream into failure; without
    this, one test's accumulated failures would open a breaker and change what
    a later test observes.
    """
    from app.services.circuit import reset_breakers

    reset_breakers()
    yield
    reset_breakers()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Return a TestClient bound to the application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db() -> Iterator[Session]:
    """Return a session with the schema created, truncated between tests."""
    import app.models.entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        _reset_database()


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    """Authorization header for the administrative routes."""
    return {"Authorization": f"Bearer {ADMIN_KEY}"}
