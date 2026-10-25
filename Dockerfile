# Garuda backend image.
#
# Single stage with a dependency layer separated from the application layer, so
# editing application code does not reinstall dependencies. Non-editable install
# on purpose: the package goes into site-packages, so no PYTHONPATH is needed and
# the image does not carry the build context's paths.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # The default SQLite path resolves next to the installed package, which is
    # root-owned in site-packages. Point it at the mounted volume instead.
    GARUDA_DATABASE_URL=sqlite:////data/garuda.db

WORKDIR /app

# The whole package directory has to be present before installing: with only
# `pyproject.toml` copied, setuptools finds no `app/` and installs an empty
# distribution (an `app` that is not there, which surfaces at runtime as
# `ModuleNotFoundError`). Dependency-only caching is not available while the
# package lives beside its own manifest; splitting the dependencies into a
# `requirements.txt` installed in a separate layer is the upgrade path.
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend

# Data directory must be writable by the unprivileged user below.
RUN useradd --create-home --uid 10001 garuda \
    && mkdir -p /data \
    && chown -R garuda:garuda /data /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER garuda

EXPOSE 8000

# exec'd so uvicorn receives SIGTERM directly and can close in-flight requests.
ENTRYPOINT ["docker-entrypoint.sh"]
