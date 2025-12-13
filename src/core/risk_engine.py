"""Risk Engine with Veto Power - Central Risk Management"""

import logging
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime, timedelta

from events.order_intent_event import OrderIntentEvent
from events.risk_approval_event import RiskApprovalEvent
from events.kill_switch_event import KillSwitchEvent
from events.system_health_event import SystemHealthEvent
from core.trading_state import TradingState

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Central Risk Engine with veto power.
    
    Evaluates all order intents and can block trades or trigger kill switch.
    All risk checks must pass before a trade is approved.
    """
    
    def __init__(self, config: Dict, trading_state: TradingState) -> None:
        """
        Initialize Risk Engine.
        
        Args:
            config: Configuration dictionary with risk settings
            trading_state: TradingState instance
        """
        self.config = config
        self.risk_config = config.get("risk", {})
        self.circuit_breaker_config = config.get("circuitBreaker", {})
        self.trading_state = trading_state
        
        # Risk limits (from config or defaults)
        self.max_risk_per_trade = Decimal(str(self.risk_config.get("riskPct", 0.002)))  # 0.2% default
        self.max_daily_loss = Decimal(str(self.risk_config.get("maxDailyLoss", 0.005)))  # 0.5% default
        self.max_trades_per_day = self.risk_config.get("maxTradesPerDay", 10)
        self.max_exposure_per_asset = Decimal(str(self.risk_config.get("maxExposurePerAsset", 0.10)))  # 10%
        self.max_drawdown_limit = Decimal(str(self.circuit_breaker_config.get("maxDailyDrawdown", 0.05)))  # 5%
        
        # Track daily trades per asset
        self._trades_per_asset_today: Dict[str, int] = {}
        self._last_reset_date: datetime = datetime.utcnow().date()
        
        logger.info("RiskEngine initialized")
    
    def evaluate_order_intent(self, event: OrderIntentEvent) -> RiskApprovalEvent:
        """
        Evaluate order intent and generate approval/rejection event.
        
        This method should be called by an event handler when OrderIntentEvent is received.
        
        Args:
            event: OrderIntentEvent to evaluate
            
        Returns:
            RiskApprovalEvent with approval decision
        """
        try:
            # Reset daily counters if new day
            self._reset_daily_counters_if_needed()
            
            # Check 1: Trading enabled
            if not self.trading_state.trading_enabled:
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason="Trading is disabled",
                    source=event.source
                )
            
            # Check 2: Daily loss limit (kill switch check)
            daily_loss_check = self._check_daily_loss_limit()
            if not daily_loss_check["passed"]:
                # Trigger kill switch
                self._trigger_kill_switch(daily_loss_check["reason"])
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=f"Kill switch triggered: {daily_loss_check['reason']}",
                    source=event.source
                )
            
            # Check 3: Drawdown limit (kill switch check)
            drawdown_check = self._check_drawdown_limit()
            if not drawdown_check["passed"]:
                self._trigger_kill_switch(drawdown_check["reason"])
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=f"Kill switch triggered: {drawdown_check['reason']}",
                    source=event.source
                )
            
            # Check 4: Risk per trade
            risk_check = self._check_risk_per_trade(
                event.quantity,
                event.entry_price,
                event.stop_loss,
                event.side
            )
            if not risk_check["passed"]:
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=risk_check["reason"],
                    source=event.source
                )
            
            # Check 5: Max trades per day
            trades_check = self._check_max_trades_per_day()
            if not trades_check["passed"]:
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=trades_check["reason"],
                    source=event.source
                )
            
            # Check 6: Max exposure per asset
            exposure_check = self._check_max_exposure_per_asset(event.symbol, event.quantity, event.entry_price)
            if not exposure_check["passed"]:
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=exposure_check["reason"],
                    source=event.source
                )
            
            # Check 7: Position conflict (already have position in this asset)
            if self._has_position_conflict(event.symbol, event.side):
                return RiskApprovalEvent(
                    order_intent_id=event.event_id,
                    approved=False,
                    reason=f"Position conflict: Already have position in {event.symbol}",
                    source=event.source
                )
            
            # All checks passed - approve with possible adjustments
            return RiskApprovalEvent(
                order_intent_id=event.event_id,
                approved=True,
                reason="All risk checks passed",
                adjusted_quantity=float(event.quantity),
                adjusted_stop_loss=float(event.stop_loss),
                adjusted_take_profit=float(event.take_profit),
                risk_metrics=risk_check.get("metrics", {}),
                original_intent=event,
                source=event.source
            )
        
        except Exception as e:
            logger.error(f"Error evaluating order intent: {e}", exc_info=True)
            return RiskApprovalEvent(
                order_intent_id=event.event_id,
                approved=False,
                reason=f"Error in risk evaluation: {str(e)}",
                source=event.source
            )
    
    def _check_daily_loss_limit(self) -> Dict:
        """Check if daily loss limit is breached"""
        daily_pnl = self.trading_state.daily_pnl
        equity = self.trading_state.equity
        
        if equity <= 0:
            return {"passed": False, "reason": "Equity is zero or negative"}
        
        daily_loss_pct = abs(daily_pnl) / equity if daily_pnl < 0 else Decimal("0")
        
        if daily_loss_pct >= self.max_daily_loss:
            return {
                "passed": False,
                "reason": f"Daily loss limit breached: {float(daily_loss_pct * 100):.2f}% >= {float(self.max_daily_loss * 100):.2f}%"
            }
        
        return {"passed": True}
    
    def _check_drawdown_limit(self) -> Dict:
        """Check if drawdown limit is breached"""
        drawdown_pct = self.trading_state.drawdown_percent
        
        if drawdown_pct >= self.max_drawdown_limit:
            return {
                "passed": False,
                "reason": f"Drawdown limit breached: {float(drawdown_pct):.2f}% >= {float(self.max_drawdown_limit):.2f}%"
            }
        
        return {"passed": True}
    
    def _check_max_daily_loss(self) -> Dict:
        """Check if max daily loss is breached"""
        daily_pnl = self.trading_state.daily_pnl
        daily_start_equity = self.trading_state.daily_start_equity
        
        if daily_start_equity <= 0:
            return {"passed": True}  # Cannot check if starting equity is invalid
        
        max_daily_loss = daily_start_equity * self.max_daily_loss  # max_daily_loss is already a percentage (e.g., 0.005 = 0.5%)
        
        if daily_pnl <= -max_daily_loss:  # Negative PnL (loss)
            return {
                "passed": False,
                "reason": f"Max daily loss breached: {float(daily_pnl):.2f} <= -{float(max_daily_loss):.2f}"
            }
        
        return {"passed": True}
    
    def _check_risk_per_trade(
        self,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        side: str
    ) -> Dict:
        """Check if risk per trade is within limits"""
        equity = self.trading_state.equity
        
        if equity <= 0:
            return {"passed": False, "reason": "Equity is zero or negative"}
        
        # Validate stop loss is reasonable
        if side == "Buy":
            if stop_loss >= entry_price:
                return {"passed": False, "reason": "Stop loss must be below entry price for long position"}
            if stop_loss <= 0:
                return {"passed": False, "reason": "Stop loss must be positive"}
            risk_per_unit = entry_price - stop_loss
        else:  # Sell
            if stop_loss <= entry_price:
                return {"passed": False, "reason": "Stop loss must be above entry price for short position"}
            if stop_loss <= 0:
                return {"passed": False, "reason": "Stop loss must be positive"}
            risk_per_unit = stop_loss - entry_price
        
        if risk_per_unit <= 0:
            return {"passed": False, "reason": "Invalid stop loss (risk per unit <= 0)"}
        
        # Check stop loss distance is reasonable (not too wide)
        risk_pct_of_price = risk_per_unit / entry_price
        if risk_pct_of_price > Decimal("0.20"):  # Max 20% risk
            return {
                "passed": False,
                "reason": f"Stop loss too wide: {float(risk_pct_of_price * 100):.2f}% of price (max 20%)"
            }
        
        # Total risk for this trade
        total_risk = risk_per_unit * quantity
        risk_pct = total_risk / equity
        
        if risk_pct > self.max_risk_per_trade:
            return {
                "passed": False,
                "reason": f"Risk per trade too high: {float(risk_pct * 100):.2f}% > {float(self.max_risk_per_trade * 100):.2f}%"
            }
        
        return {
            "passed": True,
            "metrics": {
                "risk_per_trade": float(risk_pct),
                "risk_amount": float(total_risk)
            }
        }
    
    def _check_max_trades_per_day(self) -> Dict:
        """Check if max trades per day is reached"""
        trades_today = self.trading_state.trades_today
        
        if trades_today >= self.max_trades_per_day:
            return {
                "passed": False,
                "reason": f"Max trades per day reached: {trades_today} >= {self.max_trades_per_day}"
            }
        
        return {"passed": True}
    
    def _check_max_exposure_per_asset(
        self,
        symbol: str,
        quantity: Decimal,
        entry_price: Decimal
    ) -> Dict:
        """Check if exposure per asset is within limits"""
        equity = self.trading_state.equity
        
        if equity <= 0:
            return {"passed": False, "reason": "Equity is zero or negative"}
        
        # Calculate new exposure
        new_exposure = quantity * entry_price
        existing_exposure = Decimal(str(self.trading_state.get_exposure_per_asset().get(symbol, 0)))
        total_exposure = existing_exposure + new_exposure
        
        max_exposure_amount = equity * self.max_exposure_per_asset
        
        if total_exposure > max_exposure_amount:
            return {
                "passed": False,
                "reason": f"Max exposure per asset exceeded: {float(total_exposure)} > {float(max_exposure_amount)}"
            }
        
        return {"passed": True}
    
    def _has_position_conflict(self, symbol: str, side: str) -> bool:
        """Check if there's a position conflict (opposite side)"""
        position = self.trading_state.get_position(symbol)
        
        if position:
            # If we have a position, we can only add to it if same side, or close it if opposite
            # For now, we block new positions if one already exists
            return True
        
        return False
    
    def _trigger_kill_switch(self, reason: str) -> None:
        """Trigger kill switch (disable trading)"""
        self.trading_state.disable_trading()
        logger.critical(f"Kill switch triggered: {reason}")
    
    def _reset_daily_counters_if_needed(self) -> None:
        """Reset daily counters if new day"""
        today = datetime.utcnow().date()
        if today != self._last_reset_date:
            self._trades_per_asset_today.clear()
            self._last_reset_date = today
            logger.info("Daily risk counters reset")

