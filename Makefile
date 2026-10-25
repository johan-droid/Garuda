SHELL := /bin/bash
REGION ?= odisha-test
.PHONY: dev dev-ports test lint build clean help init-db seed dev-backend dev-frontend test-backend test-frontend test-imagery test-imagery-live imagery-setup imagery-build imagery-validate imagery-clean

help:
	@echo "🦅 Garuda Development Commands:"
	@echo "  make init-db        - Initialize the SQLite database schema"
	@echo "  make seed           - Populate local database with Khordha pilot dataset"
	@echo "  make dev            - Start backend and frontend together (Ctrl-C stops both)"
	@echo "  make dev-backend    - Start FastAPI backend server on port 8000"
	@echo "  make dev-frontend   - Start Vite frontend development server on port 5173"
	@echo "  make test           - Run backend test suite"
	@echo "  make test-frontend  - Run frontend component tests"
	@echo "  make lint           - Run linting and type checking on backend"
	@echo "  make build          - Build frontend production bundle"
	@echo "  make test-imagery   - Run offline Sentinel-2 pipeline tests"
	@echo "  make imagery-build  - Build the region mosaic (REGION=odisha-test)"
	@echo "  make docker-up       - Build the backend image and start the container stack"
	@echo "  make docker-down     - Stop the container stack (keeps the data volume)"
	@echo "  make clean          - Remove cache and build artifacts"

init-db:
	PYTHONPATH=backend python3 -m app.db.init_db

seed:
	PYTHONPATH=backend python3 backend/seed_pilot.py

dev-backend:
	PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-api: dev-backend

dev-frontend:
	cd frontend && npm run dev

dev-web: dev-frontend

# The dev servers must always come back on the ports the Vite proxy and the
# README point at, so anything still holding them is stopped first instead of
# letting Vite drift to 5174 and silently break the proxy target.
dev-ports:
	@for port in 8000 5173; do \
		pids=$$(ss -ltnpH "sport = :$$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u | tr '\n' ' '); \
		if [ -n "$$pids" ]; then \
			echo "→ port $$port is taken (pid $$(echo $$pids)) — stopping it"; \
			kill $$pids 2>/dev/null || true; \
			sleep 1; \
			kill -9 $$pids 2>/dev/null || true; \
		fi; \
	done

# Both servers in one terminal; Ctrl-C stops both. The trap covers the case
# where the interrupt reaches only make (e.g. a wrapped supervisor).
dev: dev-ports
	@echo "🦅 backend http://localhost:8000  ·  frontend http://localhost:5173  ·  Ctrl-C stops both"
	-@PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload & \
	api=$$!; \
	( cd frontend && npm run dev ) & \
	web=$$!; \
	trap 'kill $$api $$web 2>/dev/null' INT TERM; \
	wait

test-backend:
	PYTHONPATH=backend pytest backend

test-api: test-backend

test-frontend:
	cd frontend && npm test

test: test-backend

lint:
	PYTHONPATH=backend mypy backend/app

build:
	cd frontend && npm run build

imagery-setup:
	python3 -m pip install --user -r tools/imagery/requirements.txt

test-imagery:
	python3 -m pytest tools/imagery/tests -q

test-imagery-live:
	GARUDA_NETWORK_TESTS=1 python3 -m pytest tools/imagery/tests/test_live_sources.py -q

imagery-build:
	python3 tools/imagery/build_composite.py --config tools/imagery/regions/$(REGION).json --cache-dir .cache/imagery

imagery-validate:
	python3 tools/imagery/build_composite.py --config tools/imagery/regions/$(REGION).json --validate

imagery-clean:
	rm -rf "frontend/public/imagery/$(REGION)"
	@echo "Removed generated imagery tiles only; source data and cache were not touched."

# Container stack. `docker build` runs first because this host's buildx (v0.14)
# is older than the version `docker compose build` requires (0.17); the image is
# named in docker-compose.yml, so compose runs it instead of rebuilding.
docker-build:
	docker build -t garuda-api:latest .

docker-up: docker-build
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f backend

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
