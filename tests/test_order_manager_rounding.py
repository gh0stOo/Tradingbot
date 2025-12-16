"""OrderManager rounding and validation tests."""

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trading.order_manager import OrderManager


def test_live_order_rejects_qty_below_minimum_after_rounding():
    """Quantization should reject quantities that fall below exchange minimums."""
    om = OrderManager(bybit_client=Mock(), trading_mode="LIVE")

    result = om._execute_live_order(
        {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "qty": 0.0005,  # Will round down
            "price": 50000.0,
            "tickSize": 0.1,
            "qtyStep": 0.001,
            "minOrderQty": 0.01,
        }
    )

    assert result["success"] is False
    assert result["qty"] == 0
    assert result["symbol"] == "BTCUSDT"
