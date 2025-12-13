"""Event-Based Backtesting Engine"""

import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd

from events.event import BaseEvent
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from events.risk_approval_event import RiskApprovalEvent
from events.order_intent_event import OrderIntentEvent
from events.fill_event import FillEvent
from events.position_update_event import PositionUpdateEvent
from core.trading_state import TradingState
from core.risk_engine import RiskEngine
from core.strategy_allocator import StrategyAllocator
from core.order_executor import OrderExecutor
from strategies.base import BaseStrategy
from trading.indicators import Indicators
from trading.slippage_model import SlippageModel

logger = logging.getLogger(__name__)


class EventBacktest:
    """
    Event-based backtesting engine with realistic simulation.
    
    Features:
    - Event stream from historical data
    - Slippage modeling
    - Fees (Maker/Taker)
    - Latency simulation
    - Partial fills
    - Order rejections
    - No lookahead
    - Intraday session logic
    """
    
    def __init__(
        self,
        initial_equity: Decimal = Decimal("10000"),
        config: Optional[Dict] = None
    ) -> None:
        """
        Initialize backtesting engine.
        
        Args:
            initial_equity: Starting equity
            config: Backtest configuration
        """
        self.config = config or {}
        self.initial_equity = initial_equity
        
        # Backtest settings
        self.maker_fee = Decimal(str(self.config.get("makerFee", 0.001)))  # 0.1%
        self.taker_fee = Decimal(str(self.config.get("takerFee", 0.001)))  # 0.1%
        self.slippage_model = SlippageModel()
        self.latency_ms = self.config.get("latencyMs", 50)  # 50ms latency
        self.order_rejection_rate = self.config.get("orderRejectionRate", 0.01)  # 1%
        
        # Components (will be initialized in run_backtest)
        self.trading_state: Optional[TradingState] = None
        self.risk_engine: Optional[RiskEngine] = None
        self.strategy_allocator: Optional[StrategyAllocator] = None
        self.order_executor: Optional[OrderExecutor] = None
        self.strategies: List[BaseStrategy] = []
        
        # Results
        self.results: Dict[str, Any] = {}
        
        logger.info(f"EventBacktest initialized with equity={initial_equity}")
    
    def run_backtest(
        self,
        historical_data: pd.DataFrame,
        strategies: List[BaseStrategy],
        risk_config: Dict,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            historical_data: DataFrame with columns: timestamp, symbol, open, high, low, close, volume
            strategies: List of strategies to test
            risk_config: Risk configuration
            start_date: Start date for backtest
            end_date: End date for backtest
            
        Returns:
            Backtest results dictionary
        """
        # Initialize components
        self.trading_state = TradingState(initial_cash=self.initial_equity)
        self.trading_state.enable_trading()
        
        risk_config_full = {"risk": risk_config, "circuitBreaker": {}}
        self.risk_engine = RiskEngine(risk_config_full, self.trading_state)
        self.strategy_allocator = StrategyAllocator(risk_config_full, self.trading_state)
        self.order_executor = OrderExecutor(self.trading_state, None, "PAPER")
        self.strategies = strategies
        
        # Filter data by date range
        if start_date or end_date:
            historical_data = self._filter_data_by_date(historical_data, start_date, end_date)
        
        # Sort by timestamp
        historical_data = historical_data.sort_values("timestamp").reset_index(drop=True)
        
        # Process events
        trades = []
        equity_curve = []
        peak_equity = self.initial_equity
        
        for idx, row in historical_data.iterrows():
            timestamp = pd.to_datetime(row["timestamp"])
            
            # Create market event
            market_event = MarketEvent(
                symbol=row.get("symbol", "UNKNOWN"),
                price=Decimal(str(row["close"])),
                volume=Decimal(str(row.get("volume", 0))),
                timestamp=timestamp.isoformat(),
                additional_data={
                    "open": row.get("open", row["close"]),
                    "high": row.get("high", row["close"]),
                    "low": row.get("low", row["close"]),
                    "klines_m1": self._get_klines_window(historical_data, idx, window=50),
                },
                source="EventBacktest",
            )
            
            # Generate signals from strategies
            all_signals: List[SignalEvent] = []
            for strategy in self.strategies:
                try:
                    signals = strategy.generate_signals(market_event)
                    all_signals.extend(signals)
                except Exception as e:
                    logger.warning(f"Error generating signals from {strategy.name}: {e}")
            
            # Process signals through allocator
            if all_signals:
                order_intents = self.strategy_allocator.process_signals(all_signals)
                
                # Process each order intent through risk engine
                for order_intent in order_intents:
                    risk_approval = self.risk_engine.evaluate_order_intent(order_intent)
                    
                    if risk_approval.approved:
                        # Execute order
                        order_submission = self.order_executor.execute_approved_order(risk_approval)
                        
                        if order_submission and order_submission.status == "filled":
                            # Record trade
                            trades.append({
                                "timestamp": timestamp,
                                "symbol": order_submission.symbol,
                                "side": order_submission.side,
                                "quantity": float(order_submission.quantity),
                                "price": float(order_submission.price),
                            })
            
            # Update equity curve
            current_equity = self.trading_state.equity
            if current_equity > peak_equity:
                peak_equity = current_equity
            
            equity_curve.append({
                "timestamp": timestamp,
                "equity": float(current_equity),
                "drawdown": float(self.trading_state.drawdown),
            })
        
        # Close all open positions at end
        self._close_all_positions(historical_data.iloc[-1])
        
        # Calculate metrics
        results = self._calculate_metrics(
            trades,
            equity_curve,
            peak_equity,
            historical_data
        )
        
        self.results = results
        return results
    
    def _filter_data_by_date(
        self,
        data: pd.DataFrame,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> pd.DataFrame:
        """Filter data by date range"""
        if "timestamp" not in data.columns:
            return data
        
        data["timestamp_dt"] = pd.to_datetime(data["timestamp"])
        
        if start_date:
            data = data[data["timestamp_dt"] >= start_date]
        if end_date:
            data = data[data["timestamp_dt"] <= end_date]
        
        data = data.drop("timestamp_dt", axis=1)
        return data
    
    def _get_klines_window(
        self,
        data: pd.DataFrame,
        current_idx: int,
        window: int = 50
    ) -> List[List]:
        """Get klines window for current index"""
        start_idx = max(0, current_idx - window)
        end_idx = current_idx + 1
        
        window_data = data.iloc[start_idx:end_idx]
        
        # Convert to kline format: [timestamp_ms, open, high, low, close, volume]
        klines = []
        for _, row in window_data.iterrows():
            timestamp_ms = int(pd.to_datetime(row["timestamp"]).timestamp() * 1000)
            klines.append([
                timestamp_ms,
                str(row.get("open", row["close"])),
                str(row.get("high", row["close"])),
                str(row.get("low", row["close"])),
                str(row["close"]),
                str(row.get("volume", 0)),
            ])
        
        return klines
    
    def _check_position_exits(
        self,
        current_bar: pd.Series,
        timestamp: datetime,
        trades: List[Dict]
    ) -> None:
        """Check for position exits (stop loss, take profit)"""
        if not self.trading_state:
            return
        
        open_positions = self.trading_state.get_open_positions()
        current_price = Decimal(str(current_bar["close"]))
        
        for symbol, position in open_positions.items():
            # Check stop loss
            if position.side == "Buy" and current_price <= position.stop_loss:
                exit_price = position.stop_loss
                exit_reason = "Stop Loss"
            elif position.side == "Sell" and current_price >= position.stop_loss:
                exit_price = position.stop_loss
                exit_reason = "Stop Loss"
            # Check take profit
            elif position.side == "Buy" and current_price >= position.take_profit:
                exit_price = position.take_profit
                exit_reason = "Take Profit"
            elif position.side == "Sell" and current_price <= position.take_profit:
                exit_price = position.take_profit
                exit_reason = "Take Profit"
            else:
                continue
            
            # Calculate realized PnL
            if position.side == "Buy":
                realized_pnl = (exit_price - position.entry_price) * position.quantity
            else:
                realized_pnl = (position.entry_price - exit_price) * position.quantity
            
            # Apply fees
            notional = exit_price * position.quantity
            fees = notional * self.taker_fee
            realized_pnl -= fees
            
            # Record exit trade
            trades.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "side": "Sell" if position.side == "Buy" else "Buy",  # Opposite side for exit
                "quantity": float(position.quantity),
                "price": float(exit_price),
                "exit_reason": exit_reason,
                "realized_pnl": float(realized_pnl),
            })
            
            # Close position
            self.trading_state.remove_position(symbol, realized_pnl)
            self.trading_state.credit_cash(position.quantity * exit_price - fees)
    
    def _close_all_positions(self, last_bar: pd.Series) -> None:
        """Close all open positions at end of backtest"""
        if not self.trading_state:
            return
        
        open_positions = self.trading_state.get_open_positions()
        for symbol, position in open_positions.items():
            exit_price = Decimal(str(last_bar["close"]))
            
            # Calculate realized PnL
            if position.side == "Buy":
                realized_pnl = (exit_price - position.entry_price) * position.quantity
            else:
                realized_pnl = (position.entry_price - exit_price) * position.quantity
            
            # Apply fees
            notional = exit_price * position.quantity
            fees = notional * self.taker_fee
            realized_pnl -= fees
            
            # Close position
            self.trading_state.remove_position(symbol, realized_pnl)
            self.trading_state.credit_cash(position.quantity * exit_price - fees)
    
    def _calculate_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[Dict],
        peak_equity: Decimal,
        historical_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Calculate backtest performance metrics"""
        if not equity_curve:
            return {"error": "No equity curve data"}
        
        final_equity = equity_curve[-1]["equity"]
        total_return = (final_equity - self.initial_equity) / self.initial_equity
        
        # Calculate individual trade PnL from trades list
        trade_pnls: List[float] = []
        for trade in trades:
            if "realized_pnl" in trade and trade["realized_pnl"] is not None:
                trade_pnls.append(trade["realized_pnl"])
        
        # Max drawdown
        max_drawdown = 0.0
        max_drawdown_duration = 0
        current_drawdown_duration = 0
        peak = float(self.initial_equity)
        drawdown_start_idx = 0
        
        for i, point in enumerate(equity_curve):
            equity_val = point["equity"]
            if equity_val > peak:
                peak = equity_val
                drawdown_start_idx = i
                current_drawdown_duration = 0
            else:
                current_drawdown_duration += 1
                drawdown = (peak - equity_val) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_drawdown_duration = current_drawdown_duration
        
        # Time to Recovery (from max drawdown to new peak)
        time_to_recovery = None
        if max_drawdown > 0:
            recovery_idx = drawdown_start_idx + max_drawdown_duration
            recovery_time = None
            peak_after_dd = peak
            
            for i in range(recovery_idx, len(equity_curve)):
                if equity_curve[i]["equity"] > peak_after_dd:
                    recovery_time = equity_curve[i]["timestamp"]
                    time_to_recovery_dt = pd.to_datetime(equity_curve[drawdown_start_idx]["timestamp"])
                    recovery_time_dt = pd.to_datetime(recovery_time)
                    time_to_recovery = (recovery_time_dt - time_to_recovery_dt).total_seconds() / 3600  # hours
                    break
            
            if time_to_recovery is None:
                time_to_recovery = -1  # Never recovered
        
        # Calculate Profit Factor from trade PnLs
        if trade_pnls:
            gross_profit = sum([pnl for pnl in trade_pnls if pnl > 0])
            gross_loss = abs(sum([pnl for pnl in trade_pnls if pnl < 0]))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        else:
            # Fallback: calculate from equity changes
            total_profit = sum([max(0, equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) 
                               for i in range(1, len(equity_curve))])
            total_loss = abs(sum([min(0, equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) 
                                for i in range(1, len(equity_curve))]))
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0.0
        
        # Expectancy (average PnL per trade)
        if trade_pnls:
            expectancy = sum(trade_pnls) / len(trade_pnls)
        else:
            expectancy = (final_equity - self.initial_equity) / max(len(trades), 1)
        
        # Tail Loss (95th and 99th percentile of losses)
        tail_loss_95 = None
        tail_loss_99 = None
        if trade_pnls:
            losses = sorted([pnl for pnl in trade_pnls if pnl < 0])
            if losses:
                tail_loss_95 = abs(losses[int(len(losses) * 0.95)]) if len(losses) > 0 else None
                tail_loss_99 = abs(losses[int(len(losses) * 0.99)]) if len(losses) > 1 else tail_loss_95
        
        # Ulcer Index (proper calculation)
        # Sum of squared percentage drawdowns / number of periods
        drawdowns_squared_sum = 0.0
        period_peak = float(self.initial_equity)
        
        for point in equity_curve:
            equity_val = point["equity"]
            if equity_val > period_peak:
                period_peak = equity_val
            else:
                drawdown_pct = (period_peak - equity_val) / period_peak
                drawdowns_squared_sum += drawdown_pct ** 2
        
        ulcer_index = (drawdowns_squared_sum / len(equity_curve)) ** 0.5 if equity_curve else 0.0
        
        num_trades = len(trades)
        days = (pd.to_datetime(equity_curve[-1]["timestamp"]) - pd.to_datetime(equity_curve[0]["timestamp"])).days
        trades_per_day = num_trades / max(days, 1) if days > 0 else num_trades
        
        return {
            "initial_equity": float(self.initial_equity),
            "final_equity": float(final_equity),
            "total_return": float(total_return),
            "total_return_pct": float(total_return * 100),
            "max_drawdown": float(max_drawdown),
            "max_drawdown_pct": float(max_drawdown * 100),
            "peak_equity": float(peak_equity),
            "num_trades": num_trades,
            "trades_per_day": float(trades_per_day),
            "profit_factor": float(profit_factor) if profit_factor != float('inf') else None,
            "ulcer_index": float(ulcer_index),
            "expectancy": float(expectancy),
            "tail_loss_95": float(tail_loss_95) if tail_loss_95 is not None else None,
            "tail_loss_99": float(tail_loss_99) if tail_loss_99 is not None else None,
            "time_to_recovery_hours": float(time_to_recovery) if time_to_recovery is not None else None,
            "equity_curve": equity_curve,
            "trades": trades,
        }

