"""
Shared dependencies for FastAPI routes.
Provider instances are managed via lifespan context.
"""

from __future__ import annotations

from typing import Any, Optional

from provider.unified import UnifiedProvider

# Module-level singleton; set during lifespan startup
_provider: Optional[UnifiedProvider] = None


def get_provider() -> UnifiedProvider:
    """Get the shared UnifiedProvider instance."""
    if _provider is None:
        raise RuntimeError("UnifiedProvider not initialized. App not started?")
    return _provider


def set_provider(provider: UnifiedProvider) -> None:
    global _provider
    _provider = provider


def clear_provider() -> None:
    global _provider
    if _provider:
        _provider.close()
    _provider = None
