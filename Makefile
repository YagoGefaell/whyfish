BACKEND_PORT ?= 8000

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend \
        lint lint-backend lint-frontend fmt

help:
	@echo "make install   Install backend (uv) and frontend (pnpm) dependencies"
	@echo "make dev       Run backend (:$(BACKEND_PORT)) and frontend (Vite) together"
	@echo "make test      Run pytest + Vitest"
	@echo "make lint      ruff + mypy --strict, ESLint + Prettier + tsc"
	@echo "make fmt       Auto-format backend and frontend"

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	@$(MAKE) --no-print-directory -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT)

dev-frontend:
	cd frontend && BACKEND_URL=http://127.0.0.1:$(BACKEND_PORT) pnpm dev

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && pnpm test

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format
