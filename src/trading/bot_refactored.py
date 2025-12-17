"""
Trading Bot Core Logic - REFACTORED

Neue Architektur mit:
- Zentrale State Machine
- Strategy Orchestrator
- Sequenzielle Strategie-Ausführung
- Marktphasen als Gewichtung (NICHT als Gates)
- Deterministisches, debugbares Verhalten
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import pandas as pd

# Core modules
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector
from trading.candlestick_patterns import CandlestickPatterns
from trading.risk_manager import RiskManager
from trading.order_manager import OrderManager
from trading.market_data import MarketData
from trading.btc_tracker import BTCTracker
from trading.correlation_filter import CorrelationFilter
from trading.portfolio_heat import PortfolioHeat

# NEW: State Machine & Orchestrator
from trading.bot_state_machine import BotStateMachine, BotState
from trading.strategy_orchestrator import StrategyOrchestrator
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

# ML Models (optional)
try:
    from ml.signal_predictor import SignalPredictor
    from ml.regime_classifier import RegimeClassifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


class TradingBotRefactored:
    """
    Refactored Trading Bot with State Machine and Orchestrator

    Key improvements:
    - Deterministic state management
    - Sequential strategy execution
    - Regime-based weighting (not blocking)
    - Clear debugging and logging
    """

    def __init__(
        self,
        config: Dict[str, Any],
        market_data: MarketData,
        order_manager: OrderManager,
        data_collector: Optional[Any] = None,
        position_tracker: Optional[Any] = None,
        position_manager: Optional[Any] = None
    ):
        """
        Initialize Trading Bot

        Args:
            config: Configuration dictionary
            market_data: MarketData instance
            order_manager: OrderManager instance
            data_collector: DataCollector instance
            position_tracker: PositionTracker instance
            position_manager: PositionManager instance
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.market_data = market_data
        self.order_manager = order_manager
        self.data_collector = data_collector
        self.position_tracker = position_tracker
        self.position_manager = position_manager

        self.trading_mode = config.get("trading", {}).get("mode", "PAPER")

        # NEW: Initialize State Machine
        self.state_machine = BotStateMachine(config)
        self.logger.info("✅ State Machine initialized")

        # NEW: Initialize Strategy Orchestrator
        self.orchestrator = StrategyOrchestrator(config)
        self._initialize_strategies()
        self.logger.info("✅ Strategy Orchestrator initialized")

        # Initialize indicators with caching
        cache_duration = config.get("indicators", {}).get("cacheDuration", 60)
        self.indicators_calc = Indicators(enable_cache=True, cache_duration=cache_duration)

        # Initialize regime detector and pattern detector
        self.regime_detector = RegimeDetector()
        self.pattern_detector = CandlestickPatterns()

        # Initialize risk manager
        self.risk_manager = RiskManager(config, data_collector)

        # Initialize BTC tracker
        self.btc_tracker = BTCTracker(history_hours=24)

        # Initialize correlation filter
        filters_config = config.get("filters", {})
        max_correlation = filters_config.get("maxCorrelation", 0.70)
        self.correlation_filter = CorrelationFilter(max_correlation=max_correlation)

        # Initialize Portfolio Heat Management
        self.portfolio_heat = PortfolioHeat(
            max_correlation=max_correlation,
            max_positions_per_sector=config.get("portfolio", {}).get("maxPositionsPerSector", 2),
            min_diversification_score=config.get("portfolio", {}).get("minDiversificationScore", 0.50)
        )

        # ML setup
        self.ml_enabled = config.get("ml", {}).get("enabled", False) and ML_AVAILABLE
        self.signal_predictor = None
        self.regime_classifier = None
        self._ml_initialized = False

        if self.ml_enabled:
            try:
                self.signal_predictor = SignalPredictor()
                self.regime_classifier = RegimeClassifier()
                self.logger.info("✅ ML models initialized")
                self._ml_initialized = True
            except Exception as e:
                self.logger.warning(f"Failed to initialize ML models: {e}. Continuing without ML.")
                self.ml_enabled = False

        # State tracking
        self.current_positions = 0
        self.daily_pnl = 0.0
        self.loss_streak = 0

        # Online learning manager
        self.online_learning_manager = None

        self.logger.info("🤖 TradingBotRefactored initialized successfully")

    def _initialize_strategies(self) -> None:
        """Initialize and register all strategies with orchestrator"""
        strategy_classes = [
            EmaTrendStrategy,
            MacdTrendStrategy,
            RsiMeanReversionStrategy,
            BollingerMeanReversionStrategy,
            AdxTrendStrategy,
            VolumeProfileStrategy,
            VolatilityBreakoutStrategy,
            MultiTimeframeStrategy
        ]

        for strategy_class in strategy_classes:
            try:
                strategy = strategy_class(self.config)
                self.orchestrator.register_strategy(strategy)
            except Exception as e:
                self.logger.error(f"Failed to initialize {strategy_class.__name__}: {e}")

        # Log strategy registration summary
        stats = self.orchestrator.get_statistics()
        self.logger.info(
            f"Registered {len(stats['strategies'])} strategies: "
            f"{', '.join(stats['strategies'].keys())}"
        )

    def update_state_tracking(self) -> None:
        """Update state tracking from position tracker and database"""
        if not self.position_tracker:
            return

        # Update positions count
        open_positions = self.position_tracker.get_open_positions()
        self.current_positions = len(open_positions)

        # Sync with state machine
        self.state_machine.update_position_count(self.current_positions)

        # Calculate daily PnL
        if self.data_collector and hasattr(self.data_collector, 'db'):
            try:
                from datetime import date
                today_start = datetime.combine(date.today(), datetime.min.time())

                cursor = self.data_collector.db.execute("""
                    SELECT realized_pnl, success
                    FROM trades
                    WHERE exit_time >= ? AND exit_time IS NOT NULL
                """, (today_start,))

                daily_pnl = 0.0
                recent_trades = cursor.fetchall()

                for trade in recent_trades:
                    pnl = trade[0] if trade[0] else 0.0
                    daily_pnl += pnl

                self.daily_pnl = daily_pnl

                # Calculate loss streak
                cursor = self.data_collector.db.execute("""
                    SELECT success
                    FROM trades
                    WHERE exit_time IS NOT NULL
                    ORDER BY exit_time DESC
                    LIMIT 10
                """)

                recent_results = cursor.fetchall()
                self.loss_streak = 0
                for result in recent_results:
                    if result[0] is False:
                        self.loss_streak += 1
                    else:
                        break

            except Exception as e:
                self.logger.warning(f"Error updating state tracking: {e}", exc_info=True)

        # Initialize online learning if enabled
        if self.ml_enabled and self.data_collector and self.online_learning_manager is None:
            try:
                from ml.weight_optimizer import OnlineLearningManager
                online_learning_config = self.config.get("ml", {}).get("onlineLearning", {})
                if online_learning_config.get("enabled", False):
                    self.online_learning_manager = OnlineLearningManager(self.config, self.data_collector)
                    self.logger.info("✅ Online Learning Manager initialized")
            except Exception as e:
                self.logger.warning(f"Online Learning Manager initialization failed: {e}")

    def process_symbol(
        self,
        symbol: str,
        symbol_info: Dict[str, Any],
        btc_price: float,
        equity: float
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single symbol using NEW architecture

        Flow:
        1. Check if bot can evaluate (State Machine)
        2. Get market data and calculate indicators
        3. Detect regime
        4. Check circuit breaker
        5. Evaluate strategies via Orchestrator (SEQUENTIAL!)
        6. Apply filters
        7. Execute if valid
        8. Update state machine

        Args:
            symbol: Trading symbol
            symbol_info: Symbol information
            btc_price: BTC price
            equity: Account equity

        Returns:
            Trade result OR None
        """
        try:
            # STEP 1: Check if bot can evaluate strategies
            if not self.state_machine.can_evaluate_strategies():
                self.logger.debug(
                    f"Cannot evaluate {symbol}: State={self.state_machine.get_state().value}, "
                    f"Positions={self.current_positions}"
                )
                return None

            # STEP 2: Transition to EVALUATING state
            if not self.state_machine.start_evaluation():
                return None

            # STEP 3: Get market data
            symbol_data = self.market_data.get_symbol_data(symbol)

            if not symbol_data or not symbol_data["klines"].get("m1"):
                self.state_machine.cancel_evaluation()
                return None

            # Parse klines (remove open candle to prevent lookahead bias)
            klines_m1_raw = self.indicators_calc.parse_klines(symbol_data["klines"]["m1"])
            klines_m5_raw = self.indicators_calc.parse_klines(symbol_data["klines"].get("m5", []))
            klines_m15_raw = self.indicators_calc.parse_klines(symbol_data["klines"].get("m15", []))

            klines_m1 = klines_m1_raw[:-1] if len(klines_m1_raw) > 0 else klines_m1_raw
            klines_m5 = klines_m5_raw[:-1] if len(klines_m5_raw) > 0 else klines_m5_raw
            klines_m15 = klines_m15_raw[:-1] if len(klines_m15_raw) > 0 else klines_m15_raw

            # Update portfolio heat price history
            if not klines_m1_raw.empty:
                self.portfolio_heat.update_price_history(symbol, klines_m1_raw["close"])

            if klines_m1.empty or len(klines_m1) < 50:
                self.state_machine.cancel_evaluation()
                return None

            # STEP 4: Calculate indicators
            indicators = self.indicators_calc.calculate_all(klines_m1, symbol=symbol)
            if not indicators:
                self.state_machine.cancel_evaluation()
                return None

            # Add funding rate
            funding_data = symbol_data.get("fundingRate", [])
            if funding_data:
                indicators["fundingRate"] = float(funding_data[0].get("fundingRate", 0))
            else:
                indicators["fundingRate"] = 0.0

            price = indicators["currentPrice"]

            # STEP 5: Detect regime
            regime = self.regime_detector.detect_regime(indicators, price)

            self.logger.debug(
                f"Processing {symbol}: "
                f"Price={price:.4f}, Regime={regime.get('type')}, "
                f"State={self.state_machine.get_state().value}"
            )

            # STEP 6: Check circuit breaker
            circuit_breaker_status = self.risk_manager.check_circuit_breaker(
                current_positions=self.current_positions,
                daily_pnl=self.daily_pnl,
                equity=equity,
                loss_streak=self.loss_streak
            )

            if circuit_breaker_status["tripped"]:
                self.logger.warning(
                    f"⚠️ Circuit breaker tripped: {circuit_breaker_status['reason']}"
                )
                self.state_machine.cancel_evaluation()
                return None

            # STEP 7: Evaluate strategies via Orchestrator (SEQUENTIAL!)
            final_signal = self.orchestrator.evaluate_strategies(
                indicators=indicators,
                regime=regime,
                price=price,
                candles_m1=klines_m1,
                candles_m5=klines_m5,
                candles_m15=klines_m15
            )

            if not final_signal:
                self.logger.debug(f"No valid signal for {symbol}")
                self.state_machine.cancel_evaluation()
                return None

            # STEP 8: ML Enhancement (if enabled)
            if self.ml_enabled and self.signal_predictor:
                final_signal = self._enhance_with_ml(final_signal, indicators, klines_m1, price)

            # STEP 9: Apply market filters
            if not self._market_filters(symbol_data, btc_price, indicators, final_signal):
                self.logger.debug(f"Signal for {symbol} blocked by market filters")
                self.state_machine.cancel_evaluation()
                return None

            # STEP 10: Portfolio heat filter
            if self.position_tracker:
                open_positions = self.position_tracker.get_open_positions()
                current_symbols = [pos["symbol"] for pos in open_positions.values()]

                can_add, reason = self.portfolio_heat.can_add_position(symbol, current_symbols)
                if not can_add:
                    self.logger.debug(f"Portfolio heat blocked {symbol}: {reason}")
                    self.state_machine.cancel_evaluation()
                    return None

            # STEP 11: Check if can enter position (state machine validation)
            if not self.state_machine.can_enter_position():
                self.logger.warning(f"State machine blocked entry for {symbol}")
                self.state_machine.cancel_evaluation()
                return None

            # STEP 12: Calculate position size
            historical_win_rate = None
            if hasattr(self.risk_manager, 'get_historical_win_rate'):
                historical_win_rate = self.risk_manager.get_historical_win_rate(min_trades=10)

            position = self.risk_manager.calculate_position_size(
                equity=equity,
                price=price,
                atr=indicators["atr"],
                side=final_signal["side"],
                confidence=final_signal["confidence"],
                qty_step=float(symbol_info.get("qtyStep", 0.001)),
                min_order_qty=float(symbol_info.get("minOrderQty", 0.001)),
                historical_win_rate=historical_win_rate,
                volatility=indicators.get("volatility"),
                regime=regime,
                position_tracker=self.position_tracker
            )

            if not position:
                self.state_machine.cancel_evaluation()
                return None

            # Setup multi-target exits
            position = self.risk_manager.setup_multi_target_exits(
                position,
                indicators["atr"],
                final_signal["side"]
            )

            # STEP 13: Prepare order
            order_data = {
                "symbol": symbol,
                "side": final_signal["side"],
                **position,
                "tickSize": symbol_info.get("tickSize", "0.01"),
                "qtyStep": float(symbol_info.get("qtyStep", 0.001)),
                "minOrderQty": float(symbol_info.get("minOrderQty", 0.001)),
                "volume24h": symbol_info.get("volume24h", 0),
                "volatility": indicators.get("volatility"),
                "assetType": "linear"
            }

            # STEP 14: Execute order
            execution = self.order_manager.execute_order(order_data)

            # STEP 15: Update state machine
            if execution.get("success"):
                self.state_machine.enter_position(symbol)
                self.update_state_tracking()

                self.logger.info(
                    f"✅ TRADE EXECUTED: {symbol} {final_signal['side']} "
                    f"via {final_signal['strategy']} "
                    f"(confidence={final_signal['confidence']:.2f})"
                )
            else:
                self.state_machine.cancel_evaluation()
                self.logger.warning(f"❌ Order execution failed for {symbol}")

            # STEP 16: Log trade to database
            trade_id = None
            if self.data_collector and execution.get("success"):
                try:
                    trade_id = self.data_collector.save_trade_entry(
                        symbol=symbol,
                        side=final_signal["side"],
                        entry_price=execution.get("price", price),
                        quantity=execution.get("qty", 0),
                        stop_loss=execution.get("stopLoss", 0),
                        take_profit=execution.get("takeProfit", 0),
                        confidence=final_signal.get("confidence", 0),
                        quality_score=final_signal.get("confidence", 0),  # Use confidence as quality
                        regime_type=regime.get("type", "unknown"),
                        strategies_used=[final_signal.get("strategy", "unknown")],
                        timestamp=datetime.utcnow(),
                        trading_mode=self.trading_mode
                    )

                    if trade_id:
                        self.data_collector.save_indicators(
                            trade_id=trade_id,
                            indicators=indicators,
                            current_price=price
                        )

                        self.data_collector.save_market_context(
                            trade_id=trade_id,
                            btc_price=btc_price,
                            funding_rate=indicators.get("fundingRate", 0),
                            volume_24h=symbol_info.get("volume24h", 0)
                        )

                        if self.position_manager and position.get("multiTargets"):
                            try:
                                self.position_manager.set_multi_targets(trade_id, position["multiTargets"])
                            except Exception as e:
                                self.logger.warning(f"Failed to persist multi-targets: {e}")

                except Exception as e:
                    self.logger.error(f"Error logging trade: {e}")

            # STEP 17: Get candlestick patterns
            patterns = self.pattern_detector.detect_patterns(klines_m1)

            # STEP 18: Return result
            return {
                "symbol": symbol,
                "signal": final_signal,
                "indicators": indicators,
                "regime": regime,
                "position": position,
                "execution": execution,
                "price": price,
                "btcPrice": btc_price,
                "patterns": patterns,
                "tradeId": trade_id,
                "mode": self.trading_mode,
                "config": self.config,
                "stateMachine": self.state_machine.get_status()
            }

        except Exception as e:
            self.logger.error(f"Error processing {symbol}: {e}", exc_info=True)
            self.state_machine.set_error(str(e))
            return {
                "symbol": symbol,
                "error": str(e),
                "execution": {"success": False, "error": str(e)}
            }

    def _enhance_with_ml(
        self,
        signal: Dict[str, Any],
        indicators: Dict[str, float],
        klines: pd.DataFrame,
        price: float
    ) -> Dict[str, Any]:
        """Enhance signal with ML prediction"""
        if not self.ml_enabled or not self.signal_predictor:
            return signal

        try:
            ml_prediction = self.signal_predictor.predict(indicators, price, klines)

            if not ml_prediction.get('model_enhanced'):
                return signal

            blend_ratio = self.config.get("ml", {}).get("inference", {}).get("blendRatio", 0.5)
            base_confidence = signal["confidence"]
            ml_confidence = ml_prediction.get("success_probability", 0.5)

            blended_confidence = (
                base_confidence * (1 - blend_ratio) +
                ml_confidence * blend_ratio
            )

            signal["confidence"] = blended_confidence
            signal["mlEnhanced"] = True
            signal["mlConfidence"] = ml_confidence
            signal["blendRatio"] = blend_ratio

            return signal

        except Exception as e:
            self.logger.debug(f"ML enhancement failed: {e}")
            return signal

    def _market_filters(
        self,
        symbol_data: Dict[str, Any],
        btc_price: float,
        indicators: Dict[str, float],
        signal: Dict[str, Any]
    ) -> bool:
        """Apply market filters"""
        filters_config = self.config.get("filters", {})

        # BTC crash check
        btc_crash_threshold = filters_config.get("btcCrashThreshold", -0.03)
        self.btc_tracker.update_price(btc_price)
        btc_change_24h = self.btc_tracker.get_price_change_24h(btc_price)

        if btc_change_24h is not None and btc_change_24h < btc_crash_threshold:
            return False

        # Funding rate check
        funding_rate = indicators.get("fundingRate", 0)
        funding_range = filters_config.get("fundingRateRange", {"min": -0.01, "max": 0.01})
        funding_block_enabled = filters_config.get("fundingRateBlock", True)
        funding_directional = filters_config.get("fundingRateDirectional", True)

        signal_side = signal.get("side", "")

        if funding_block_enabled and funding_directional:
            if funding_rate < funding_range["min"]:
                if signal_side == "Sell":
                    return False
                signal["confidence"] *= 0.95
            elif funding_rate > funding_range["max"]:
                if signal_side == "Buy":
                    return False
                signal["confidence"] *= 0.95

        # Correlation filter
        if self.position_tracker:
            open_positions = self.position_tracker.get_open_positions()
            existing_symbols = [pos.get("symbol") for pos in open_positions.values()]

            symbol = symbol_data.get("symbol", "")
            if symbol in existing_symbols:
                return False

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get bot status including state machine and orchestrator stats"""
        return {
            "stateMachine": self.state_machine.get_status(),
            "orchestrator": self.orchestrator.get_statistics(),
            "positions": self.current_positions,
            "dailyPnl": self.daily_pnl,
            "lossStreak": self.loss_streak,
            "mlEnabled": self.ml_enabled
        }
