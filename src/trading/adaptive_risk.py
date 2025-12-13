"""Adaptive Risk Management Utilities"""

from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class AdaptiveRiskCalculator:
    """Calculate adaptive risk parameters based on market conditions"""
    
    def calculate_volatility_adjustment(self, volatility: float) -> float:
        """
        Calculate position size adjustment based on volatility
        
        Args:
            volatility: Asset volatility (0.01 = 1%, 0.05 = 5%, etc.)
            
        Returns:
            Multiplier for position size (0.0-1.0)
        """
        if volatility <= 0.01:  # Very low volatility (<1%)
            return 1.0  # No adjustment
        elif volatility <= 0.02:  # Low volatility (1-2%)
            return 0.95
        elif volatility <= 0.03:  # Medium volatility (2-3%)
            return 0.85
        elif volatility <= 0.05:  # High volatility (3-5%)
            return 0.70
        elif volatility <= 0.10:  # Very high volatility (5-10%)
            return 0.50
        else:  # Extreme volatility (>10%)
            return 0.30
    
    def calculate_regime_adjustment(
        self,
        regime: Dict[str, Any],
        default_multipliers: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate risk adjustment based on market regime
        
        Args:
            regime: Market regime dictionary with 'type' key
            default_multipliers: Optional custom multipliers
            
        Returns:
            Multiplier for position size
        """
        if default_multipliers:
            multipliers = default_multipliers
        else:
            # Default multipliers
            multipliers = {
                "trending": 1.0,      # Full size in trending markets
                "ranging": 0.75,      # 75% in ranging markets
                "volatile": 0.5,      # 50% in volatile markets
                "unknown": 0.8        # Conservative for unknown
            }
        
        regime_type = regime.get("type", "unknown")
        return multipliers.get(regime_type, 0.8)
    
    def calculate_dynamic_kelly_fraction(
        self,
        base_win_rate: float,
        risk_reward: float,
        confidence: float,
        regime: Optional[Dict[str, Any]] = None,
        volatility: Optional[float] = None
    ) -> float:
        """
        Calculate dynamic Kelly Criterion fraction with adjustments
        
        Args:
            base_win_rate: Base win rate (0.0-1.0)
            risk_reward: Risk:Reward ratio
            confidence: Signal confidence (0.0-1.0)
            regime: Market regime (optional)
            volatility: Asset volatility (optional)
            
        Returns:
            Kelly fraction (0.0-1.0)
        """
        # Base Kelly calculation: f = (p * b - (1 - p)) / b
        # where p = win rate, b = risk:reward ratio
        if risk_reward <= 0:
            return 0.0
        
        base_kelly = (base_win_rate * risk_reward - (1 - base_win_rate)) / risk_reward
        
        # Ensure positive
        base_kelly = max(0.0, base_kelly)
        
        # Apply confidence adjustment
        confidence_factor = min(confidence / 0.7, 1.0)  # Normalize to 0.7 = 1.0
        adjusted_kelly = base_kelly * confidence_factor
        
        # Apply volatility adjustment (reduce in high volatility)
        if volatility:
            vol_factor = self.calculate_volatility_adjustment(volatility)
            adjusted_kelly *= vol_factor
        
        # Apply regime adjustment
        if regime:
            regime_factor = self.calculate_regime_adjustment(regime)
            adjusted_kelly *= regime_factor
        
        # Cap at maximum (e.g., 0.25 = 25% of equity)
        max_kelly = 0.25
        adjusted_kelly = min(adjusted_kelly, max_kelly)
        
        # Floor at minimum (e.g., 0.01 = 1% of equity)
        min_kelly = 0.01
        adjusted_kelly = max(adjusted_kelly, min_kelly)
        
        return adjusted_kelly
    
    def calculate_position_risk_multiplier(
        self,
        volatility: Optional[float] = None,
        regime: Optional[Dict[str, Any]] = None,
        drawdown: Optional[float] = None,
        loss_streak: int = 0
    ) -> float:
        """
        Calculate overall risk multiplier for position sizing
        
        Args:
            volatility: Asset volatility
            regime: Market regime
            drawdown: Current drawdown (0.0-1.0)
            loss_streak: Current loss streak count
            
        Returns:
            Risk multiplier (0.0-1.5)
        """
        multiplier = 1.0
        
        # Volatility adjustment
        if volatility:
            vol_adj = self.calculate_volatility_adjustment(volatility)
            multiplier *= vol_adj
        
        # Regime adjustment
        if regime:
            regime_adj = self.calculate_regime_adjustment(regime)
            multiplier *= regime_adj
        
        # Drawdown adjustment (reduce risk during drawdowns)
        if drawdown:
            if drawdown > 0.20:  # >20% drawdown
                multiplier *= 0.5
            elif drawdown > 0.15:  # >15% drawdown
                multiplier *= 0.7
            elif drawdown > 0.10:  # >10% drawdown
                multiplier *= 0.85
        
        # Loss streak adjustment (reduce risk after losses)
        if loss_streak >= 5:
            multiplier *= 0.5  # 50% after 5+ losses
        elif loss_streak >= 3:
            multiplier *= 0.75  # 75% after 3-4 losses
        elif loss_streak >= 2:
            multiplier *= 0.9  # 90% after 2 losses
        
        # Ensure reasonable bounds
        multiplier = max(0.1, min(1.5, multiplier))
        
        return multiplier

