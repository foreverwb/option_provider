from __future__ import annotations

import httpx

from bridge_client.client import BridgeClient
from bridge_client.models import BridgeSnapshot


def test_bridge_client_connects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/bridge/params/NVDA":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "bridge": {
                        "symbol": "NVDA",
                        "as_of": "2025-06-01",
                        "market_state": {"iv30": 0.33},
                        "event_state": {"earnings_date": "2025-06-20"},
                        "execution_state": {"quadrant": "偏多—买波"},
                        "term_structure": {
                            "ratios": {"30_90": 0.9},
                            "label": "正常陡峭",
                            "label_code": "normal_steep",
                            "ratio_30_90": 0.9,
                            "adjustment": -0.1,
                            "horizon_bias": "short",
                            "state_flags": {"normal_steep": True},
                        },
                    },
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://test", transport=transport)

    client = BridgeClient(base_url="http://test", client=http_client)
    snap = client.get_bridge_snapshot("NVDA")

    assert isinstance(snap, BridgeSnapshot)
    assert snap.symbol == "NVDA"
    assert snap.market_state.get("iv30") == 0.33
    assert snap.term_structure is not None
    assert snap.term_structure.label_code == "normal_steep"
