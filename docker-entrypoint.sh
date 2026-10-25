#!/bin/sh
# Container entrypoint: create the schema, seed it once, then serve.
#
# The app does not create its own tables at startup - `create_app()`'s lifespan
# only configures logging - so a container started against an empty volume would
# serve 500s from every route that touches the database. `init_db()` is
# `create_all`, which is a no-op on an existing schema, so this is safe to run on
# every start.
#
# Seeding is idempotent: `seed_pilot` writes with `session.merge`, so re-running
# it upserts rather than duplicating.
set -eu

DB_URL="${GARUDA_DATABASE_URL:-sqlite:////data/garuda.db}"
SEED_ON_START="${SEED_ON_START:-true}"

echo "→ database: ${DB_URL}"

echo "→ creating schema"
python -m app.db.init_db

if [ "${SEED_ON_START}" = "true" ]; then
  echo "→ seeding pilot data (set SEED_ON_START=false to skip)"
  # Run by path: `seed_pilot.py` is a standalone script, not part of the `app`
  # package, so it is not on the module path after install.
  python /app/backend/seed_pilot.py
else
  echo "→ skipping seed"
fi

echo "→ starting uvicorn on 0.0.0.0:8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
