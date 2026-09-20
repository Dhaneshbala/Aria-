# ─────────────────────────────────────────────────────────────
#  Study Buddy — AI Study Assistant  |  make targets
#  Test / verification convenience targets.
# ─────────────────────────────────────────────────────────────

SHELL := /bin/bash
BACKEND := $(CURDIR)/backend

# Absolute python path: the project venv when it has deps, else system python3.
PY := $(shell (venv/bin/python -c 'import pytest' 2>/dev/null && echo "$(CURDIR)/venv/bin/python") || echo "$$(command -v python3)")

.PHONY: help deps test fast verify verify-live check coverage lint

help: ## Show targets
	@echo "Targets:"
	@echo "  make deps       — install backend requirements into venv"
	@echo "  make test       — full automated suite (incl. E2E; Ollama up = live AI)"
	@echo "  make fast       — quick deterministic unit suite (no live AI)"
	@echo "  make coverage   — run tests with HTML coverage report"
	@echo "  make lint       — run ruff linter on backend"
	@echo "  make verify     — deterministic + accuracy drift-tracker"
	@echo "  make verify-live — 12 live Ollama feature-accuracy checks"
	@echo "                    (needs gemma4:e4b-mlx + nomic-embed-text)"

deps: ## Install backend requirements into the venv
	@test -d venv || python3 -m venv venv
	venv/bin/pip install -r $(BACKEND)/requirements.txt

test: ## Full automated suite (live E2E runs when Ollama is up)
	cd $(BACKEND) && $(PY) -m pytest -q

fast: ## Deterministic unit suite, no live AI
	cd $(BACKEND) && $(PY) -m pytest -q --ignore=tests/test_e2e_features.py

coverage: ## Run tests with HTML coverage report
	cd $(BACKEND) && $(PY) -m pytest -q --ignore=tests/test_e2e_features.py --cov=services --cov=routers --cov=config --cov=models --cov-report=term-missing --cov-report=html:htmlcov
	@echo "Coverage report: $(BACKEND)/htmlcov/index.html"

lint: ## Run ruff linter on backend
	cd $(BACKEND) && $(PY) -m ruff check . --fix
	cd $(BACKEND) && $(PY) -m ruff format .

verify: ## Deterministic + accuracy drift-tracker
	cd $(BACKEND) && $(PY) -m pytest -q tests/test_accuracy_deterministic.py

verify-live: ## 12 live feature-accuracy checks against local Ollama
	cd $(BACKEND) && $(PY) scripts/feature_accuracy_harness.py
	cd $(BACKEND) && $(PY) scripts/feature_accuracy_harness2.py

check: test ## Alias for the full suite