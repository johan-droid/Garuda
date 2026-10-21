SHELL := /bin/bash
.PHONY: dev test lint build clean help init-db seed dev-backend dev-frontend test-backend test-frontend

help:
	@echo "🦅 Garuda Development Commands:"
	@echo "  make init-db        - Initialize the SQLite database schema"
	@echo "  make seed           - Populate local database with Khordha pilot dataset"
	@echo "  make dev-backend    - Start FastAPI backend server on port 8000"
	@echo "  make dev-frontend   - Start Vite frontend development server on port 5173"
	@echo "  make test           - Run both backend and frontend test suites"
	@echo "  make lint           - Run linting and type checking on backend"
	@echo "  make build          - Build frontend production bundle"
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

test-backend:
	PYTHONPATH=backend pytest backend

test-api: test-backend

test: test-backend

lint:
	PYTHONPATH=backend mypy backend/app

build:
	cd frontend && npm run build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
