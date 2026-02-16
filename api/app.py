"""
FastAPI app wrapper for unified provider.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from provider.unified import UnifiedProvider

provider = UnifiedProvider(
    va_base_url=os.getenv("VA_BASE_URL", "http://localhost:8668"),
    orats_token=os.getenv("ORATS_TOKEN"),
)


def create_app() -> FastAPI:
    app = FastAPI(title="Options Provider API", version="1.0.0")

    from .routes.bridge import router as bridge_router
    from .routes.greeks import router as greeks_router
    from .routes.volatility import router as volatility_router

    app.include_router(bridge_router, prefix="/api/v1")
    app.include_router(greeks_router, prefix="/api/v1")
    app.include_router(volatility_router, prefix="/api/v1")

    @app.on_event("shutdown")
    def _shutdown() -> None:
        provider.close()

    return app


app = create_app()
