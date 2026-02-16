from __future__ import annotations

import os

ORATS_BASE_URL = os.environ.get("ORATS_BASE_URL", "https://api.orats.io/datav2")
ORATS_TOKEN = os.environ.get("ORATS_TOKEN", "")

# Greeks exposure defaults.
DEFAULT_STRIKES_RANGE = 15
DEFAULT_DTE = 98
DEFAULT_EXPIRATION_FILTER = "*"

# Volatility defaults.
DEFAULT_VOL_DTE = 365
DEFAULT_METRIC = "VOLATILITY_MID"
DEFAULT_CONTRACT_FILTER = "ntm"

# Cache settings.
CACHE_TTL_SECONDS = 900

EXPIRATION_FILTER_MAP = {
    "w": "weekly",
    "m": "monthly",
    "q": "quarterly",
    "fd": "front_dated",
    "*": "all",
}

MAX_TICKERS_PER_ORATS_REQUEST = 10
