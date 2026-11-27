BACKEND_PORT ?= 8000

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend test-integration test-e2e install-e2e analyze explain-report why-report stats-report \
        lint lint-backend lint-frontend fmt

help:
	@echo "make install   Install backend (uv) and frontend (pnpm) dependencies"
	@echo "make dev       Run backend (:$(BACKEND_PORT)) and frontend (Vite) together"
	@echo "make test      Fast tests: pytest (fake engine) + Vitest"
	@echo "make test-integration  Tests against the real Stockfish (reduced search times)"
	@echo "make test-e2e  Browser tests (Playwright) on their own DB and ports; screenshots in frontend/e2e-artifacts/"
	@echo "make analyze PGN=file.pgn  Analyse a PGN with Stockfish and print the review"
	@echo "DATABASE_URL=sqlite:////tmp/x.db make explain-report  Explanations review report (HTML)"
	@echo "DATABASE_URL=sqlite:////tmp/x.db make why-report      'Ver por qué' review report (HTML)"
	@echo "DATABASE_URL=sqlite:////tmp/x.db make stats-report    Statistics report (HTML)"
	@echo "make lint      ruff + mypy --strict, ESLint + Prettier + tsc"
	@echo "make fmt       Auto-format backend and frontend"

install:
	cd backend && uv sync
	cd frontend && pnpm install
	@echo "For browser tests also run: make install-e2e"

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

test-e2e:
	cd frontend && pnpm exec playwright test

install-e2e:
	cd frontend && pnpm exec playwright install chromium

analyze:
	@test -n "$(PGN)" || (echo "Usage: make analyze PGN=path/to/game.pgn" && exit 1)
	cd backend && uv run python -m app.analysis.cli "$(abspath $(PGN))" $(ARGS)

explain-report:
	@test -n "$(DATABASE_URL)" || (echo "Usage: DATABASE_URL=sqlite:////tmp/x.db make explain-report [OUT=file.html]" && exit 1)
	cd backend && uv run python -m app.explain.report --out "$(abspath $(or $(OUT),docs/reports/explanations-fase4.html))"

why-report:
	@test -n "$(DATABASE_URL)" || (echo "Usage: DATABASE_URL=sqlite:////tmp/x.db make why-report [OUT=file.html]" && exit 1)
	cd backend && uv run python -m app.explain.why_report --out "$(abspath $(or $(OUT),docs/reports/why-fase5.html))"

stats-report:
	@test -n "$(DATABASE_URL)" || (echo "Usage: DATABASE_URL=sqlite:////tmp/x.db make stats-report [OUT=file.html]" && exit 1)
	cd backend && uv run python -m app.stats.report --out "$(abspath $(or $(OUT),docs/reports/stats-fase6b.html))"

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy

lint-frontend:
	cd frontend && pnpm lint && pnpm typecheck

fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && pnpm format
