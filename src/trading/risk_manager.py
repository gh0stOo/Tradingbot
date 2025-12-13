"""Risk Management Module"""

from typing import Dict, Optional, Any
from decimal import Decimal, ROUND_DOWN
import logging

from utils.exceptions import CalculationError, ValidationError

logger = logging.getLogger(__name__)

class RiskManager:
    """Risk Management and Position Sizing"""
    
    def __init__(self, config: Dict[str, Any], data_collector: Optional[Any] = None):
        """
        Initialize Risk Manager
        
        Args:
            config: Configuration dictionary
            data_collector: DataCollector instance for historical data (optional)
        """
        self.config = config
        self.risk_config = config.get("risk", {})
        self.kelly_config = self.risk_config.get("kelly", {})
        self.multi_target_config = config.get("multiTargetExits", {})
        self.data_collector = data_collector
    
    def get_historical_win_rate(self, min_trades: int = 10) -> Optional[float]:
        """
        Calculate historical win rate from closed trades
        
        Args:
            min_trades: Minimum number of trades required to calculate win rate
            
        Returns:
            Win rate (0.0-1.0) or None if insufficient data
        """
        if not self.data_collector or not hasattr(self.data_collector, 'db'):
            return None
        
        try:
            cursor = self.data_collector.db.execute("""
                SELECT success
                FROM trades
                WHERE exit_time IS NOT NULL AND success IS NOT NULL
                ORDER BY exit_time DESC
                LIMIT 100
            """)
            
            results = cursor.fetchall()
            if len(results) < min_trades:
                return None
            
            wins = sum(1 for r in results if r[0] is True)
            total = len(results)
            win_rate = wins / total if total > 0 else None
            
            return win_rate
        except Exception as e:
            logger.warning(f"Error calculating historical win rate: {e}", exc_info=True)
            return None
    
    def calculate_position_size(
        self,
        equity: float,
        price: float,
        atr: float,
        side: str,
        confidence: float,
        qty_step: float,
        min_order_qty: float,
        historical_win_rate: Optional[float] = None,
        volatility: Optional[float] = None,
        regime: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate position size based on risk
        
        Args:
            equity: Account equity
            price: Entry price
            atr: Average True Range
            side: Trade side (Buy/Sell)
            confidence: Signal confidence
            qty_step: Quantity step size
            min_order_qty: Minimum order quantity
            
        Returns:
            Dictionary with position size details or None if invalid
        """
        # Validation
        try:
            if equity <= 0:
                raise ValidationError(f"Invalid equity: {equity}. Must be > 0")
            if price <= 0:
                raise ValidationError(f"Invalid price: {price}. Must be > 0")
            if atr <= 0:
                raise ValidationError(f"Invalid ATR: {atr}. Must be > 0")
            if side not in ["Buy", "Sell"]:
                raise ValidationError(f"Invalid side: {side}. Must be 'Buy' or 'Sell'")
            if not 0 <= confidence <= 1:
                raise ValidationError(f"Invalid confidence: {confidence}. Must be between 0 and 1")
            if qty_step <= 0:
                raise ValidationError(f"Invalid qty_step: {qty_step}. Must be > 0")
            if min_order_qty <= 0:
                raise ValidationError(f"Invalid min_order_qty: {min_order_qty}. Must be > 0")
        except ValidationError:
            raise
        except Exception as e:
            raise CalculationError(f"Error validating position size parameters: {e}")
        
        # Risk amount
        risk_pct = self.risk_config.get("riskPct", 0.02)
        risk_amount = equity * risk_pct
        
        # Stop loss distance
        atr_multiplier_sl = self.risk_config.get("atrMultiplierSL", 2.0)
        sl_distance = atr * atr_multiplier_sl
        
        # Calculate stop loss price
        if side == "Buy":
            sl_price = price - sl_distance
        else:
            sl_price = price + sl_distance
        
        # Take profit distance
        atr_multiplier_tp = self.risk_config.get("atrMultiplierTP", 4.0)
        tp_distance = atr * atr_multiplier_tp
        
        # Calculate take profit price
        if side == "Buy":
            tp_price = price + tp_distance
        else:
            tp_price = price - tp_distance
        
        # Risk per unit
        risk_per_unit = abs(price - sl_price)
        if risk_per_unit == 0:
            return None
        
        # Risk:Reward ratio
        reward_per_unit = abs(tp_price - price)
        rr = reward_per_unit / risk_per_unit
        
        min_rr = self.risk_config.get("minRR", 2.0)
        if rr < min_rr:
            return None
        
        # Base quantity
        base_qty = risk_amount / risk_per_unit
        
        # Apply Kelly Criterion if enabled (with regime-based adjustment)
        if self.kelly_config.get("enabled", False):
            # Use historical win rate if available, otherwise use config minWinRate
            # Confidence can be used as a multiplier but not as win rate itself
            if historical_win_rate is not None and historical_win_rate > 0:
                base_p = max(historical_win_rate, self.kelly_config.get("minWinRate", 0.40))
            else:
                # Fallback to config minWinRate if no historical data
                base_p = self.kelly_config.get("minWinRate", 0.40)
            
            # Apply confidence as a multiplier (reduce position size if confidence is low)
            confidence_multiplier = min(confidence / 0.7, 1.0)  # Normalize to 0.7 = 1.0
            
            # Regime-based Kelly adjustment
            kelly_adjustment = 1.0
            if regime:
                regime_type = regime.get("type", "unknown")
                kelly_adjustments = self.kelly_config.get("regimeAdjustments", {})
                
                if regime_type in kelly_adjustments:
                    kelly_adjustment = kelly_adjustments[regime_type]
                else:
                    # Default adjustments
                    if regime_type == "volatile":
                        kelly_adjustment = 0.7  # Reduce Kelly in volatile markets
                    elif regime_type == "trending":
                        kelly_adjustment = 1.0  # Full Kelly in trending markets
                    elif regime_type == "ranging":
                        kelly_adjustment = 0.85  # Slight reduction in ranging markets
            
            p = base_p * confidence_multiplier * kelly_adjustment
            
            b = max(rr, self.kelly_config.get("minRR", 1.5))
            q = 1 - p
            
            # Kelly formula: f = (p*b - q) / b
            kelly_fraction = (p * b - q) / b if b > 0 else 0
            kelly_fraction = max(0, min(kelly_fraction, 1))  # Cap at 0-100%
            
            # Apply Kelly fraction with safety multiplier
            kelly_adjusted = kelly_fraction * self.kelly_config.get("fraction", 0.25)
            
            base_qty = base_qty * kelly_adjusted
        
        # Round to qty_step
        rounded_qty = (base_qty // qty_step) * qty_step
        
        # Check minimum
        if rounded_qty < min_order_qty:
            return None
        
        # Check max exposure
        notional_value = rounded_qty * price
        max_exposure = equity * self.risk_config.get("maxExposure", 0.50)
        required_margin = notional_value / self.risk_config.get("leverageMax", 10)
        
        if required_margin > max_exposure:
            return None
        
        return {
            "qty": float(rounded_qty),
            "price": price,
            "stopLoss": float(sl_price),
            "takeProfit": float(tp_price),
            "riskReward": float(rr),
            "notionalValue": float(notional_value),
            "leverage": min(
                self.risk_config.get("leverageMax", 10),
                int(notional_value / (equity * 0.5))
            ),
            "riskAmount": float(risk_amount)
        }
    
    def setup_multi_target_exits(
        self,
        position: Dict[str, Any],
        atr: float,
        side: str
    ) -> Dict[str, Any]:
        """
        Setup multi-target exits (supports 2-4 targets dynamically)

        INTERNAL CALCULATION FUNCTION - Results passed to OrderManager for execution.
        Do not make API calls here. OrderManager is responsible for order execution.

        Args:
            position: Position dictionary with qty and price
            atr: Average True Range
            side: Trade side (Buy/Sell)

        Returns:
            Position dictionary with multi-target exits
        """
        if not self.multi_target_config.get("enabled", False):
            return position
        
        qty = position["qty"]
        entry_price = position["price"]
        
        # Determine which TP levels are configured (tp1-tp4)
        available_tps = []
        for tp_key in ["tp1", "tp2", "tp3", "tp4"]:
            if tp_key in self.multi_target_config:
                available_tps.append(tp_key)
        
        if not available_tps:
            return position
        
        # Calculate TP levels dynamically
        multi_targets = {"enabled": True}
        tp_configs = []
        
        for tp_key in available_tps:
            tp_config = self.multi_target_config[tp_key]
            tp_distance = atr * tp_config.get("distance", 1.5)
            
            if side == "Buy":
                tp_price = entry_price + tp_distance
            else:
                tp_price = entry_price - tp_distance
            
            tp_configs.append({
                "key": tp_key,
                "price": float(tp_price),
                "size": tp_config.get("size", 0.25)
            })
        
        # Calculate quantities for each TP level
        total_allocated = 0.0
        for i, tp_config in enumerate(tp_configs):
            if i == len(tp_configs) - 1:
                # Last TP gets remaining quantity
                tp_qty = qty - total_allocated
            else:
                tp_qty = float(int(qty * tp_config["size"]))
                total_allocated += tp_qty
            
            multi_targets[tp_config["key"]] = {
                "price": tp_config["price"],
                "qty": float(tp_qty)
            }
        
        position["multiTargets"] = multi_targets
        
        return position
    
    def check_circuit_breaker(
        self,
        current_positions: int,
        daily_pnl: float,
        equity: float,
        loss_streak: int
    ) -> Dict[str, Any]:
        """
        Check circuit breaker conditions
        
        Args:
            current_positions: Current number of open positions
            daily_pnl: Today's PnL
            equity: Account equity
            loss_streak: Current loss streak
            
        Returns:
            Dictionary with circuit breaker status
        """
        circuit_config = self.config.get("circuitBreaker", {})
        if not circuit_config.get("enabled", False):
            return {"tripped": False, "reason": None}
        
        max_positions = self.risk_config.get("maxPositions", 3)
        if current_positions >= max_positions:
            return {
                "tripped": True,
                "reason": f"Max positions reached: {current_positions}/{max_positions}"
            }
        
        max_daily_drawdown = circuit_config.get("maxDailyDrawdown", 0.05)
        if daily_pnl < 0 and abs(daily_pnl / equity) > max_daily_drawdown:
            return {
                "tripped": True,
                "reason": f"Max daily drawdown exceeded: {abs(daily_pnl / equity) * 100:.2f}%"
            }
        
        max_loss_streak = circuit_config.get("maxLossStreak", 3)
        if loss_streak >= max_loss_streak:
            return {
                "tripped": True,
                "reason": f"Max loss streak reached: {loss_streak}"
            }

        return {"tripped": False, "reason": None}

    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion fraction for optimal position sizing

        Args:
            win_rate: Historical win rate (0.0-1.0)
            avg_win: Average win amount per trade
            avg_loss: Average loss amount per trade

        Returns:
            Kelly fraction (0.0-1.0)
        """
        try:
            if not 0 <= win_rate <= 1:
                logger.warning(f"Invalid win_rate: {win_rate}. Using default.")
                return 0.25

            if avg_loss <= 0:
                logger.warning(f"Invalid avg_loss: {avg_loss}. Using default.")
                return 0.25

            if avg_win <= 0:
                logger.warning(f"Invalid avg_win: {avg_win}. Using default.")
                return 0.25

            # Kelly formula: f = (bp - q) / b
            # where b = avg_win / avg_loss, p = win_rate, q = 1 - win_rate
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - p

            kelly_fraction = (b * p - q) / b if b > 0 else 0

            # Cap at 0-1 range (0-100%)
            kelly_fraction = max(0, min(kelly_fraction, 1))

            logger.debug(f"Kelly fraction calculated: {kelly_fraction:.4f} (win_rate={p:.2f}, b={b:.2f})")
            return kelly_fraction

        except Exception as e:
            logger.error(f"Error calculating Kelly fraction: {e}")
            return 0.25

