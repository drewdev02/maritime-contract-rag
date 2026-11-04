# Desarrollo local: infra (db, redis, jaeger) en Docker; api, worker y frontend en bare metal.
# Requiere .env y .env.local en la raiz. Cada servicio largo va en su propia terminal.

SHELL := /bin/bash
COMPOSE := docker compose -f docker-compose.dev.yml
MOCK ?=

# Carga .env y luego .env.local (que pisa los hostnames de Docker) y fija STORAGE_PATH.
LOAD_ENV = set -a; . ./.env; . ./.env.local; set +a; \
	export STORAGE_PATH="$(CURDIR)/.storage/contracts"; mkdir -p "$$STORAGE_PATH"; \
	if [ -n "$(MOCK)" ]; then export LLM_PROVIDER=mock EMBEDDING_PROVIDER=mock; fi

.DEFAULT_GOAL := help
.PHONY: help infra-up infra-tracing infra-down infra-logs infra-ps install migrate api worker flower web test-back test-front

help: ## Muestra esta ayuda
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

infra-up: ## Levanta db y redis en Docker
	$(COMPOSE) up -d --wait db redis

infra-tracing: ## Levanta db, redis y jaeger (UI en :16686)
	$(COMPOSE) --profile tracing up -d --wait

infra-down: ## Detiene la infra (conserva los datos)
	$(COMPOSE) --profile tracing down

infra-logs: ## Sigue los logs de la infra
	$(COMPOSE) --profile tracing logs -f

infra-ps: ## Estado de los contenedores
	$(COMPOSE) --profile tracing ps

install: ## Instala dependencias de backend (uv) y frontend (bun)
	cd backend && uv sync
	cd frontend && bun install

migrate: ## Aplica migraciones de Alembic
	$(LOAD_ENV); cd backend && uv run alembic upgrade head

api: ## FastAPI con recarga en :8000 (MOCK=1 para proveedores mock)
	$(LOAD_ENV); export OTEL_SERVICE_NAME=maritime-api; cd backend && uv run uvicorn maritime.main:app --reload --port $${API_PORT:-8000}

worker: ## Worker de Celery, pool solo (prefork falla en macOS); MOCK=1 para mocks
	$(LOAD_ENV); export OTEL_SERVICE_NAME=maritime-worker; cd backend && uv run celery -A maritime.infrastructure.celery.celery_app worker -l info -P solo

flower: ## Flower (colas y tareas de Celery) en 127.0.0.1:5555, con auth basica
	$(LOAD_ENV); \
	if [ -z "$$FLOWER_BASIC_AUTH" ]; then \
		export FLOWER_BASIC_AUTH="admin:$$(openssl rand -hex 8)"; \
		echo "Flower: usuario:clave = $$FLOWER_BASIC_AUTH (define FLOWER_BASIC_AUTH en .env para fijarla)"; \
	fi; \
	cd backend && uv run celery -A maritime.infrastructure.celery.celery_app flower --address=127.0.0.1 --port=$${FLOWER_PORT:-5555}

web: ## Frontend Vite con proxy al API local
	$(LOAD_ENV); cd frontend && bun run dev

test-back: ## Tests del backend
	$(LOAD_ENV); cd backend && uv run pytest

test-front: ## Tests del frontend
	cd frontend && bun run test
