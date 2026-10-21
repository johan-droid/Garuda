SHELL := /bin/bash
.PHONY: dev dev-api test seed init-db

dev:
	uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-api: dev

test:
	pytest .

init-db:
	python3 -m app.db.init_db

seed:
	python3 seed_pilot.py
