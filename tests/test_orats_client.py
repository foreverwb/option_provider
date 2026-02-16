from __future__ import annotations

import httpx

from orats_provider.client import OratsClient


def test_orats_client_endpoints() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("token") == "demo-token"

        if request.url.path == "/datav2/strikes":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "strike": 190}]})
        if request.url.path == "/datav2/summaries":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "iv30d": 0.22}]})
        if request.url.path == "/datav2/cores":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "ivPctile1y": 0.5}]})
        if request.url.path == "/datav2/monies/implied":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "atmiv": 0.22}]})
        if request.url.path == "/datav2/monies/forecast":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "forecast": 0.2}]})
        if request.url.path == "/datav2/ivrank":
            return httpx.Response(200, json={"data": [{"ticker": "AAPL", "ivRank": 45}]})

        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="https://api.orats.io/datav2", transport=transport)

    client = OratsClient(token="demo-token", client=http_client)

    assert client.get_strikes("AAPL")
    assert client.get_summaries("AAPL")
    assert client.get_cores("AAPL")
    assert client.get_monies_implied("AAPL")
    assert client.get_monies_forecast("AAPL")
    assert client.get_iv_rank("AAPL")
