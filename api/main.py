"""
FastAPI application — options_provider service.

Routes:
  /api/v1/bridge/*           — Bridge snapshot + micro template
  /api/v1/greeks/{cmd}/{sym} — 9 Greeks exposure commands
  /api/v1/volatility/{cmd}/{sym} — 3 Volatility commands
  /api/v1/full/{symbol}      — Comprehensive analysis
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from orats_provider import OratsConfig
from provider.unified import UnifiedProvider
from api.dependencies import set_provider, clear_provider, get_provider
from api.routes.bridge import router as bridge_router
from api.routes.greeks import router as greeks_router
from api.routes.volatility import router as volatility_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    config = OratsConfig.from_env()
    bridge_url = os.environ.get("BRIDGE_URL", "http://localhost:8668")
    provider = UnifiedProvider(bridge_url=bridge_url, orats_config=config)
    set_provider(provider)
    yield
    clear_provider()


app = FastAPI(
    title="Options Provider API",
    version="1.0.0",
    description="Unified options analysis: Bridge + ORATS Greeks + Volatility",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route groups
app.include_router(bridge_router)
app.include_router(greeks_router)
app.include_router(volatility_router)


# ── Full analysis endpoint ──────────────────────────────────────────────

@app.get("/api/v1/full/{symbol}")
async def full_analysis(
    symbol: str,
    greeks: Optional[str] = Query(None, description="Comma-separated Greeks commands"),
    vol: Optional[str] = Query(None, description="Comma-separated Vol commands"),
) -> Dict[str, Any]:
    """Run comprehensive analysis (fault-tolerant)."""
    try:
        provider = get_provider()
        g_cmds = greeks.split(",") if greeks else None
        v_cmds = vol.split(",") if vol else None
        return provider.full_analysis(symbol, greeks_commands_list=g_cmds, vol_commands_list=v_cmds)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health check ────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
