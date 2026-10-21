SHELL := /bin/bash
.PHONY: dev test lint build clean help

help:
	@echo "Garuda Development Commands:"
	@echo "  make dev         - Start both backend and frontend in dev mode"
	@echo "  make test        - Run backend and frontend test suites"
	@echo "  make lint        - Run linting and type checking"
	@echo "  make build       - Build frontend and verify packaging"
	@echo "  make clean       - Remove cache, build artifacts, and pyc files"

dev-api:
	PYTHONPATH=services/api .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-web:
	cd apps/web && npm run dev

test-api:
	PYTHONPATH=services/api .venv/bin/pytest services/api

test: test-api

lint:
	PYTHONPATH=services/api .venv/bin/mypy services/api/app || true

build:
	cd apps/web && npm run build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
