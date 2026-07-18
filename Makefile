SHELL := /bin/sh

TEST_DATABASE_URL := postgresql+psycopg://incidentpilot:incidentpilot@postgres:5432/incidentpilot_test
OLLAMA_MODEL ?= qwen2.5:3b

.PHONY: help setup up down logs migrate seed reindex test eval demo status

help:
	@echo "IncidentPilot AI commands"
	@echo ""
	@echo "  make setup    First-time setup and migrations"
	@echo "  make up       Start existing containers without rebuilding"
	@echo "  make down     Stop containers without deleting volumes"
	@echo "  make migrate  Apply development database migrations"
	@echo "  make seed     Seed services, runbooks, logs, metrics, and RCA demo data"
	@echo "  make reindex  Rebuild all document embeddings"
	@echo "  make test     Run isolated test suite"
	@echo "  make eval     Run retrieval evaluation and update README"
	@echo "  make demo     Run the end-to-end local RCA demo"
	@echo "  make logs     Follow API logs"
	@echo "  make status   Show container and Ollama status"

setup:
	@command -v ollama >/dev/null 2>&1 || \
		(echo "Ollama is required. Install and start Ollama first."; exit 1)
	@ollama list | grep -q "$(OLLAMA_MODEL)" || ollama pull "$(OLLAMA_MODEL)"
	docker compose up -d --build
	docker compose exec -T api alembic upgrade head
	docker compose exec -T postgres sh -lc \
		'createdb -U incidentpilot incidentpilot_test 2>/dev/null || true'
	docker compose exec -T api sh -lc \
		'DATABASE_URL=$(TEST_DATABASE_URL) alembic upgrade head'
	@echo ""
	@echo "Setup complete."
	@echo "Run: make seed"
	@echo "Then: make demo"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec -T api alembic upgrade head

seed:
	docker compose exec -T api python scripts/seed.py
	docker compose exec -T api python scripts/seed_day3_runbooks.py
	docker compose exec -T api python scripts/seed_day9_rca.py

reindex:
	docker compose exec -T api python scripts/reindex_documents.py

test:
	docker compose exec -T postgres sh -lc \
		'createdb -U incidentpilot incidentpilot_test 2>/dev/null || true'
	docker compose exec -T api sh -lc \
		'DATABASE_URL=$(TEST_DATABASE_URL) alembic upgrade head'
	docker compose exec -T api sh -lc \
		'TEST_DATABASE_URL=$(TEST_DATABASE_URL) python -m pytest -q'

eval:
	docker compose exec -T api python scripts/seed_day3_runbooks.py
	docker compose exec -T api python scripts/reindex_documents.py
	docker compose exec -T api \
		python scripts/run_retrieval_evals.py --update-readme

demo:
	sh scripts/demo_day10.sh

status:
	docker compose ps
	@echo ""
	@ollama ps || true