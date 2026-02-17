"""
FastAPI application — options_provider service.

Routes:
  /api/v1/bridge/*           — Bridge snapshot + micro template
  /api/v1/greeks/{cmd}/{sym} — 9 Greeks exposure commands
  /api/v1/volatility/{cmd}/{sym} — 3 Volatility commands
  /api/v1/full/{symbol}      — Comprehensive analysis
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any, Dict, List, Optional

import fastapi
from fastapi import FastAPI, HTTPException, Query, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware

from orats_provider import OratsConfig
from provider.unified import UnifiedProvider
from api.dependencies import set_provider, clear_provider, get_provider
from api.routes.bridge import router as bridge_router
from api.routes.greeks import router as greeks_router
from api.routes.volatility import router as volatility_router

_SOURCE_LABELS = {
    "swing": "波段",
}
_CUSTOM_SOURCE_LOG_PATHS = {"/api/bridge/batch"}
_access_logger = logging.getLogger("options_provider.access")


def _configure_access_logger() -> None:
    """Ensure custom access logger is visible in terminal output."""
    _access_logger.setLevel(logging.INFO)
    _access_logger.propagate = False
    if not _access_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        _access_logger.addHandler(handler)


def _normalize_source(source: Optional[str]) -> Optional[str]:
    if source is None:
        return None
    normalized = source.strip()
    if not normalized:
        return None
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()
    return normalized or None


def _source_log_tag(source: Optional[str]) -> str:
    normalized = (_normalize_source(source) or "swing").lower()
    label = _SOURCE_LABELS.get(normalized, normalized)
    return f"['{label}']"


async def _extract_source_from_request(request: Request) -> Optional[str]:
    source = _normalize_source(request.query_params.get("source"))
    if source:
        return source
    body = await request.body()
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        return _normalize_source(payload.get("source"))
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    _configure_access_logger()
    logging.getLogger("uvicorn.access").disabled = True
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


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method
    http_version = request.scope.get("http_version", "1.1")

    custom_source_log = method == "POST" and path in _CUSTOM_SOURCE_LOG_PATHS
    request_source = None
    if custom_source_log:
        request_source = await _extract_source_from_request(request)

    status_code = 500
    response = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        status_phrase = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else ""
        if custom_source_log:
            _access_logger.info(
                '%s %s %s HTTP/%s" %d %s',
                _source_log_tag(request_source),
                method,
                path,
                http_version,
                status_code,
                status_phrase,
            )
        else:
            client = request.client
            client_addr = f"{client.host}:{client.port}" if client else "-"
            _access_logger.info(
                '%s - "%s %s HTTP/%s" %d %s',
                client_addr,
                method,
                path,
                http_version,
                status_code,
                status_phrase,
            )

# Register route groups
app.include_router(bridge_router)
app.include_router(greeks_router)
app.include_router(volatility_router)

# VA-compatible route aliases — allows swing/vol_quant to switch provider URL
# without changing their endpoint paths (/api/bridge/* → /api/v1/bridge/*)
from api.routes.bridge import router as _bridge_compat
_compat_router = APIRouter(prefix="/api/bridge", tags=["bridge-compat"])


@_compat_router.get("/params/{symbol}")
async def compat_bridge_params(symbol: str, date: str = None, source: str = None):
    """VA-compatible: GET /api/bridge/params/{symbol}"""
    from api.routes.bridge import get_bridge_params
    return await get_bridge_params(symbol, date=date, source=source)


@_compat_router.post("/batch")
async def compat_bridge_batch(
    source: Optional[str] = Query(None),
    req: dict = fastapi.Body(default={}),
):
    """VA-compatible: POST /api/bridge/batch"""
    from api.routes.bridge import BatchRequest, get_batch
    from pydantic import ValidationError
    payload = dict(req or {})
    query_source = _normalize_source(source)
    if query_source:
        payload["source"] = query_source
    elif "source" in payload:
        body_source = _normalize_source(payload.get("source"))
        if body_source:
            payload["source"] = body_source
        else:
            payload.pop("source", None)

    try:
        batch_req = BatchRequest(**payload)
    except (ValidationError, TypeError):
        batch_req = BatchRequest(source=query_source or "swing")
    return await get_batch(batch_req)


app.include_router(_compat_router)


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
