BACKEND_PORT ?= 8000

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend test-integration analyze \
        lint lint-backend lint-frontend fmt

help:
	@echo "make install   Install backend (uv) and frontend (pnpm) dependencies"
	@echo "make dev       Run backend (:$(BACKEND_PORT)) and frontend (Vite) together"
	@echo "make test      Fast tests: pytest (fake engine) + Vitest"
	@echo "make test-integration  Tests against the real Stockfish (reduced search times)"
	@echo "make analyze PGN=file.pgn  Analyse a PGN with Stockfish and print the review"
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
	cd backend && uv run pytest -m "not integration"

test-integration:
	cd backend && uv run pytest -m integration

test-frontend:
	cd frontend && pnpm test

analyze:
	@test -n "$(PGN)" || (echo "Usage: make analyze PGN=path/to/game.pgn" && exit 1)
	cd backend && uv run python -m app.analysis.cli "$(abspath $(PGN))" $(ARGS)

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format
