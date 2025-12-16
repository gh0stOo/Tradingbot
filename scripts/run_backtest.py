"""CLI wrapper to run a backtest using BacktestEngine."""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.config_loader import ConfigLoader
from backtesting.backtest_engine import BacktestEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backtest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run backtest with BacktestEngine.")
    parser.add_argument("--symbol", required=True, help="Trading symbol, e.g., BTCUSDT")
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV (timestamp,open,high,low,close,volume)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--initial_equity", type=float, default=10000.0, help="Starting equity")
    parser.add_argument("--fixed_slippage", action="store_true", help="Use fixed slippage instead of dynamic model")
    return parser.parse_args()


def load_klines(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV missing required columns: {required_cols - set(df.columns)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    config = ConfigLoader().config
    klines = load_klines(csv_path)

    engine = BacktestEngine(
        config=config,
        initial_equity=args.initial_equity,
        use_dynamic_slippage=not args.fixed_slippage,
    )

    start = pd.to_datetime(args.start) if args.start else None
    end = pd.to_datetime(args.end) if args.end else None

    results = engine.run_backtest(symbol=args.symbol, klines=klines, start_date=start, end_date=end)

    logger.info("Backtest complete for %s", args.symbol)
    for key, value in results.items():
        logger.info("%s: %s", key, value)


if __name__ == "__main__":
    main()
