"""
API tests for bridge batch compatibility route behavior.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import api.routes.bridge as bridge_routes
from api.main import app


def test_compat_batch_query_source_and_access_log(capsys, monkeypatch):
    captured = {}

    async def fake_get_batch(req):
        captured["source"] = req.source
        return {"success": True, "source": req.source}

    monkeypatch.setattr(bridge_routes, "get_batch", fake_get_batch)

    with TestClient(app) as client:
        resp = client.post(
            "/api/bridge/batch?source='swing'",
            json={"symbols": ["AAPL"], "source": "vol"},
        )

    assert resp.status_code == 200
    assert resp.json()["source"] == "swing"
    assert captured["source"] == "swing"
    io = capsys.readouterr()
    assert "['波段'] POST /api/bridge/batch HTTP/1.1\" 200 OK" in io.err
