"""
Strategy Orchestrator

Zentrale Orchestrierung aller Trading-Strategien.
Erzwingt sequenzielle, deterministische Ausführung.

Regeln:
- Maximal EINE Strategie pro Trade
- Strategien werden nach Priorität sortiert
- Strategien werden NACHEINANDER geprüft
- Erste valide Strategie darf handeln
- Marktphasen beeinflussen Gewichtung, NICHT Ausführung

Ablauf pro Candle Close:
1. BotState == IDLE
2. Marktphase berechnen
3. Strategien nach Priorität sortieren
4. Strategien NACHEINANDER prüfen
5. Erste valide Strategie darf handeln
6. Alle anderen werden ignoriert
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import logging
from .strategy_base import StrategyBase


class StrategyOrchestrator:
    """
    Orchestrates strategy execution

    Ensures:
    - Only one strategy trades at a time
    - Sequential evaluation (no race conditions)
    - Deterministic behavior
    - Regime-based prioritization (NOT blocking!)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize orchestrator

        Args:
            config: Bot configuration
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # Strategy registry
        self.strategies: List[StrategyBase] = []

        # Filters
        self.min_confidence = config.get("filters", {}).get("minConfidence", 0.60)
        self.min_quality_score = config.get("filters", {}).get("minQualityScore", 0.50)

        # Statistics
        self.stats = {
            "total_evaluations": 0,
            "signals_generated": 0,
            "signals_filtered": 0,
            "strategies_evaluated": {}
        }

    def register_strategy(self, strategy: StrategyBase) -> None:
        """
        Register a strategy with the orchestrator

        Args:
            strategy: Strategy instance
        """
        if strategy.is_enabled():
            self.strategies.append(strategy)
            self.logger.info(f"Strategy registered: {strategy.name}")
            self.stats["strategies_evaluated"][strategy.name] = {
                "evaluated": 0,
                "signals": 0,
                "executed": 0
            }
        else:
            self.logger.info(f"Strategy skipped (disabled): {strategy.name}")

    def evaluate_strategies(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate all strategies sequentially

        Args:
            indicators: Technical indicators
            regime: Market regime
            price: Current price
            candles_m1: M1 candles
            candles_m5: M5 candles
            candles_m15: M15 candles

        Returns:
            Best signal OR None
        """
        self.stats["total_evaluations"] += 1

        if not self.strategies:
            self.logger.warning("⚠️ No strategies registered! Cannot evaluate.")
            return None

        # Sort strategies by priority for this regime
        sorted_strategies = self._sort_strategies_by_priority(regime, indicators)

        self.logger.debug(
            f"Evaluating {len(sorted_strategies)} strategies in regime: {regime.get('type')}"
        )

        # Evaluate strategies SEQUENTIALLY
        for strategy in sorted_strategies:
            self.stats["strategies_evaluated"][strategy.name]["evaluated"] += 1

            try:
                # Check entry conditions
                signal = strategy.check_entry(
                    indicators=indicators,
                    regime=regime,
                    price=price,
                    candles_m1=candles_m1,
                    candles_m5=candles_m5,
                    candles_m15=candles_m15
                )

                if signal is None:
                    continue

                # Add strategy metadata
                signal["strategy"] = strategy.name
                signal["regimeWeight"] = strategy.get_regime_weight(regime)

                # Apply regime weighting to confidence
                regime_weight = signal["regimeWeight"]
                base_confidence = signal["confidence"]
                weighted_confidence = base_confidence * (0.7 + 0.3 * regime_weight)
                signal["baseConfidence"] = base_confidence
                signal["confidence"] = weighted_confidence

                # Validate signal
                if not self._validate_signal(signal):
                    self.logger.debug(
                        f"Signal from {strategy.name} filtered: "
                        f"confidence={signal['confidence']:.2f} (min={self.min_confidence})"
                    )
                    self.stats["signals_filtered"] += 1
                    continue

                # Signal is valid - return immediately (first valid strategy wins)
                self.stats["signals_generated"] += 1
                self.stats["strategies_evaluated"][strategy.name]["signals"] += 1

                self.logger.info(
                    f"✅ Signal generated by {strategy.name}: {signal['side']} "
                    f"(confidence={signal['confidence']:.2f}, regime_weight={regime_weight:.2f})"
                )

                return signal

            except Exception as e:
                self.logger.error(
                    f"Error evaluating strategy {strategy.name}: {e}",
                    exc_info=True
                )
                continue

        # No strategy produced a valid signal
        self.logger.debug(f"No valid signals from {len(sorted_strategies)} strategies")
        return None

    def get_strategy_by_name(self, name: str) -> Optional[StrategyBase]:
        """
        Get strategy by name

        Args:
            name: Strategy name

        Returns:
            Strategy instance OR None
        """
        for strategy in self.strategies:
            if strategy.name == name:
                return strategy
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics

        Returns:
            Statistics dictionary
        """
        return {
            "total_evaluations": self.stats["total_evaluations"],
            "signals_generated": self.stats["signals_generated"],
            "signals_filtered": self.stats["signals_filtered"],
            "signal_rate": (
                self.stats["signals_generated"] / self.stats["total_evaluations"]
                if self.stats["total_evaluations"] > 0
                else 0.0
            ),
            "strategies": self.stats["strategies_evaluated"]
        }

    def _sort_strategies_by_priority(
        self,
        regime: Dict[str, Any],
        indicators: Dict[str, float]
    ) -> List[StrategyBase]:
        """
        Sort strategies by priority for current market conditions

        Args:
            regime: Market regime
            indicators: Technical indicators

        Returns:
            Sorted list of strategies (highest priority first)
        """
        # Calculate priority for each strategy
        strategy_priorities = []
        for strategy in self.strategies:
            priority = strategy.get_priority_score(regime, indicators)
            strategy_priorities.append((strategy, priority))

        # Sort by priority (descending)
        strategy_priorities.sort(key=lambda x: x[1], reverse=True)

        # Log priority order
        priority_order = [
            f"{s.name}({p:.1f})" for s, p in strategy_priorities
        ]
        self.logger.debug(f"Strategy priority order: {', '.join(priority_order)}")

        return [s for s, p in strategy_priorities]

    def _validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate signal meets minimum requirements

        Args:
            signal: Signal dictionary

        Returns:
            True if signal is valid
        """
        # Check required fields
        required_fields = ["side", "confidence", "strategy"]
        for field in required_fields:
            if field not in signal:
                self.logger.warning(f"Signal missing required field: {field}")
                return False

        # Check confidence threshold
        if signal["confidence"] < self.min_confidence:
            return False

        # Check side is valid
        if signal["side"] not in ["Buy", "Sell"]:
            self.logger.warning(f"Invalid signal side: {signal['side']}")
            return False

        return True

    def reset_statistics(self) -> None:
        """Reset orchestrator statistics"""
        self.stats = {
            "total_evaluations": 0,
            "signals_generated": 0,
            "signals_filtered": 0,
            "strategies_evaluated": {
                name: {"evaluated": 0, "signals": 0, "executed": 0}
                for name in self.stats["strategies_evaluated"].keys()
            }
        }
        self.logger.info("Orchestrator statistics reset")
