"""
Base Strategy Interface

Standardisiertes Interface für alle Trading-Strategien.
Trennt Signal-Generierung von Order-Execution.

Alle Strategien MÜSSEN dieses Interface implementieren:
- check_entry(): Prüft Entry-Bedingungen
- check_exit(): Prüft Exit-Bedingungen
- get_stop_loss(): Berechnet Stop-Loss
- get_take_profit(): Berechnet Take-Profit
- get_time_exit(): Berechnet Time-Exit

Strategien dürfen NICHT:
- Orders senden
- State-Management betreiben
- Marktphasen als harte Gates verwenden
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import pandas as pd


class StrategyBase(ABC):
    """
    Base class for all trading strategies

    All strategies must implement this interface to ensure
    consistent behavior and testability.
    """

    def __init__(self, config: Dict[str, Any], name: str):
        """
        Initialize strategy

        Args:
            config: Strategy configuration
            name: Strategy name (e.g., "emaTrend")
        """
        self.config = config
        self.name = name
        self.strategy_config = config.get("strategies", {}).get(name, {})

        # Strategy metadata
        self.preferred_regimes = self.strategy_config.get("regimes", ["all"])
        self.weight = self.strategy_config.get("weight", 1.0)
        self.enabled = self.strategy_config.get("enabled", True)

    @abstractmethod
    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if entry conditions are met

        Args:
            indicators: Technical indicators
            regime: Market regime information
            price: Current price
            candles_m1: M1 candles (optional)
            candles_m5: M5 candles (optional)
            candles_m15: M15 candles (optional)

        Returns:
            Signal dictionary with side, confidence, reason OR None
            Example: {
                "side": "Buy",  # or "Sell"
                "confidence": 0.75,
                "reason": "Price > EMA8 > EMA21 in uptrend"
            }
        """
        pass

    def check_exit(
        self,
        position: Dict[str, Any],
        indicators: Dict[str, float],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if exit conditions are met

        Args:
            position: Current position data
            indicators: Technical indicators
            price: Current price
            candles_m1: M1 candles (optional)

        Returns:
            Exit signal dictionary OR None
            Example: {
                "reason": "Stop loss hit",
                "exitType": "stopLoss"
            }
        """
        # Default: no custom exit logic
        return None

    def get_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr: float,
        indicators: Dict[str, float]
    ) -> float:
        """
        Calculate stop loss price

        Args:
            entry_price: Entry price
            side: Trade side ("Buy" or "Sell")
            atr: Average True Range
            indicators: Technical indicators

        Returns:
            Stop loss price
        """
        # Default: 2x ATR stop loss
        atr_multiplier = self.config.get("risk", {}).get("atrMultiplierSL", 2.0)

        if side == "Buy":
            return entry_price - (atr * atr_multiplier)
        else:  # Sell
            return entry_price + (atr * atr_multiplier)

    def get_take_profit(
        self,
        entry_price: float,
        side: str,
        atr: float,
        indicators: Dict[str, float]
    ) -> float:
        """
        Calculate take profit price

        Args:
            entry_price: Entry price
            side: Trade side ("Buy" or "Sell")
            atr: Average True Range
            indicators: Technical indicators

        Returns:
            Take profit price
        """
        # Default: 4x ATR take profit (2:1 R:R)
        atr_multiplier = self.config.get("risk", {}).get("atrMultiplierTP", 4.0)

        if side == "Buy":
            return entry_price + (atr * atr_multiplier)
        else:  # Sell
            return entry_price - (atr * atr_multiplier)

    def get_time_exit(self) -> Optional[int]:
        """
        Get time-based exit in minutes

        Returns:
            Minutes until time exit OR None if no time exit
        """
        # Default: no time exit
        return None

    def get_regime_weight(self, regime: Dict[str, Any]) -> float:
        """
        Get strategy weight based on market regime

        This replaces hard regime gates with soft weightings.

        Args:
            regime: Market regime information

        Returns:
            Weight multiplier (0.0 to 1.0)
        """
        regime_type = regime.get("type", "ranging")

        # Check if strategy prefers this regime
        if "all" in self.preferred_regimes:
            return 1.0

        if regime_type in self.preferred_regimes:
            return 1.0  # Full weight in preferred regime

        # Reduced weight in non-preferred regimes (NOT zero!)
        # This allows strategies to still trade, just with lower priority
        return 0.3

    def get_priority_score(
        self,
        regime: Dict[str, Any],
        indicators: Dict[str, float]
    ) -> float:
        """
        Get strategy priority score for orchestration

        Higher score = higher priority in sequential evaluation

        Args:
            regime: Market regime information
            indicators: Technical indicators

        Returns:
            Priority score (0.0 to 10.0)
        """
        # Base priority from regime weight
        regime_weight = self.get_regime_weight(regime)

        # Base priority from config weight
        config_weight = self.weight

        # Combined priority
        priority = regime_weight * config_weight * 10.0

        return max(0.0, min(10.0, priority))

    def is_enabled(self) -> bool:
        """
        Check if strategy is enabled

        Returns:
            True if strategy is enabled
        """
        return self.enabled

    def get_info(self) -> Dict[str, Any]:
        """
        Get strategy information

        Returns:
            Strategy metadata
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "weight": self.weight,
            "preferredRegimes": self.preferred_regimes
        }
