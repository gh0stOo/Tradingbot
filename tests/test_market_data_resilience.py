"""MarketData should handle integration errors gracefully."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trading.market_data import MarketData


class _FailingClient:
    """Client stub that raises on optional endpoints."""

    def get_klines(self, symbol, interval, limit):
        return []

    def get_funding_rate(self, symbol, limit):
        raise RuntimeError("boom")

    def get_open_interest(self, symbol, limit):
        raise RuntimeError("boom")


def test_get_symbol_data_survives_optional_endpoint_failures():
    """Errors in optional endpoints should not raise or corrupt result."""
    md = MarketData(_FailingClient())

    data = md.get_symbol_data("BTCUSDT")

    assert data["symbol"] == "BTCUSDT"
    assert data["klines"] == {"m1": [], "m5": [], "m15": []}
    assert data["fundingRate"] == []
    assert data["openInterest"] == []
