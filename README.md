# Options Provider

Unified options analysis service integrating **Bridge API** (volatility_analysis) and **ORATS** data sources.

## Architecture

```
options_provider/
├── start.sh                 # ⚡ One-command launcher (bash)
├── cli.py                   # ⚡ Unified CLI entry point (python)
├── Makefile                 # ⚡ Quick make commands
├── pyproject.toml           # ⚡ Modern packaging + entry points
├── .env.example             # ⚡ Environment template
│
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

### 1. One-Command Setup

```bash
./start.sh setup              # Install deps + create .env (interactive)
# or
./start.sh                    # Interactive menu (auto-detects first run)
```

### 2. Start Server

```bash
# start.sh (recommended)
./start.sh serve              # Foreground server (0.0.0.0:9988)
./start.sh dev                # Dev mode (auto-reload)
./start.sh start-bg           # Background daemon
PORT=9000 ./start.sh serve    # Custom port

# make
make serve                    # Same as ./start.sh serve
make dev                      # Same as ./start.sh dev

# cli.py
python cli.py serve -p 9000   # Custom port
python cli.py s --reload      # Short alias + reload
```

### 3. Run Tests

```bash
./start.sh test               # All tests
./start.sh test -k greeks     # Filter by name
make test                     # All tests
make test-greeks              # Only Greeks tests
make test-cov                 # Tests + coverage report
```

### 4. Direct CLI Queries (No Server Needed)

```bash
# start.sh
./start.sh greeks gex AAPL
./start.sh vol skew SPY
./start.sh full TSLA

# cli.py (more options)
python cli.py greeks gex AAPL --dte-max 60
python cli.py vol term QQQ --target-dte 60
python cli.py full TSLA --greeks gex,vanna --vol skew,term
```

### 5. Server Management

```bash
./start.sh start-bg           # Start as background daemon
./start.sh status             # Check server status
./start.sh logs               # Tail server logs
./start.sh health             # HTTP health check
./start.sh stop               # Stop background server
```

## CLI Reference

```
./start.sh <command> [args]

Server:
  serve   (s, run)         Start API server (foreground)
  dev     (d)              Dev mode with auto-reload
  start-bg (bg)            Start server in background
  stop                     Stop background server
  status  (st)             Show server status
  logs                     Tail server logs
  health  (h)              HTTP health check

Testing:
  test    (t)              Run all tests
  test    -k <filter>      Run filtered tests

Offline Queries:
  greeks  (g) <cmd> <sym>  Greeks exposure command
  vol     (v) <cmd> <sym>  Volatility analysis command
  full    (f) <sym>        Full analysis

Setup:
  setup   (install)        Install deps + init .env
  clean                    Clean caches and temp files
  routes                   List all API routes

Environment (override via .env or shell):
  PORT=9988   HOST=0.0.0.0   WORKERS=1   LOG_LEVEL=info

Make Targets:
  make serve    Start server          make test-greeks   Greeks tests only
  make dev      Dev mode (reload)     make test-vol      Vol tests only
  make test     All tests             make test-cov      Tests + coverage
  make health   Health check          make routes        List routes
  make install  Install deps          make clean         Clean caches
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ORATS_TOKEN` | Yes* | — | ORATS API token (* for Greeks/Vol) |
| `BRIDGE_URL` | No | `http://localhost:8668` | Bridge API URL |
| `ORATS_BASE_URL` | No | `https://api.orats.io/datav2` | ORATS API base URL |

The CLI auto-loads `.env` files — just copy `.env.example` to `.env` and fill in your tokens.

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
