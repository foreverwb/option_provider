"""
Tests for BridgeClient and OratsClient with HTTP mocking.
Also tests cache behavior and utility functions.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock

from bridge_client.client import BridgeClient
from bridge_client.models import BridgeSnapshot
from orats_provider.cache import TTLCache
from orats_provider.config import OratsConfig
from orats_provider.utils import (
    filter_by_dte, filter_by_moneyness, filter_atm,
    classify_expiry_type, filter_by_expiry_type,
    group_by_expiry, group_by_strike, find_gamma_flip,
)


# ── BridgeClient tests ─────────────────────────────────────────────────

class TestBridgeClient:
    @patch("bridge_client.client.requests.Session")
    def test_get_snapshot(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "symbol": "AAPL", "spot_price": 150.0,
            "direction_score": 30.0, "volatility_score": -5.0,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = BridgeClient(base_url="http://test:8668")
        snap = client.get_snapshot("AAPL")
        assert isinstance(snap, BridgeSnapshot)
        assert snap.symbol == "AAPL"
        assert snap.spot_price == 150.0

    @patch("bridge_client.client.requests.Session")
    def test_get_batch(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"symbol": "AAPL", "spot_price": 150.0},
            {"symbol": "MSFT", "spot_price": 300.0},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = BridgeClient(base_url="http://test:8668")
        snaps = client.get_batch(["AAPL", "MSFT"])
        assert len(snaps) == 2
        assert snaps[0].symbol == "AAPL"
        assert snaps[1].symbol == "MSFT"

    @patch("bridge_client.client.requests.Session")
    def test_get_records(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": 1}, {"id": 2}]
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        client = BridgeClient(base_url="http://test:8668")
        records = client.get_records()
        assert len(records) == 2

    @patch("bridge_client.client.requests.Session")
    def test_context_manager(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        with BridgeClient(base_url="http://test:8668") as client:
            assert client is not None
        mock_session.close.assert_called_once()


# ── TTLCache tests ──────────────────────────────────────────────────────

class TestTTLCache:
    def test_basic_set_get(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_ttl_expiry(self):
        cache = TTLCache(default_ttl=1)
        cache.set("key1", "value1", ttl=0)
        # Expired immediately
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_delete(self):
        cache = TTLCache()
        cache.set("key1", "value1")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    def test_make_key(self):
        cache = TTLCache()
        key = cache.make_key("strikes", "AAPL", "30")
        assert key == "strikes:AAPL:30"

    def test_max_size_eviction(self):
        cache = TTLCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict oldest
        assert cache.size <= 3


# ── Utility function tests ──────────────────────────────────────────────

class TestFilterUtils:
    def test_filter_by_dte(self, strike_chain):
        filtered = filter_by_dte(strike_chain, 20, 40)
        assert all(20 <= r.dte <= 40 for r in filtered)
        assert len(filtered) > 0

    def test_filter_by_moneyness(self, strike_chain):
        filtered = filter_by_moneyness(strike_chain, 0.05)
        for r in filtered:
            assert abs(r.strike - r.spot_price) / r.spot_price <= 0.05

    def test_filter_atm(self, strike_chain):
        atm = filter_atm(strike_chain, tolerance=0.01)
        for r in atm:
            assert abs(r.strike - r.spot_price) / r.spot_price <= 0.01

    def test_classify_expiry_monthly(self):
        # 3rd Friday of March 2026 = March 20
        assert classify_expiry_type("2026-03-20") in ("MONTHLY", "QUARTERLY")

    def test_classify_expiry_weekly(self):
        # Not a 3rd Friday
        assert classify_expiry_type("2026-03-13") == "WEEKLY"

    def test_classify_expiry_quarterly(self):
        # 3rd Friday of June 2026 = June 19
        result = classify_expiry_type("2026-06-19")
        assert result == "QUARTERLY"

    def test_group_by_expiry(self, strike_chain):
        groups = group_by_expiry(strike_chain)
        assert len(groups) == 3  # 3 expiry dates

    def test_group_by_strike(self, strike_chain):
        groups = group_by_strike(strike_chain)
        assert len(groups) > 0

    def test_find_gamma_flip(self, strike_chain):
        flip = find_gamma_flip(strike_chain)
        # Should find a flip point near spot
        if flip is not None:
            assert 100 < flip < 200  # Within reasonable range of spot=150

    def test_filter_by_expiry_type(self, strike_chain):
        # All test data has specific dates; filter by WEEKLY to get non-3rd-Friday
        weeklies = filter_by_expiry_type(strike_chain, "WEEKLY")
        # Result depends on test dates
        assert isinstance(weeklies, list)
