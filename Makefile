# ─────────────────────────────────────────────────────────────
#  ARIA — AI Study Assistant  |  make targets
#  Test / verification convenience targets.
# ─────────────────────────────────────────────────────────────

SHELL := /bin/bash
BACKEND := $(CURDIR)/backend

# Absolute python path: the project venv (.venv, then legacy venv) when it has
# deps, else system python3.
PY := $(shell (.venv/bin/python -c 'import pytest' 2>/dev/null && echo "$(CURDIR)/.venv/bin/python") || (venv/bin/python -c 'import pytest' 2>/dev/null && echo "$(CURDIR)/venv/bin/python") || echo "$$(command -v python3)")

.PHONY: help deps test fast cov audit dead verify verify-live check

help: ## Show targets
	@echo "Targets:"
	@echo "  make deps       — install backend requirements into venv"
	@echo "  make test       — full automated suite (incl. E2E; Ollama up = live AI)"
	@echo "  make fast       — quick deterministic unit suite (no live AI)"
	@echo "  make verify     — deterministic + accuracy drift-tracker"
	@echo "  make verify-live — 12 live Ollama feature-accuracy checks"
	@echo "                    (needs gemma3:12b + nomic-embed-text)"

deps: ## Install backend requirements into the venv
	@test -d venv || python3 -m venv venv
	venv/bin/pip install -r $(BACKEND)/requirements.txt

test: ## Full automated suite (live E2E runs when Ollama is up)
	cd $(BACKEND) && $(PY) -m pytest -q

fast: ## Deterministic unit suite, no live AI
	cd $(BACKEND) && $(PY) -m pytest -q --ignore=tests/test_e2e_features.py

cov: ## Same suite + coverage report (finds untested code)
	cd $(BACKEND) && $(PY) -m pytest -q --ignore=tests/test_e2e_features.py \
		--cov=. --cov-report=term-missing --cov-fail-under=40

audit: ## Scan installed Python deps for known CVEs
	# ChromaDB IDs ignored: tenant/RBAC server CVEs, not exploitable with
	# embedded PersistentClient (see requirements.txt note). Re-check yearly.
	SSL_CERT_FILE=~/.config/zscaler-ca-bundle.pem REQUESTS_CA_BUNDLE=~/.config/zscaler-ca-bundle.pem $(PY) -m pip_audit \
		--ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 \
		--ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815

dead: ## Find dead code in app sources (tests excluded: fixtures/idioms trip it)
	cd $(BACKEND) && $(PY) -m vulture services routers models main.py config --min-confidence 80

verify: ## Deterministic + accuracy drift-tracker
	cd $(BACKEND) && $(PY) -m pytest -q tests/test_accuracy_deterministic.py

verify-live: ## 12 live feature-accuracy checks against local Ollama
	cd $(BACKEND) && $(PY) scripts/feature_accuracy_harness.py
	cd $(BACKEND) && $(PY) scripts/feature_accuracy_harness2.py

check: test ## Alias for the full suite
