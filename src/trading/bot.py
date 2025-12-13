"""Trading Bot Core Logic"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import pandas as pd
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector
from trading.candlestick_patterns import CandlestickPatterns
from trading.strategies import Strategies
from trading.risk_manager import RiskManager
from trading.order_manager import OrderManager
from trading.market_data import MarketData
from trading.btc_tracker import BTCTracker
from trading.correlation_filter import CorrelationFilter
from trading.portfolio_heat import PortfolioHeat

# ML Models
try:
    from ml.signal_predictor import SignalPredictor
    from ml.regime_classifier import RegimeClassifier
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

class TradingBot:
    """Main Trading Bot Class"""

    def __init__(
        self,
        config: Dict[str, Any],
        market_data: MarketData,
        order_manager: OrderManager,
        data_collector: Optional[Any] = None,
        position_tracker: Optional[Any] = None
    ):
        """
        Initialize Trading Bot

        Args:
            config: Configuration dictionary
            market_data: MarketData instance
            order_manager: OrderManager instance
            data_collector: DataCollector instance for logging trades
            position_tracker: PositionTracker instance for tracking positions
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.market_data = market_data
        self.order_manager = order_manager
        self.data_collector = data_collector
        self.position_tracker = position_tracker
        # Initialize indicators with caching enabled
        cache_duration = config.get("indicators", {}).get("cacheDuration", 60)
        self.indicators_calc = Indicators(enable_cache=True, cache_duration=cache_duration)
        self.regime_detector = RegimeDetector()
        self.pattern_detector = CandlestickPatterns()
        self.strategies = Strategies(config)
        self.risk_manager = RiskManager(config, data_collector)
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
        
        # ML Model Configuration
        self.ml_enabled = config.get("ml", {}).get("enabled", False) and ML_AVAILABLE
        self.signal_predictor = None
        self.regime_classifier = None

        if self.ml_enabled:
            try:
                self.signal_predictor = SignalPredictor()
                self.regime_classifier = RegimeClassifier()
                self.logger.info("ML models initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize ML models: {e}. Continuing without ML.")
                self.ml_enabled = False

        # State tracking (will be updated from position_tracker)
        self.current_positions = 0
        self.daily_pnl = 0.0
        self.loss_streak = 0
    
    def update_state_tracking(self) -> None:
        """
        Update state tracking from position tracker and database
        """
        if not self.position_tracker:
            return
        
        # Update current positions count
        open_positions = self.position_tracker.get_open_positions()
        self.current_positions = len(open_positions)
        
        # Calculate daily PnL from closed trades today
        if self.data_collector and hasattr(self.data_collector, 'db'):
            try:
                from datetime import date
                today_start = datetime.combine(date.today(), datetime.min.time())
                
                # Get all closed trades from today
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
                
                # Get loss streak (check most recent closed trades)
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
                    if result[0] is False:  # Loss
                        self.loss_streak += 1
                    else:  # Win - break streak
                        break
                        
            except Exception as e:
                self.logger.warning(
                    f"Error updating state tracking: {e}",
                    exc_info=True,
                    extra={"context": {"position_tracker": type(self.position_tracker).__name__}}
                )

        # ML Models initialization
        self.ml_enabled = self.config.get("ml", {}).get("enabled", False)
        self.signal_predictor = None
        self.regime_classifier = None
        
        # Online Learning (Phase 3)
        self.online_learning_manager = None
        if self.ml_enabled and self.data_collector:
            try:
                from ml.weight_optimizer import OnlineLearningManager
                online_learning_config = self.config.get("ml", {}).get("onlineLearning", {})
                if online_learning_config.get("enabled", False):
                    self.online_learning_manager = OnlineLearningManager(self.config, data_collector)
                    self.logger.info("Online Learning Manager initialized")
            except Exception as e:
                self.logger.warning(f"Online Learning Manager initialization failed: {e}")
            except ImportError as e:
                self.logger.debug(f"Online Learning not available: {e}")

        if self.ml_enabled and ML_AVAILABLE:
            self._initialize_ml_models()
        else:
            if self.ml_enabled and not ML_AVAILABLE:
                self.logger.warning("ML enabled but ML modules not available. Running without ML.")
            self.ml_enabled = False

    def _initialize_ml_models(self):
        """Load ML models for inference"""
        try:
            # Initialize and load Signal Predictor
            signal_predictor = SignalPredictor()
            if signal_predictor.load():
                self.signal_predictor = signal_predictor
                self.logger.info("✅ Signal Predictor loaded successfully")
            else:
                self.logger.warning("Signal Predictor model not found, running without ML enhancement")
                self.signal_predictor = None

            # Initialize and load Regime Classifier
            regime_classifier = RegimeClassifier()
            if regime_classifier.load():
                self.regime_classifier = regime_classifier
                self.logger.info("✅ Regime Classifier loaded successfully")
            else:
                self.logger.warning("Regime Classifier model not found, running without ML enhancement")
                self.regime_classifier = None

            # Set ml_enabled based on whether at least one model loaded
            if self.signal_predictor or self.regime_classifier:
                self.logger.info("✅ ML models initialized (at least one model available)")
                self.ml_enabled = True
            else:
                self.logger.warning("No ML models available. Running with base strategies only.")
                self.ml_enabled = False
        except Exception as e:
            self.logger.warning(f"Error loading ML models: {e}. Running without ML.")
            self.ml_enabled = False
    
    def ensemble_decision(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Make ensemble decision from strategy signals
        
        Args:
            signals: List of strategy signals
            
        Returns:
            Final signal dictionary or None
        """
        if not signals:
            return None
        
        # Count buy/sell signals
        buy_signals = [s for s in signals if s["side"] == "Buy"]
        sell_signals = [s for s in signals if s["side"] == "Sell"]
        
        # Use online learning weights if available, otherwise use config weights
        strategy_weights = {}
        if self.online_learning_manager and self.online_learning_manager.enabled:
            try:
                online_weights = self.online_learning_manager.get_current_weights()
                strategy_weights = online_weights
                self.logger.debug(f"Using online learning weights: {online_weights}")
            except Exception as e:
                self.logger.debug(f"Error getting online learning weights: {e}")
        
        # Fallback to config weights
        if not strategy_weights:
            for strategy_name in self.config.get("strategies", {}).keys():
                strategy_weights[strategy_name] = self.config["strategies"][strategy_name].get("weight", 1.0)
        
        # Calculate weighted confidence using dynamic weights
        def calculate_weighted_confidence(sigs: List[Dict[str, Any]]) -> float:
            weighted_sum = 0.0
            total_weight = 0.0
            
            for sig in sigs:
                strategy_name = sig["strategy"]
                weight = strategy_weights.get(strategy_name, 1.0)
                weighted_sum += sig["confidence"] * weight
                total_weight += weight
            
            return weighted_sum / total_weight if total_weight > 0 else 0.0
        
        buy_confidence = calculate_weighted_confidence(buy_signals)
        sell_confidence = calculate_weighted_confidence(sell_signals)
        
        # Determine final signal with clear decision logic
        min_confidence = self.config.get("filters", {}).get("minConfidence", 0.60)
        final_side = None
        final_confidence = 0.0
        
        # Only proceed if at least one side meets minimum confidence
        buy_meets_threshold = buy_signals and buy_confidence >= min_confidence
        sell_meets_threshold = sell_signals and sell_confidence >= min_confidence
        
        if not buy_meets_threshold and not sell_meets_threshold:
            return None
        
        # Decide based on signal count and confidence
        if buy_meets_threshold and sell_meets_threshold:
            # Both sides meet threshold - compare signal counts first
            if len(buy_signals) > len(sell_signals):
                final_side = "Buy"
                final_confidence = buy_confidence
            elif len(sell_signals) > len(buy_signals):
                final_side = "Sell"
                final_confidence = sell_confidence
            else:
                # Equal signal counts - use confidence as tie-breaker
                if buy_confidence > sell_confidence:
                    final_side = "Buy"
                    final_confidence = buy_confidence
                else:
                    final_side = "Sell"
                    final_confidence = sell_confidence
        elif buy_meets_threshold:
            final_side = "Buy"
            final_confidence = buy_confidence
        elif sell_meets_threshold:
            final_side = "Sell"
            final_confidence = sell_confidence
        
        if not final_side:
            return None

        # Calculate quality score
        agreement_ratio = max(len(buy_signals), len(sell_signals)) / len(signals)
        quality_score = final_confidence * agreement_ratio

        min_quality = self.config.get("filters", {}).get("minQualityScore", 0.50)
        if quality_score < min_quality:
            return None

        final_signal = {
            "side": final_side,
            "confidence": final_confidence,
            "qualityScore": quality_score,
            "buyCount": len(buy_signals),
            "sellCount": len(sell_signals),
            "strategiesUsed": [s["strategy"] for s in signals],
            "mlEnhanced": False
        }

        return final_signal

    def _enhance_with_ml(
        self,
        signal: Dict[str, Any],
        indicators: Dict[str, float],
        klines: pd.DataFrame,
        price: float
    ) -> Dict[str, Any]:
        """
        Enhance signal with ML prediction

        Args:
            signal: Base signal from ensemble
            indicators: Technical indicators
            klines: Historical klines
            price: Current price

        Returns:
            Enhanced signal with ML confidence
        """
        if not self.ml_enabled or not self.signal_predictor:
            return signal

        try:
            # Get ML prediction
            ml_prediction = self.signal_predictor.predict(indicators, price, klines)

            if not ml_prediction.get('model_enhanced'):
                return signal

            # Blend base confidence with ML
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
            self.logger.debug(
                f"ML enhancement failed: {e}",
                exc_info=True,
                extra={"context": {"symbol": signal.get("symbol"), "ml_enabled": self.ml_enabled}}
            )
            return signal
    
    def market_filters(
        self,
        symbol_data: Dict[str, Any],
        btc_price: float,
        indicators: Dict[str, float],
        signal: Dict[str, Any]
    ) -> bool:
        """
        Apply market filters
        
        Args:
            symbol_data: Symbol data dictionary
            btc_price: BTC price
            indicators: Indicators dictionary
            signal: Signal dictionary
            
        Returns:
            True if passes filters, False otherwise
        """
        filters_config = self.config.get("filters", {})
        
        # BTC crash check
        btc_crash_threshold = filters_config.get("btcCrashThreshold", -0.03)
        
        # Update BTC tracker with current price
        self.btc_tracker.update_price(btc_price)
        
        # Calculate BTC price change over 24 hours
        btc_change_24h = self.btc_tracker.get_price_change_24h(btc_price)
        
        if btc_change_24h is not None and btc_change_24h < btc_crash_threshold:
            # BTC crash detected - block trade
            return False
        
        # Funding rate check with directional logic
        funding_rate = indicators.get("fundingRate", 0)
        funding_range = filters_config.get("fundingRateRange", {"min": -0.01, "max": 0.01})
        funding_block_enabled = filters_config.get("fundingRateBlock", True)  # Default: block
        funding_directional = filters_config.get("fundingRateDirectional", True)  # Default: use directional logic
        
        signal_side = signal.get("side", "")
        
        if funding_block_enabled:
            # Check if funding rate is outside acceptable range
            if funding_rate < funding_range["min"] or funding_rate > funding_range["max"]:
                # Directional logic: prefer Longs when funding is negative, Shorts when positive
                if funding_directional:
                    # Extreme negative funding (> -0.01): prefer Longs, block Shorts
                    if funding_rate < funding_range["min"]:
                        if signal_side == "Sell":
                            return False  # Block shorts when funding is very negative
                        # Allow longs, but reduce confidence slightly
                        signal["confidence"] *= 0.95
                    # Extreme positive funding (> 0.01): prefer Shorts, block Longs
                    elif funding_rate > funding_range["max"]:
                        if signal_side == "Buy":
                            return False  # Block longs when funding is very positive
                        # Allow shorts, but reduce confidence slightly
                        signal["confidence"] *= 0.95
                else:
                    # Non-directional: block all trades outside range
                    return False
            else:
                # Legacy behavior: reduce confidence but don't block
                if funding_rate < funding_range["min"] or funding_rate > funding_range["max"]:
                    signal["confidence"] *= 0.8
        
        # Correlation filter check
        if self.position_tracker:
            open_positions = self.position_tracker.get_open_positions()
            existing_symbols = [pos.get("symbol") for pos in open_positions.values()]
            
            if existing_symbols:
                # Check correlation with existing positions
                # Note: This is a simplified check - full implementation would need price histories
                # For now, we check if symbol is already in positions (avoid duplicate positions)
                symbol = symbol_data.get("symbol", "")
                if symbol in existing_symbols:
                    # Symbol already in positions - block duplicate
                    return False
                
                # Future: Implement full correlation calculation with price histories
                # violation, violating_symbol = self.correlation_filter.check_correlation_violation(
                #     symbol, existing_symbols, price_histories
                # )
                # if violation:
                #     return False
        
        return True
    
    def process_symbol(
        self,
        symbol: str,
        symbol_info: Dict[str, Any],
        btc_price: float,
        equity: float
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single symbol
        
        Args:
            symbol: Trading symbol
            symbol_info: Symbol information dictionary
            btc_price: BTC price
            equity: Account equity
            
        Returns:
            Trade result dictionary or None if no trade
        """
        try:
            # Get symbol data
            symbol_data = self.market_data.get_symbol_data(symbol)
            
            if not symbol_data or not symbol_data["klines"].get("m1"):
                return None
            
            # Parse klines
            klines_m1 = self.indicators_calc.parse_klines(symbol_data["klines"]["m1"])
            klines_m5 = self.indicators_calc.parse_klines(symbol_data["klines"].get("m5", []))
            klines_m15 = self.indicators_calc.parse_klines(symbol_data["klines"].get("m15", []))
            
            # Update portfolio heat price history for correlation calculation
            if not klines_m1.empty:
                self.portfolio_heat.update_price_history(symbol, klines_m1["close"])
            
            if klines_m1.empty or len(klines_m1) < 50:
                return None
            
            # Calculate indicators (with caching)
            indicators = self.indicators_calc.calculate_all(klines_m1, symbol=symbol)
            if not indicators:
                return None
            
            # Get funding rate
            funding_data = symbol_data.get("fundingRate", [])
            if funding_data:
                indicators["fundingRate"] = float(funding_data[0].get("fundingRate", 0))
            else:
                indicators["fundingRate"] = 0.0
            
            price = indicators["currentPrice"]
            
            # Detect regime
            regime = self.regime_detector.detect_regime(indicators, price)
            
            # Run strategies
            signals = self.strategies.run_all_strategies(
                indicators,
                regime,
                price,
                klines_m1,
                klines_m5,
                klines_m15
            )
            
            # Ensemble decision
            final_signal = self.ensemble_decision(signals)
            if not final_signal:
                return None

            # ML Enhancement (if enabled)
            if self.ml_enabled:
                final_signal = self._enhance_with_ml(final_signal, indicators, klines_m1, price)

            # Market filters
            if not self.market_filters(symbol_data, btc_price, indicators, final_signal):
                return None
            
            # Portfolio Heat Filter (correlation & diversification check)
            if self.position_tracker:
                open_positions = self.position_tracker.get_open_positions()
                current_symbols = [pos["symbol"] for pos in open_positions.values()]
                
                can_add, reason = self.portfolio_heat.can_add_position(symbol, current_symbols)
                if not can_add:
                    self.logger.debug(f"Portfolio heat filter blocked {symbol}: {reason}")
                    return None
            
            # Get historical win rate for Kelly Criterion
            historical_win_rate = None
            if hasattr(self.risk_manager, 'get_historical_win_rate'):
                historical_win_rate = self.risk_manager.get_historical_win_rate(min_trades=10)
            
            # Calculate position size (with adaptive risk management)
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
                regime=regime
            )
            
            if not position:
                return None
            
            # Setup multi-target exits
            position = self.risk_manager.setup_multi_target_exits(
                position,
                indicators["atr"],
                final_signal["side"]
            )
            
            # Prepare order data
            order_data = {
                "symbol": symbol,
                "side": final_signal["side"],
                **position,
                "tickSize": symbol_info.get("tickSize", "0.01"),
                # Add data for slippage calculation
                "volume24h": symbol_info.get("volume24h", 0),
                "volatility": indicators.get("volatility"),
                "assetType": "linear"  # Default to linear futures
            }
            
            # Execute order
            execution = self.order_manager.execute_order(order_data)
            
            # Update state tracking after order execution
            if execution.get("success"):
                self.update_state_tracking()

            # Add candlestick patterns
            patterns = self.pattern_detector.detect_patterns(klines_m1)

            # Log trade to database if data collector is available
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
                        quality_score=final_signal.get("qualityScore", 0),
                        regime_type=regime.get("type", "unknown"),
                        strategies_used=final_signal.get("strategiesUsed", []),
                        timestamp=datetime.utcnow(),
                        trading_mode=self.trading_mode
                    )

                    # Save indicators if trade was created
                    if trade_id:
                        self.data_collector.save_indicators(
                            trade_id=trade_id,
                            indicators=indicators,
                            current_price=price
                        )

                        # Save market context
                        self.data_collector.save_market_context(
                            trade_id=trade_id,
                            btc_price=btc_price,
                            funding_rate=indicators.get("fundingRate", 0),
                            volume_24h=symbol_info.get("volume24h", 0)
                        )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error logging trade to database: {e}")

            # Return result
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
                "mode": self.trading_mode,  # Add trading mode (PAPER/LIVE/TESTNET)
                "config": self.config
            }
        
        except Exception as e:
            return {
                "symbol": symbol,
                "error": str(e),
                "execution": {"success": False, "error": str(e)}
            }

