# Options Provider

Unified options analysis service integrating **Bridge API** (volatility_analysis) and **ORATS** data sources.

## Architecture

```
options_provider/
├── bridge_client/           # Task 1: Decoupled Bridge API client
│   ├── models.py            # BridgeSnapshot / TermStructureSnapshot
│   ├── client.py            # BridgeClient + AsyncBridgeClient
│   └── micro_templates.py   # Template selection (zero core dependency)
│
├── orats_provider/          # Task 2: ORATS data provider
│   ├── config.py            # API config + field mappings
│   ├── models.py            # 6 data models + 2 result models
│   ├── cache.py             # Thread-safe TTL cache
│   ├── utils.py             # Filtering + grouping utilities
│   ├── client.py            # OratsClient + AsyncOratsClient
│   ├── greeks_exposure/     # GEX/DEX/VEX/Vanna calculator
│   │   ├── calculator.py    # 9 computation functions
│   │   ├── commands.py      # Command pipeline
│   │   └── formatter.py     # Output formatting
│   └── volatility/          # Skew/Term/Surface analyzer
│       ├── analyzer.py      # Analysis functions
│       ├── commands.py      # Command pipeline
│       └── formatter.py     # Output formatting
│
├── provider/                # Task 3: Unified provider
│   └── unified.py           # UnifiedProvider (fault-tolerant)
│
├── api/                     # Task 3: FastAPI service
│   ├── main.py              # App + lifespan + /full endpoint
│   ├── dependencies.py      # Shared provider singleton
│   └── routes/
│       ├── bridge.py        # /api/v1/bridge/*
│       ├── greeks.py        # /api/v1/greeks/{cmd}/{sym}
│       └── volatility.py    # /api/v1/volatility/{cmd}/{sym}
│
└── tests/                   # 90 tests
    ├── conftest.py          # Shared fixtures + synthetic data
    ├── test_models.py       # Serialization + micro-template
    ├── test_client.py       # HTTP mock + cache + utils
    ├── test_greeks.py       # GEX/DEX/VEX/Vanna formulas
    └── test_volatility.py   # Skew/term/surface analysis
```

## Quick Start

```bash
pip install -r requirements.txt

# Run tests
PYTHONPATH=. pytest tests/ -v

# Start API server
ORATS_TOKEN=your_token BRIDGE_URL=http://localhost:8668 uvicorn api.main:app --port 8000
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/bridge/snapshot/{symbol}` | GET | Bridge snapshot |
| `/api/v1/bridge/batch` | POST | Batch snapshots |
| `/api/v1/bridge/micro-template/{symbol}` | GET | Micro-template selection |
| `/api/v1/greeks/{command}/{symbol}` | GET | Greeks exposure (9 commands) |
| `/api/v1/volatility/{command}/{symbol}` | GET | Vol analysis (3 commands) |
| `/api/v1/full/{symbol}` | GET | Comprehensive analysis |
| `/health` | GET | Health check |

## Greeks Commands

`gex`, `net_gex`, `gex_distribution`, `gex_3d`, `dex`, `net_dex`, `vex`, `net_vex`, `vanna`

## Volatility Commands

`skew`, `term`, `surface`
