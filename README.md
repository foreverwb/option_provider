# options_provider

Decoupled bridge client + ORATS options metrics provider.

## Components

- `bridge_client`: HTTP client for `volatility_analysis` bridge APIs.
- `orats_provider`: ORATS delayed data client and metrics commands.
- `provider.UnifiedProvider`: one-stop interface for bridge + ORATS.
- `api`: optional FastAPI service wrapper.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
pytest
```

## Environment

- `VA_BASE_URL` (default `http://localhost:8668`)
- `ORATS_TOKEN` (required for ORATS endpoints)
