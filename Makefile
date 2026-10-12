.PHONY: help dev up down logs test test-unit test-integration test-e2e lint format \
        migrate migration seed models rag frontend build-frontend check-ephemeral deploy clean

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.yml -f docker-compose.prod.yml

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: up  ## Start the development stack
	$(COMPOSE) logs -f backend

up:  ## Start containers
	$(COMPOSE) up -d

down:  ## Stop containers
	$(COMPOSE) down

logs:  ## Tail all logs
	$(COMPOSE) logs -f

test:  ## Run the whole backend test suite
	$(COMPOSE) exec backend pytest

test-unit:  ## Unit tests only
	$(COMPOSE) exec backend pytest tests/unit -q

test-integration:  ## Integration tests (need the database)
	$(COMPOSE) exec backend pytest tests/integration -q

test-e2e:  ## End-to-end tests
	$(COMPOSE) exec backend pytest tests/e2e -q

lint:  ## Ruff + mypy
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec backend mypy app rule_engine ai_pipeline

format:  ## Ruff format
	$(COMPOSE) exec backend ruff format .

migrate:  ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

migration:  ## Create a migration: make migration m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

seed:  ## Load reference data into the database
	$(COMPOSE) exec backend python ../scripts/seed_database.py

models:  ## Download model weights into backend/models/ (gitignored)
	python scripts/download_models.py

rag:  ## Build the ChromaDB store from data/efsa_pdfs/
	$(COMPOSE) exec backend python ../scripts/ingest_efsa_pdfs.py

frontend:  ## Run the Vite dev server
	cd frontend && npm run dev

build-frontend:  ## Production frontend build
	cd frontend && npm ci && npm run build

check-ephemeral:  ## Verify no photo can survive on disk (Rule 7)
	./scripts/check_ephemeral.sh

deploy:  ## Build and start the production stack
	$(MAKE) build-frontend
	$(COMPOSE_PROD) build
	$(COMPOSE_PROD) up -d
	$(COMPOSE_PROD) exec backend alembic upgrade head
	$(MAKE) check-ephemeral

clean:  ## Remove caches and build artefacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf frontend/dist .pytest_cache .ruff_cache .mypy_cache
