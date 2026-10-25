"""Alembic environment configuration targeting Base.metadata from app.db.session."""

from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import create_engine, pool

from alembic import context

# Ensure backend root is on sys.path if not already
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import application DeclarativeBase, engine, and registered entities
import app.models.entities  # noqa: F401 (registers all entities on Base.metadata)
# Registered explicitly: not reachable from entities, and a metadata built
# without it makes autogenerate silently omit the table.
import app.models.saved_place  # noqa: F401
from app.core.config import settings
from app.db.session import Base, engine as app_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target Base.metadata from app.db.session
target_metadata = Base.metadata


def get_url() -> str:
    """Resolve database URL from app settings or alembic config."""
    url = getattr(settings, "DATABASE_URL", None)
    if url:
        return str(url)
    return str(config.get_main_option("sqlalchemy.url", "sqlite:///garuda_local.db"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Associates a connection from the configured application engine with the context.
    If a custom sqlalchemy.url is passed via alembic config, creates a dedicated engine.
    """
    config_url = config.get_main_option("sqlalchemy.url")
    if config_url and config_url != settings.DATABASE_URL:
        connectable = create_engine(config_url, poolclass=pool.NullPool)
    else:
        connectable = app_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
