# ──────────────────────────────────────────────────────────────────────────────
# Options Provider — Makefile
# ──────────────────────────────────────────────────────────────────────────────
# Quick reference:
#   make serve          Start API server (port 9988)
#   make dev            Start in dev mode (auto-reload)
#   make test           Run all tests
#   make test-greeks    Run only Greeks tests
#   make test-vol       Run only Volatility tests
#   make test-cov       Run tests with coverage
#   make health         Check if server is running
#   make routes         Show all API routes
#   make install        Install dependencies
#   make clean          Clean caches
# ──────────────────────────────────────────────────────────────────────────────

PYTHON   ?= python3
PORT     ?= 9988
HOST     ?= 0.0.0.0
WORKERS  ?= 1

# Colors
_cyan    := \033[96m
_green   := \033[92m
_reset   := \033[0m

.PHONY: help serve dev test test-greeks test-vol test-models test-client \
        test-cov health routes install clean lint fmt

# ── Default target ──────────────────────────────────────────────────────
help:  ## Show this help
	@echo ""
	@echo "  $(_cyan)Options Provider$(_reset) — Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(_green)make %-16s$(_reset) %s\n", $$1, $$2}'
	@echo ""

# ── Server ──────────────────────────────────────────────────────────────
serve:  ## Start API server (PORT=9988)
	@$(PYTHON) cli.py serve --port $(PORT) --host $(HOST) --workers $(WORKERS)

dev:  ## Start in dev mode (auto-reload)
	@$(PYTHON) cli.py serve --port $(PORT) --reload --log-level debug

run: serve  ## Alias for serve

# ── Testing ─────────────────────────────────────────────────────────────
test:  ## Run all tests
	@PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --tb=short

test-greeks:  ## Run Greeks exposure tests
	@PYTHONPATH=. $(PYTHON) -m pytest tests/test_greeks.py -v

test-vol:  ## Run Volatility analysis tests
	@PYTHONPATH=. $(PYTHON) -m pytest tests/test_volatility.py -v

test-models:  ## Run model/serialization tests
	@PYTHONPATH=. $(PYTHON) -m pytest tests/test_models.py -v

test-client:  ## Run client/cache tests
	@PYTHONPATH=. $(PYTHON) -m pytest tests/test_client.py -v

test-cov:  ## Run tests with coverage report
	@PYTHONPATH=. $(PYTHON) -m pytest tests/ -v --cov=. --cov-report=term-missing --tb=short

# ── Utilities ───────────────────────────────────────────────────────────
health:  ## Check server health
	@$(PYTHON) cli.py health --port $(PORT)

routes:  ## List all API routes
	@PYTHONPATH=. $(PYTHON) cli.py routes

# ── Setup ───────────────────────────────────────────────────────────────
install:  ## Install Python dependencies
	@$(PYTHON) -m pip install -r requirements.txt
	@echo "$(_green)✓$(_reset) Dependencies installed"

clean:  ## Clean caches and temp files
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .coverage htmlcov/ .mypy_cache/
	@echo "$(_green)✓$(_reset) Cleaned"
