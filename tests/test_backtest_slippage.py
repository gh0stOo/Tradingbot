"""Backtest slippage alignment with live model."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from backtesting.backtest_engine import BacktestEngine


class _StubSlippageModel:
    def __init__(self, slippage_value: float):
        self.slippage_value = slippage_value
        self.calls = 0

    def calculate_slippage(self, **kwargs):
        self.calls += 1
        return self.slippage_value


def test_simulate_order_uses_dynamic_slippage_when_enabled(monkeypatch):
    engine = BacktestEngine(config={}, use_dynamic_slippage=True)
    stub_model = _StubSlippageModel(slippage_value=10.0)
    engine.slippage_model = stub_model

    price = engine.simulate_order(
        symbol="BTCUSDT",
        side="Buy",
        price=50000.0,
        quantity=0.01,
        volume_24h_usd=1_000_000,
        volatility=0.02,
    )

    assert price == pytest.approx(50010.0)
    assert stub_model.calls == 1


def test_simulate_order_fallbacks_when_disabled(monkeypatch):
    engine = BacktestEngine(config={}, use_dynamic_slippage=False, slippage_rate=0.0002)

    price = engine.simulate_order(
        symbol="BTCUSDT",
        side="Sell",
        price=50000.0,
        quantity=0.01,
    )

    assert price == pytest.approx(50000.0 * (1 - 0.0002))
