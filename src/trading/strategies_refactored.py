"""
Refactored Trading Strategies

8 Core Trading Strategies mit standardisiertem Interface.
Verwendet StrategyBase für konsistentes Verhalten.

WICHTIG:
- Keine hardcoded Regime-Gates mehr
- Regime beeinflusst Gewichtung, NICHT Ausführung
- Strategien können in allen Regimes handeln (mit reduzierter Gewichtung)
"""

from typing import Dict, Any, Optional
import pandas as pd
from .strategy_base import StrategyBase


class EmaTrendStrategy(StrategyBase):
    """Strategy 1: EMA Trend (bevorzugt trending markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "emaTrend")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check EMA trend entry conditions"""
        ema8 = indicators.get("ema8", price)
        ema21 = indicators.get("ema21", price)

        # Bullish setup
        if price > ema8 and ema8 > ema21:
            # Stronger signal in uptrend
            base_confidence = 0.75 if regime.get("isBullish") else 0.65
            return {
                "side": "Buy",
                "confidence": base_confidence,
                "reason": "Price > EMA8 > EMA21 (bullish alignment)"
            }

        # Bearish setup
        elif price < ema8 and ema8 < ema21:
            # Stronger signal in downtrend
            base_confidence = 0.75 if regime.get("isBearish") else 0.65
            return {
                "side": "Sell",
                "confidence": base_confidence,
                "reason": "Price < EMA8 < EMA21 (bearish alignment)"
            }

        return None


class MacdTrendStrategy(StrategyBase):
    """Strategy 2: MACD Trend (bevorzugt trending markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "macdTrend")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check MACD trend entry conditions"""
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macdSignal", 0)
        macd_hist = indicators.get("macdHist", 0)

        # Bullish crossover
        if macd > macd_signal and macd_hist > 0:
            base_confidence = 0.70 if regime.get("isBullish") else 0.60
            return {
                "side": "Buy",
                "confidence": base_confidence,
                "reason": "MACD bullish crossover with positive histogram"
            }

        # Bearish crossover
        elif macd < macd_signal and macd_hist < 0:
            base_confidence = 0.70 if regime.get("isBearish") else 0.60
            return {
                "side": "Sell",
                "confidence": base_confidence,
                "reason": "MACD bearish crossover with negative histogram"
            }

        return None


class RsiMeanReversionStrategy(StrategyBase):
    """Strategy 3: RSI Mean Reversion (bevorzugt ranging markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "rsiMeanReversion")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check RSI mean reversion entry conditions"""
        rsi = indicators.get("rsi", 50)

        # Oversold - expect bounce
        if rsi < 30:
            # Stronger in ranging markets
            base_confidence = 0.68 if regime.get("type") == "ranging" else 0.58
            return {
                "side": "Buy",
                "confidence": base_confidence,
                "reason": f"RSI oversold ({rsi:.1f}), expecting bounce"
            }

        # Overbought - expect pullback
        elif rsi > 70:
            # Stronger in ranging markets
            base_confidence = 0.68 if regime.get("type") == "ranging" else 0.58
            return {
                "side": "Sell",
                "confidence": base_confidence,
                "reason": f"RSI overbought ({rsi:.1f}), expecting pullback"
            }

        return None


class BollingerMeanReversionStrategy(StrategyBase):
    """Strategy 4: Bollinger Mean Reversion (bevorzugt ranging markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "bollingerMeanReversion")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check Bollinger mean reversion entry conditions"""
        bb_upper = indicators.get("bbUpper", price)
        bb_lower = indicators.get("bbLower", price)

        # At lower band - expect bounce
        if price <= bb_lower:
            base_confidence = 0.72 if regime.get("type") == "ranging" else 0.62
            return {
                "side": "Buy",
                "confidence": base_confidence,
                "reason": "Price at lower Bollinger Band, expecting bounce"
            }

        # At upper band - expect pullback
        elif price >= bb_upper:
            base_confidence = 0.72 if regime.get("type") == "ranging" else 0.62
            return {
                "side": "Sell",
                "confidence": base_confidence,
                "reason": "Price at upper Bollinger Band, expecting pullback"
            }

        return None


class AdxTrendStrategy(StrategyBase):
    """Strategy 5: ADX Trend Strength (bevorzugt trending markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "adxTrend")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check ADX trend strength entry conditions"""
        adx = indicators.get("adx", 0)

        # Strong trend confirmed
        if adx > 30:
            if regime.get("isBullish"):
                return {
                    "side": "Buy",
                    "confidence": 0.78,
                    "reason": f"Strong uptrend confirmed by ADX={adx:.1f}"
                }
            elif regime.get("isBearish"):
                return {
                    "side": "Sell",
                    "confidence": 0.78,
                    "reason": f"Strong downtrend confirmed by ADX={adx:.1f}"
                }

        # Moderate trend
        elif adx > 20:
            if regime.get("isBullish"):
                return {
                    "side": "Buy",
                    "confidence": 0.65,
                    "reason": f"Moderate uptrend (ADX={adx:.1f})"
                }
            elif regime.get("isBearish"):
                return {
                    "side": "Sell",
                    "confidence": 0.65,
                    "reason": f"Moderate downtrend (ADX={adx:.1f})"
                }

        return None


class VolumeProfileStrategy(StrategyBase):
    """Strategy 6: Volume Profile with VWAP (all markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "volumeProfile")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check volume profile entry conditions"""
        if candles_m1 is None or candles_m1.empty or len(candles_m1) < 20:
            return None

        recent_candles = candles_m1.tail(20)
        avg_volume = recent_candles["volume"].mean()
        recent_vol = recent_candles.tail(3)["volume"].mean()
        current_price = candles_m1.iloc[-1]["close"]

        # Check for volume spike
        volume_spike = recent_vol > avg_volume * 1.5

        if not volume_spike:
            return None

        # VWAP analysis
        vwap = indicators.get("vwap", current_price)
        price_vs_vwap = (current_price - vwap) / vwap if vwap > 0 else 0

        # Bullish: Price above VWAP with high volume
        if price_vs_vwap > 0.001 and regime.get("isBullish"):
            confidence = 0.68 + min(price_vs_vwap * 10, 0.08)
            return {
                "side": "Buy",
                "confidence": min(confidence, 0.85),
                "reason": f"High volume above VWAP ({price_vs_vwap*100:.2f}%)"
            }

        # Bearish: Price below VWAP with high volume
        elif price_vs_vwap < -0.001 and regime.get("isBearish"):
            confidence = 0.68 + min(abs(price_vs_vwap) * 10, 0.08)
            return {
                "side": "Sell",
                "confidence": min(confidence, 0.85),
                "reason": f"High volume below VWAP ({price_vs_vwap*100:.2f}%)"
            }

        return None


class VolatilityBreakoutStrategy(StrategyBase):
    """Strategy 7: Volatility Breakout (bevorzugt volatile markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "volatilityBreakout")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check volatility breakout entry conditions"""
        if candles_m1 is None or candles_m1.empty or len(candles_m1) < 20:
            return None

        atr = indicators.get("atr", 0)
        if atr <= 0:
            return None

        atr_percent = atr / price
        if atr_percent < 0.03:  # Not enough volatility
            return None

        # Volume confirmation
        recent_candles = candles_m1.tail(20)
        avg_volume = recent_candles["volume"].mean()
        current_volume = candles_m1.iloc[-1]["volume"]
        volume_spike = current_volume > avg_volume * 1.3

        if not volume_spike:
            return None

        # Breakout confirmation
        recent_high = recent_candles["high"].max()
        recent_low = recent_candles["low"].min()
        current_high = candles_m1.iloc[-1]["high"]
        current_low = candles_m1.iloc[-1]["low"]

        # Bullish breakout
        if regime.get("isBullish") and current_high >= recent_high * 0.998:
            confidence = 0.78 if current_high > recent_high else 0.75
            # Boost in volatile regime
            if regime.get("type") == "volatile":
                confidence += 0.05
            return {
                "side": "Buy",
                "confidence": min(confidence, 0.85),
                "reason": f"Volatility breakout upside (ATR={atr_percent*100:.2f}%)"
            }

        # Bearish breakout
        elif regime.get("isBearish") and current_low <= recent_low * 1.002:
            confidence = 0.78 if current_low < recent_low else 0.75
            # Boost in volatile regime
            if regime.get("type") == "volatile":
                confidence += 0.05
            return {
                "side": "Sell",
                "confidence": min(confidence, 0.85),
                "reason": f"Volatility breakdown downside (ATR={atr_percent*100:.2f}%)"
            }

        return None


class MultiTimeframeStrategy(StrategyBase):
    """Strategy 8: Multi-Timeframe Analysis (all markets)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, "multiTimeframe")

    def check_entry(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None
    ) -> Optional[Dict[str, Any]]:
        """Check multi-timeframe entry conditions"""
        if (candles_m1 is None or candles_m5 is None or candles_m15 is None or
            candles_m1.empty or candles_m5.empty or candles_m15.empty or
            len(candles_m5) < 50 or len(candles_m15) < 50):
            return None

        # Calculate EMAs for each timeframe
        from .indicators import Indicators
        ind_calc = Indicators()

        ema21_m1 = ind_calc.ema(candles_m1["close"], 21)
        ema21_m5 = ind_calc.ema(candles_m5["close"], 21)
        ema21_m15 = ind_calc.ema(candles_m15["close"], 21)

        ema50_m5 = ind_calc.ema(candles_m5["close"], 50)
        ema50_m15 = ind_calc.ema(candles_m15["close"], 50)

        # Get current values
        price_m1 = candles_m1.iloc[-1]["close"]
        price_m5 = candles_m5.iloc[-1]["close"]
        price_m15 = candles_m15.iloc[-1]["close"]

        ema21_m1_val = ema21_m1.iloc[-1] if len(ema21_m1) > 0 else price_m1
        ema21_m5_val = ema21_m5.iloc[-1] if len(ema21_m5) > 0 else price_m5
        ema21_m15_val = ema21_m15.iloc[-1] if len(ema21_m15) > 0 else price_m15
        ema50_m5_val = ema50_m5.iloc[-1] if len(ema50_m5) > 0 else price_m5
        ema50_m15_val = ema50_m15.iloc[-1] if len(ema50_m15) > 0 else price_m15

        # Check alignment
        m1_bullish = price_m1 > ema21_m1_val
        m5_bullish = price_m5 > ema21_m5_val > ema50_m5_val
        m15_bullish = price_m15 > ema21_m15_val > ema50_m15_val

        m1_bearish = price_m1 < ema21_m1_val
        m5_bearish = price_m5 < ema21_m5_val < ema50_m5_val
        m15_bearish = price_m15 < ema21_m15_val < ema50_m15_val

        # RSI confirmation
        rsi = indicators.get("rsi", 50)
        rsi_bullish = 45 < rsi < 75
        rsi_bearish = 25 < rsi < 55

        # Bullish alignment
        if m1_bullish and m5_bullish and m15_bullish and regime.get("isBullish"):
            confidence = 0.80 if rsi_bullish else 0.76
            return {
                "side": "Buy",
                "confidence": confidence,
                "reason": "Bullish EMA alignment across M1, M5, M15"
            }

        # Bearish alignment
        elif m1_bearish and m5_bearish and m15_bearish and regime.get("isBearish"):
            confidence = 0.80 if rsi_bearish else 0.76
            return {
                "side": "Sell",
                "confidence": confidence,
                "reason": "Bearish EMA alignment across M1, M5, M15"
            }

        return None
