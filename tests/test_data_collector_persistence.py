"""DataCollector persistence tests."""

import os
import tempfile
import sys

# Ensure src is on path for direct module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from data.database import Database
from data.data_collector import DataCollector


def test_save_trade_entry_returns_id_and_persists():
    """Trade insert should return a valid row id and be queryable immediately."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = Database(db_path)
        collector = DataCollector(db)

        trade_id = collector.save_trade_entry(
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=0.01,
            stop_loss=49000.0,
            take_profit=51000.0,
            confidence=0.8,
            quality_score=0.9,
            regime_type="trending",
            strategies_used=["emaTrend"],
            trading_mode="PAPER",
        )

        assert isinstance(trade_id, int) and trade_id > 0

        row = db.fetch_one("SELECT id, symbol, trading_mode FROM trades WHERE id = ?", (trade_id,))
        assert row is not None
        assert row["symbol"] == "BTCUSDT"
        assert row["trading_mode"] == "PAPER"
    finally:
        db.close()
        os.unlink(db_path)
