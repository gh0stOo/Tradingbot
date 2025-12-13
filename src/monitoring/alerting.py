"""Alerting System for Trading Bot"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Alert:
    """Represents an alert"""
    
    def __init__(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.level = level
        self.title = title
        self.message = message
        self.source = source
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.acknowledged = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged
        }


class AlertManager:
    """Manage alerts and notifications"""
    
    def __init__(self):
        """Initialize Alert Manager"""
        self.alerts: List[Alert] = []
        self.handlers: List[Callable[[Alert], None]] = []
        self.alert_history: List[Alert] = []
        self.max_history = 1000
    
    def register_handler(self, handler: Callable[[Alert], None]) -> None:
        """
        Register alert handler
        
        Args:
            handler: Function to handle alerts (takes Alert as parameter)
        """
        self.handlers.append(handler)
    
    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Send an alert
        
        Args:
            level: Alert level
            title: Alert title
            message: Alert message
            source: Alert source
            metadata: Optional metadata
            
        Returns:
            Created alert
        """
        alert = Alert(level, title, message, source, metadata)
        self.alerts.append(alert)
        self.alert_history.append(alert)
        
        # Trim history
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        
        # Call handlers
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in alert handler: {e}", exc_info=True)
        
        logger.log(
            getattr(logging, level.value.upper(), logging.INFO),
            f"ALERT [{level.value.upper()}]: {title} - {message}"
        )
        
        return alert
    
    def check_circuit_breaker_alert(
        self,
        circuit_breaker_result: Dict[str, Any]
    ) -> Optional[Alert]:
        """Check if circuit breaker should trigger alert"""
        if circuit_breaker_result.get("tripped"):
            return self.send_alert(
                level=AlertLevel.CRITICAL,
                title="Circuit Breaker Tripped",
                message=f"Trading halted: {circuit_breaker_result.get('reason', 'Unknown')}",
                source="risk_manager",
                metadata=circuit_breaker_result
            )
        return None
    
    def check_performance_alert(
        self,
        win_rate: float,
        daily_pnl: float,
        loss_streak: int
    ) -> List[Alert]:
        """Check for performance-related alerts"""
        alerts = []
        
        # Low win rate alert
        if win_rate < 0.40:  # <40% win rate
            alerts.append(self.send_alert(
                level=AlertLevel.WARNING,
                title="Low Win Rate",
                message=f"Win rate is {win_rate*100:.1f}% (below 40%)",
                source="performance",
                metadata={"win_rate": win_rate}
            ))
        
        # High loss streak
        if loss_streak >= 5:
            alerts.append(self.send_alert(
                level=AlertLevel.WARNING,
                title="High Loss Streak",
                message=f"Current loss streak: {loss_streak} trades",
                source="performance",
                metadata={"loss_streak": loss_streak}
            ))
        
        # Large daily loss
        if daily_pnl < -1000:  # Loss > $1000
            alerts.append(self.send_alert(
                level=AlertLevel.WARNING,
                title="Large Daily Loss",
                message=f"Daily PnL: ${daily_pnl:.2f}",
                source="performance",
                metadata={"daily_pnl": daily_pnl}
            ))
        
        return alerts
    
    def check_api_error_alert(
        self,
        error_count: int,
        error_rate: float
    ) -> Optional[Alert]:
        """Check for API error alerts"""
        if error_rate > 0.10:  # >10% error rate
            return self.send_alert(
                level=AlertLevel.ERROR,
                title="High API Error Rate",
                message=f"API error rate: {error_rate*100:.1f}% ({error_count} errors)",
                source="api",
                metadata={"error_count": error_count, "error_rate": error_rate}
            )
        return None
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """Get active (unacknowledged) alerts"""
        alerts = [a for a in self.alerts if not a.acknowledged]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts
    
    def acknowledge_alert(self, alert: Alert) -> None:
        """Acknowledge an alert"""
        alert.acknowledged = True
        if alert in self.alerts:
            self.alerts.remove(alert)
    
    def clear_old_alerts(self, days: int = 7) -> int:
        """Clear alerts older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        old_count = len(self.alerts)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff]
        return old_count - len(self.alerts)


def discord_alert_handler(webhook_url: str) -> Callable[[Alert], None]:
    """
    Create Discord webhook alert handler
    
    Args:
        webhook_url: Discord webhook URL
        
    Returns:
        Alert handler function
    """
    import requests
    
    def handler(alert: Alert) -> None:
        """Send alert to Discord"""
        try:
            # Color mapping
            colors = {
                AlertLevel.INFO: 0x3498db,      # Blue
                AlertLevel.WARNING: 0xf39c12,   # Orange
                AlertLevel.ERROR: 0xe74c3c,     # Red
                AlertLevel.CRITICAL: 0x8e44ad   # Purple
            }
            
            payload = {
                "embeds": [{
                    "title": alert.title,
                    "description": alert.message,
                    "color": colors.get(alert.level, 0x95a5a6),
                    "fields": [
                        {"name": "Level", "value": alert.level.value.upper(), "inline": True},
                        {"name": "Source", "value": alert.source, "inline": True},
                        {"name": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"), "inline": False}
                    ],
                    "timestamp": alert.timestamp.isoformat()
                }]
            }
            
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
    
    return handler


def send_discord_trade_signal(webhook_url: str, trade_result: Dict[str, Any], signal_type: str = "signal") -> bool:
    """
    Send trade signal or execution notification directly to Discord
    
    Args:
        webhook_url: Discord webhook URL
        trade_result: Trade result dictionary from bot
        signal_type: "signal" for signal notification, "execution" for execution notification
        
    Returns:
        True if successful, False otherwise
    """
    import requests
    from datetime import datetime
    
    try:
        signal = trade_result.get("signal", {})
        execution = trade_result.get("execution", {})
        position = trade_result.get("position", {})
        indicators = trade_result.get("indicators", {})
        regime = trade_result.get("regime", {})
        
        symbol = trade_result.get("symbol", "UNKNOWN")
        side = signal.get("side", "Hold")
        
        # Get price from indicators.currentPrice or execution or trade_result
        price = (
            indicators.get("currentPrice") or 
            execution.get("price") or 
            signal.get("price") or 
            trade_result.get("price") or 
            0.0
        )
        
        confidence = signal.get("confidence", 0.0)
        strategies = signal.get("strategiesUsed", [])
        
        # Extract regime type properly
        if isinstance(regime, dict):
            regime_type = regime.get("type", "unknown")
        elif isinstance(regime, str):
            regime_type = regime
        else:
            regime_type = "unknown"
        
        # Determine color based on side
        color = 0x00ff00 if side == "Buy" else 0xff0000  # Green for Buy, Red for Sell
        
        # Determine title and emoji
        if signal_type == "execution":
            title = "✅ Trade Executed" if execution.get("success") else "❌ Trade Execution Failed"
            status_emoji = "✅" if execution.get("success") else "❌"
        else:
            title = "🚀 New Trading Signal"
            status_emoji = "🎯"
        
        # Get trading mode from result
        trading_mode = trade_result.get("mode", "PAPER")
        mode_emoji = "📄" if trading_mode == "PAPER" else "💵" if trading_mode == "LIVE" else "🧪"
        
        # Build fields
        fields = [
            {"name": "Symbol", "value": symbol, "inline": True},
            {"name": "Side", "value": f"{'🟢' if side == 'Buy' else '🔴' if side == 'Sell' else '⚪'} {side}", "inline": True},
            {"name": "Price", "value": f"${price:,.4f}" if price > 0 else "N/A", "inline": True},
            {"name": "Confidence", "value": f"{confidence*100:.1f}%" if confidence > 0 else "N/A", "inline": True},
            {"name": "Market Regime", "value": regime_type.capitalize(), "inline": True},
            {"name": "Mode", "value": f"{mode_emoji} {trading_mode}", "inline": True},
        ]
        
        # Add execution details if available
        if signal_type == "execution" and execution:
            order_id = execution.get("orderId", "N/A")
            fields.append({"name": "Order ID", "value": f"`{order_id}`", "inline": False})
            if execution.get("success"):
                fields.append({"name": "Status", "value": "✅ Executed Successfully", "inline": True})
            else:
                error = execution.get("error", "Unknown error")
                fields.append({"name": "Error", "value": f"❌ {error}", "inline": False})
        
        # Add position details if available
        if position:
            qty = position.get("qty")
            stop_loss = position.get("stopLoss")
            take_profit = position.get("takeProfit")
            
            if qty:
                fields.append({"name": "Quantity", "value": f"{qty:.4f}", "inline": True})
            if stop_loss:
                fields.append({"name": "Stop Loss", "value": f"${stop_loss:,.4f}", "inline": True})
            if take_profit:
                fields.append({"name": "Take Profit", "value": f"${take_profit:,.4f}", "inline": True})
            
            # Multi-target exits with potential profit and probability
            multi_targets = position.get("multiTargets", {})
            if multi_targets:
                tp_list = []
                qty = position.get("qty", 0)
                
                # Estimated probabilities based on target distance (can be improved with historical data)
                # Closer targets have higher probability
                probability_map = {
                    "tp1": 0.65,  # 65% probability for TP1 (closest)
                    "tp2": 0.45,  # 45% probability for TP2
                    "tp3": 0.30,  # 30% probability for TP3
                    "tp4": 0.18   # 18% probability for TP4 (furthest)
                }
                
                for tp_key in sorted(multi_targets.keys()):
                    tp_data = multi_targets[tp_key]
                    tp_price = tp_data.get("price", 0)
                    tp_size = tp_data.get("size", 0) * 100
                    
                    # Calculate potential profit for this target
                    if side == "Buy":
                        profit_per_unit = tp_price - price
                    else:  # Sell
                        profit_per_unit = price - tp_price
                    
                    # Calculate profit for the portion size of this target
                    target_qty = qty * tp_data.get("size", 0)
                    potential_profit = profit_per_unit * target_qty
                    
                    # Get probability for this target
                    prob = probability_map.get(tp_key.lower(), 0.25) * 100
                    
                    # Format: TP1: $Price (25%) | Profit: $XXX.XX | Prob: 65%
                    tp_list.append(
                        f"**{tp_key.upper()}**: ${tp_price:,.4f} ({tp_size:.0f}%) | "
                        f"💰 ${potential_profit:,.2f} | "
                        f"📊 {prob:.0f}%"
                    )
                
                fields.append({"name": "🎯 Multi-Target Exits", "value": "\n".join(tp_list), "inline": False})
                
                # Calculate total potential profit if all targets hit
                total_potential_profit = 0
                for tp_key in sorted(multi_targets.keys()):
                    tp_data = multi_targets[tp_key]
                    tp_price = tp_data.get("price", 0)
                    target_qty = qty * tp_data.get("size", 0)
                    
                    if side == "Buy":
                        profit_per_unit = tp_price - price
                    else:
                        profit_per_unit = price - tp_price
                    
                    total_potential_profit += profit_per_unit * target_qty
                
                # Add total potential profit summary
                fields.append({
                    "name": "💰 Total Potential Profit (All Targets)",
                    "value": f"${total_potential_profit:,.2f}",
                    "inline": True
                })
        
        # Add strategies
        if strategies:
            fields.append({"name": "Strategies", "value": ", ".join(strategies), "inline": False})
        
        # Add regime
        fields.append({"name": "Market Regime", "value": regime.capitalize(), "inline": True})
        
        # Add trading mode if available
        mode = trade_result.get("mode", "PAPER")
        mode_emoji = "📄" if mode == "PAPER" else "🔥" if mode == "LIVE" else "🧪"
        fields.append({"name": "Mode", "value": f"{mode_emoji} {mode}", "inline": True})
        
        payload = {
            "embeds": [{
                "title": title,
                "color": color,
                "fields": fields,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Crypto Trading Bot"
                }
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Discord {signal_type} notification sent for {symbol}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send Discord {signal_type} notification: {e}")
        return False

