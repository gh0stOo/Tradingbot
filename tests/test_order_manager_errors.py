"""OrderManager error handling and retry tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trading.order_manager import OrderManager
from utils.exceptions import NetworkError, InsufficientBalanceError


class _NetworkFlakyClient:
    def __init__(self, succeed_on: int = 3):
        self.calls = 0
        self.succeed_on = succeed_on

    def create_order(self, payload):
        self.calls += 1
        if self.calls < self.succeed_on:
            raise NetworkError("temporary network issue")
        return {"orderId": "ok", "price": payload.get("price", 50000.0)}


class _InsufficientBalanceClient:
    def __init__(self):
        self.calls = 0

    def create_order(self, payload):
        self.calls += 1
        raise InsufficientBalanceError("balance too low")


def _live_order_payload():
    return {
        "symbol": "BTCUSDT",
        "side": "Buy",
        "qty": 0.02,
        "price": 50000.0,
        "tickSize": 0.1,
        "qtyStep": 0.001,
        "minOrderQty": 0.001,
    }


def test_live_order_retries_network(monkeypatch):
    """Network errors should be retried before succeeding."""
    client = _NetworkFlakyClient(succeed_on=3)
    om = OrderManager(bybit_client=client, trading_mode="LIVE")

    # Avoid real sleep in retry
    monkeypatch.setattr("trading.order_manager.time.sleep", lambda s: None)

    result = om._execute_live_order(_live_order_payload())

    assert result["success"] is True
    assert client.calls == 3


def test_live_order_insufficient_balance_not_retried(monkeypatch):
    """Insufficient balance must not be retried."""
    client = _InsufficientBalanceClient()
    om = OrderManager(bybit_client=client, trading_mode="LIVE")

    monkeypatch.setattr("trading.order_manager.time.sleep", lambda s: None)

    result = om._execute_live_order(_live_order_payload())

    assert result["success"] is False
    assert result.get("retryable") is False
    assert client.calls == 1
