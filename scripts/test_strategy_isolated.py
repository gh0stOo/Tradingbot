"""
Isolated Strategy Testing Script

PFLICHT für Phase 8: Jede Strategie einzeln testen

Usage:
    python scripts/test_strategy_isolated.py --strategy emaTrend
    python scripts/test_strategy_isolated.py --strategy all --start-date 2024-01-01 --end-date 2024-12-31

Testet:
- Entry-Signal-Generierung
- Exit-Bedingungen
- Stop-Loss Trigger
- Take-Profit Trigger
- Time-Exit
- Trade-Anzahl
- Win Rate
- Sharpe Ratio

KRITISCH:
- Strategie MUSS Trades generieren
- MINDESTENS 10 Trades über Testzeitraum
- Win Rate sollte > 40% sein
- Sharpe > 0.5

Wenn eine Strategie diese Kriterien NICHT erfüllt:
→ NICHT PRODUKTIONSFÄHIG markieren
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import json
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from utils.config_loader import ConfigLoader
from trading.strategies_refactored import (
    EmaTrendStrategy,
    MacdTrendStrategy,
    RsiMeanReversionStrategy,
    BollingerMeanReversionStrategy,
    AdxTrendStrategy,
    VolumeProfileStrategy,
    VolatilityBreakoutStrategy,
    MultiTimeframeStrategy
)
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector


class StrategyIsolatedTester:
    """
    Tests einzelne Strategien isoliert

    Simuliert Backtesting nur mit EINER Strategie.
    Validiert dass die Strategie real handeln kann.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.indicators_calc = Indicators()
        self.regime_detector = RegimeDetector()

        # Test results
        self.results = {
            "strategy": None,
            "total_evaluations": 0,
            "signals_generated": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "trades": [],
            "regime_distribution": {
                "trending": 0,
                "ranging": 0,
                "volatile": 0
            }
        }

    def test_strategy(
        self,
        strategy_name: str,
        historical_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Test a single strategy in isolation

        Args:
            strategy_name: Name of strategy to test
            historical_data: Historical OHLCV data

        Returns:
            Test results dictionary
        """
        print(f"\n{'='*60}")
        print(f"TESTING STRATEGY: {strategy_name}")
        print(f"{'='*60}\n")

        # Create strategy instance
        strategy = self._create_strategy(strategy_name)
        if not strategy:
            return {"error": f"Unknown strategy: {strategy_name}"}

        self.results["strategy"] = strategy_name

        # Iterate through historical data
        for i in range(100, len(historical_data)):
            # Get candle window
            candles = historical_data.iloc[max(0, i-100):i]

            if len(candles) < 50:
                continue

            # Calculate indicators
            indicators = self.indicators_calc.calculate_all(candles)
            if not indicators:
                continue

            price = indicators["currentPrice"]

            # Detect regime
            regime = self.regime_detector.detect_regime(indicators, price)
            self.results["regime_distribution"][regime["type"]] += 1

            # Evaluate strategy
            self.results["total_evaluations"] += 1

            signal = strategy.check_entry(
                indicators=indicators,
                regime=regime,
                price=price,
                candles_m1=candles
            )

            if signal:
                self.results["signals_generated"] += 1

                if signal["side"] == "Buy":
                    self.results["buy_signals"] += 1
                else:
                    self.results["sell_signals"] += 1

                # Simulate trade
                trade = self._simulate_trade(
                    signal=signal,
                    entry_price=price,
                    entry_time=candles.iloc[-1].name,
                    atr=indicators["atr"],
                    indicators=indicators,
                    historical_data=historical_data,
                    entry_index=i,
                    strategy=strategy
                )

                if trade:
                    self.results["trades"].append(trade)

        # Calculate statistics
        stats = self._calculate_statistics()

        # Validation
        validation = self._validate_strategy(stats)

        return {
            "strategy": strategy_name,
            "signals": {
                "total_evaluations": self.results["total_evaluations"],
                "signals_generated": self.results["signals_generated"],
                "buy_signals": self.results["buy_signals"],
                "sell_signals": self.results["sell_signals"],
                "signal_rate": (
                    self.results["signals_generated"] / self.results["total_evaluations"]
                    if self.results["total_evaluations"] > 0 else 0
                )
            },
            "trades": stats,
            "validation": validation,
            "regime_distribution": self.results["regime_distribution"]
        }

    def _create_strategy(self, strategy_name: str):
        """Create strategy instance"""
        strategy_map = {
            "emaTrend": EmaTrendStrategy,
            "macdTrend": MacdTrendStrategy,
            "rsiMeanReversion": RsiMeanReversionStrategy,
            "bollingerMeanReversion": BollingerMeanReversionStrategy,
            "adxTrend": AdxTrendStrategy,
            "volumeProfile": VolumeProfileStrategy,
            "volatilityBreakout": VolatilityBreakoutStrategy,
            "multiTimeframe": MultiTimeframeStrategy
        }

        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            return None

        return strategy_class(self.config)

    def _simulate_trade(
        self,
        signal: Dict[str, Any],
        entry_price: float,
        entry_time: Any,
        atr: float,
        indicators: Dict[str, float],
        historical_data: pd.DataFrame,
        entry_index: int,
        strategy: Any
    ) -> Optional[Dict[str, Any]]:
        """Simulate a trade execution and exit"""
        # Calculate SL/TP
        stop_loss = strategy.get_stop_loss(entry_price, signal["side"], atr, indicators)
        take_profit = strategy.get_take_profit(entry_price, signal["side"], atr, indicators)

        # Simulate holding period (max 100 candles)
        max_hold = min(100, len(historical_data) - entry_index)

        for j in range(1, max_hold):
            candle_idx = entry_index + j
            if candle_idx >= len(historical_data):
                break

            candle = historical_data.iloc[candle_idx]

            # Check stop loss
            if signal["side"] == "Buy":
                if candle["low"] <= stop_loss:
                    # Stop loss hit
                    return {
                        "entry_time": entry_time,
                        "exit_time": candle.name,
                        "entry_price": entry_price,
                        "exit_price": stop_loss,
                        "side": signal["side"],
                        "pnl_pct": (stop_loss - entry_price) / entry_price,
                        "exit_type": "stop_loss",
                        "hold_candles": j,
                        "success": False
                    }

                # Check take profit
                if candle["high"] >= take_profit:
                    # Take profit hit
                    return {
                        "entry_time": entry_time,
                        "exit_time": candle.name,
                        "entry_price": entry_price,
                        "exit_price": take_profit,
                        "side": signal["side"],
                        "pnl_pct": (take_profit - entry_price) / entry_price,
                        "exit_type": "take_profit",
                        "hold_candles": j,
                        "success": True
                    }

            else:  # Sell
                if candle["high"] >= stop_loss:
                    # Stop loss hit
                    return {
                        "entry_time": entry_time,
                        "exit_time": candle.name,
                        "entry_price": entry_price,
                        "exit_price": stop_loss,
                        "side": signal["side"],
                        "pnl_pct": (entry_price - stop_loss) / entry_price,
                        "exit_type": "stop_loss",
                        "hold_candles": j,
                        "success": False
                    }

                # Check take profit
                if candle["low"] <= take_profit:
                    # Take profit hit
                    return {
                        "entry_time": entry_time,
                        "exit_time": candle.name,
                        "entry_price": entry_price,
                        "exit_price": take_profit,
                        "side": signal["side"],
                        "pnl_pct": (entry_price - take_profit) / entry_price,
                        "exit_type": "take_profit",
                        "hold_candles": j,
                        "success": True
                    }

        # Time exit (if strategy has one)
        time_exit_minutes = strategy.get_time_exit()
        if time_exit_minutes and j >= time_exit_minutes:
            exit_price = historical_data.iloc[entry_index + j]["close"]
            if signal["side"] == "Buy":
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - exit_price) / entry_price

            return {
                "entry_time": entry_time,
                "exit_time": historical_data.iloc[entry_index + j].name,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "side": signal["side"],
                "pnl_pct": pnl_pct,
                "exit_type": "time_exit",
                "hold_candles": j,
                "success": pnl_pct > 0
            }

        return None

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate trade statistics"""
        trades = self.results["trades"]

        if not trades:
            return {
                "total_trades": 0,
                "error": "NO TRADES GENERATED - STRATEGY NOT FUNCTIONAL"
            }

        wins = [t for t in trades if t["success"]]
        losses = [t for t in trades if not t["success"]]

        total_pnl = sum(t["pnl_pct"] for t in trades)
        win_rate = len(wins) / len(trades) if trades else 0

        # Average win/loss
        avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0

        # Calculate Sharpe (simplified)
        returns = [t["pnl_pct"] for t in trades]
        avg_return = sum(returns) / len(returns)
        std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
        sharpe = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0

        # Exit type distribution
        exit_types = {}
        for trade in trades:
            exit_type = trade["exit_type"]
            exit_types[exit_type] = exit_types.get(exit_type, 0) + 1

        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl_pct": total_pnl,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            "sharpe_ratio": sharpe,
            "exit_types": exit_types
        }

    def _validate_strategy(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate strategy meets minimum requirements

        Returns:
            Validation result with status and reasons
        """
        issues = []
        warnings = []

        # CRITICAL: Must generate trades
        if stats.get("total_trades", 0) == 0:
            return {
                "status": "FAILED",
                "production_ready": False,
                "reason": "CRITICAL: Strategy generated ZERO trades",
                "issues": ["NO_TRADES_GENERATED"],
                "recommendation": "Strategy is NOT functional - do NOT use in production"
            }

        # Minimum trade count
        if stats["total_trades"] < 10:
            issues.append(f"Too few trades: {stats['total_trades']} (minimum: 10)")

        # Win rate check
        if stats["win_rate"] < 0.40:
            issues.append(f"Win rate too low: {stats['win_rate']:.2%} (minimum: 40%)")

        # Sharpe ratio check
        if stats["sharpe_ratio"] < 0.5:
            warnings.append(f"Low Sharpe ratio: {stats['sharpe_ratio']:.2f} (recommended: > 0.5)")

        # Total PnL check
        if stats["total_pnl_pct"] < 0:
            issues.append(f"Negative total PnL: {stats['total_pnl_pct']:.2%}")

        # Determine status
        if issues:
            status = "FAILED"
            production_ready = False
            recommendation = "Strategy NOT ready for production. Fix issues first."
        elif warnings:
            status = "PASSED_WITH_WARNINGS"
            production_ready = True
            recommendation = "Strategy can be used but monitor closely."
        else:
            status = "PASSED"
            production_ready = True
            recommendation = "Strategy is production-ready."

        return {
            "status": status,
            "production_ready": production_ready,
            "issues": issues,
            "warnings": warnings,
            "recommendation": recommendation
        }


def load_historical_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load historical data for testing from database

    Args:
        symbol: Trading symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data
    """
    from data.database import Database
    import os

    # Get database path from config
    db_path = os.path.join(project_root, "data", "trading.db")

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print(f"   Run: python scripts/collect_historical_data.py --symbol {symbol} --days 90")
        return pd.DataFrame()

    # Load data from database
    db = Database(db_path)

    try:
        # Query klines from database
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM klines
            WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """

        cursor = db.execute(query, (symbol, start_date, end_date))
        rows = cursor.fetchall()

        if not rows:
            print(f"⚠️ No data found for {symbol} between {start_date} and {end_date}")
            print(f"   Database has {db.execute('SELECT COUNT(*) FROM klines WHERE symbol = ?', (symbol,)).fetchone()[0]} klines for {symbol}")
            print(f"   Oldest: {db.execute('SELECT MIN(timestamp) FROM klines WHERE symbol = ?', (symbol,)).fetchone()[0]}")
            print(f"   Newest: {db.execute('SELECT MAX(timestamp) FROM klines WHERE symbol = ?', (symbol,)).fetchone()[0]}")
            print(f"\n   Falling back to Bybit API...")

            # Fallback: Fetch from Bybit API
            from integrations.bybit import BybitClient
            from datetime import datetime

            bybit = BybitClient("", "", testnet=False)  # Public API
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)

            klines_raw = bybit.get_klines(
                symbol=symbol,
                interval="1",
                startTime=start_ts,
                limit=1000
            )

            if not klines_raw:
                print(f"❌ Failed to fetch data from Bybit API")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(klines_raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            # Convert to float
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            print(f"✅ Loaded {len(df)} candles from Bybit API")
            return df

        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        # Convert to float
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        print(f"✅ Loaded {len(df)} candles from database")
        return df

    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Test individual strategies in isolation")
    parser.add_argument("--strategy", type=str, required=True,
                        help="Strategy name (emaTrend, macdTrend, etc.) or 'all'")
    parser.add_argument("--symbol", type=str, default="BTCUSDT",
                        help="Trading symbol (default: BTCUSDT)")
    parser.add_argument("--start-date", type=str, default="2024-01-01",
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2024-12-31",
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default="test_results",
                        help="Output directory for results")

    args = parser.parse_args()

    # Load config
    config = ConfigLoader.load_config()

    # Load historical data
    print(f"\nLoading historical data for {args.symbol}...")
    historical_data = load_historical_data(args.symbol, args.start_date, args.end_date)
    print(f"Loaded {len(historical_data)} candles")

    # Determine which strategies to test
    if args.strategy == "all":
        strategies = [
            "emaTrend", "macdTrend", "rsiMeanReversion", "bollingerMeanReversion",
            "adxTrend", "volumeProfile", "volatilityBreakout", "multiTimeframe"
        ]
    else:
        strategies = [args.strategy]

    # Test each strategy
    all_results = {}

    for strategy_name in strategies:
        tester = StrategyIsolatedTester(config)
        results = tester.test_strategy(strategy_name, historical_data)
        all_results[strategy_name] = results

        # Print results
        print(f"\n{'='*60}")
        print(f"RESULTS: {strategy_name}")
        print(f"{'='*60}")
        print(json.dumps(results, indent=2))

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"strategy_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")

    for strategy_name, results in all_results.items():
        validation = results.get("validation", {})
        status = validation.get("status", "UNKNOWN")
        production_ready = validation.get("production_ready", False)

        status_symbol = "✅" if production_ready else "❌"
        print(f"{status_symbol} {strategy_name}: {status}")

        if not production_ready:
            issues = validation.get("issues", [])
            for issue in issues:
                print(f"   - {issue}")

    print()


if __name__ == "__main__":
    main()
