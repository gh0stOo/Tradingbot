"""Trading Strategies Module - 8 Core Strategies"""

from typing import Dict, List, Any, Optional
import pandas as pd

class Strategies:
    """8 Core Trading Strategies"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategies
        
        Args:
            config: Configuration dictionary with strategy weights
        """
        self.config = config
        self.strategy_configs = config.get("strategies", {})
    
    def ema_trend(self, indicators: Dict[str, float], regime: Dict[str, Any], price: float) -> Optional[Dict[str, Any]]:
        """Strategy 1: EMA Trend (trending markets)"""
        if regime["type"] != "trending":
            return None
        
        ema8 = indicators.get("ema8", price)
        ema21 = indicators.get("ema21", price)
        
        if regime["isBullish"] and price > ema8 and ema8 > ema21:
            return {
                "strategy": "emaTrend",
                "side": "Buy",
                "confidence": 0.75,
                "reason": "Price > EMA8 > EMA21 in uptrend"
            }
        elif regime["isBearish"] and price < ema8 and ema8 < ema21:
            return {
                "strategy": "emaTrend",
                "side": "Sell",
                "confidence": 0.75,
                "reason": "Price < EMA8 < EMA21 in downtrend"
            }
        
        return None
    
    def macd_trend(self, indicators: Dict[str, float], regime: Dict[str, Any], price: float = None) -> Optional[Dict[str, Any]]:
        """Strategy 2: MACD Trend (trending markets)"""
        if regime["type"] != "trending":
            return None
        
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macdSignal", 0)
        macd_hist = indicators.get("macdHist", 0)
        
        if macd > macd_signal and macd_hist > 0:
            return {
                "strategy": "macdTrend",
                "side": "Buy",
                "confidence": 0.70,
                "reason": "MACD bullish crossover with positive histogram"
            }
        elif macd < macd_signal and macd_hist < 0:
            return {
                "strategy": "macdTrend",
                "side": "Sell",
                "confidence": 0.70,
                "reason": "MACD bearish crossover with negative histogram"
            }
        
        return None
    
    def rsi_mean_reversion(self, indicators: Dict[str, float], regime: Dict[str, Any], price: float = None) -> Optional[Dict[str, Any]]:
        """Strategy 3: RSI Mean Reversion (ranging markets)"""
        if regime["type"] != "ranging":
            return None
        
        rsi = indicators.get("rsi", 50)
        
        if rsi < 30:
            return {
                "strategy": "rsiMeanReversion",
                "side": "Buy",
                "confidence": 0.68,
                "reason": "RSI oversold in ranging market"
            }
        elif rsi > 70:
            return {
                "strategy": "rsiMeanReversion",
                "side": "Sell",
                "confidence": 0.68,
                "reason": "RSI overbought in ranging market"
            }
        
        return None
    
    def bollinger_mean_reversion(self, indicators: Dict[str, float], regime: Dict[str, Any], price: float) -> Optional[Dict[str, Any]]:
        """Strategy 4: Bollinger Mean Reversion (ranging markets)"""
        if regime["type"] != "ranging":
            return None
        
        bb_upper = indicators.get("bbUpper", price)
        bb_lower = indicators.get("bbLower", price)
        
        if price <= bb_lower:
            return {
                "strategy": "bollingerMeanReversion",
                "side": "Buy",
                "confidence": 0.72,
                "reason": "Price at lower Bollinger Band"
            }
        elif price >= bb_upper:
            return {
                "strategy": "bollingerMeanReversion",
                "side": "Sell",
                "confidence": 0.72,
                "reason": "Price at upper Bollinger Band"
            }
        
        return None
    
    def adx_trend(self, indicators: Dict[str, float], regime: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Strategy 5: ADX Trend Strength (trending markets)"""
        if regime["type"] != "trending":
            return None
        
        adx = indicators.get("adx", 0)
        
        if adx > 30:
            if regime["isBullish"]:
                return {
                    "strategy": "adxTrend",
                    "side": "Buy",
                    "confidence": 0.78,
                    "reason": "Strong uptrend confirmed by ADX > 30"
                }
            elif regime["isBearish"]:
                return {
                    "strategy": "adxTrend",
                    "side": "Sell",
                    "confidence": 0.78,
                    "reason": "Strong downtrend confirmed by ADX > 30"
                }
        
        return None
    
    def volume_profile(
        self,
        candles_m1: pd.DataFrame,
        regime: Dict[str, Any],
        indicators: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Strategy 6: Volume Profile with VWAP Integration (all markets)"""
        if candles_m1.empty or len(candles_m1) < 20:
            return None
        
        recent_candles = candles_m1.tail(20)
        avg_volume = recent_candles["volume"].mean()
        recent_vol = recent_candles.tail(3)["volume"].mean()
        current_price = candles_m1.iloc[-1]["close"]
        
        # Check for volume spike
        volume_spike = recent_vol > avg_volume * 1.5
        
        # VWAP analysis
        vwap = indicators.get("vwap", current_price)
        price_vs_vwap = (current_price - vwap) / vwap if vwap > 0 else 0
        
        # Volume-weighted price areas: check if price is above/below VWAP with high volume
        if volume_spike:
            # Bullish: Price above VWAP with high volume
            if price_vs_vwap > 0.001 and regime.get("isBullish"):
                confidence = 0.68 + min(price_vs_vwap * 10, 0.08)  # Boost confidence if well above VWAP
                return {
                    "strategy": "volumeProfile",
                    "side": "Buy",
                    "confidence": min(confidence, 0.85),
                    "reason": f"High volume above VWAP confirming uptrend (Price-VWAP: {price_vs_vwap*100:.2f}%)"
                }
            # Bearish: Price below VWAP with high volume
            elif price_vs_vwap < -0.001 and regime.get("isBearish"):
                confidence = 0.68 + min(abs(price_vs_vwap) * 10, 0.08)
                return {
                    "strategy": "volumeProfile",
                    "side": "Sell",
                    "confidence": min(confidence, 0.85),
                    "reason": f"High volume below VWAP confirming downtrend (Price-VWAP: {price_vs_vwap*100:.2f}%)"
                }
        
        return None
    
    def volatility_breakout(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """Strategy 7: Volatility Breakout with Confirmation (volatile markets)"""
        if regime["type"] != "volatile":
            return None
        
        if candles_m1.empty or len(candles_m1) < 20:
            return None
        
        atr = indicators.get("atr", 0)
        if atr <= 0:
            return None
        
        atr_percent = atr / price
        if atr_percent < 0.03:  # Not enough volatility
            return None
        
        # Volume confirmation: check for volume spike
        recent_candles = candles_m1.tail(20)
        avg_volume = recent_candles["volume"].mean()
        current_volume = candles_m1.iloc[-1]["volume"]
        volume_spike = current_volume > avg_volume * 1.3
        
        # Breakout confirmation: price should be making new highs/lows
        recent_high = recent_candles["high"].max()
        recent_low = recent_candles["low"].min()
        current_high = candles_m1.iloc[-1]["high"]
        current_low = candles_m1.iloc[-1]["low"]
        
        # Bullish breakout: new high with volume
        if regime.get("isBullish") and current_high >= recent_high * 0.998:  # Near or above recent high
            if volume_spike:
                confidence = 0.75
                if current_high > recent_high:
                    confidence = 0.78  # Strong breakout
                return {
                    "strategy": "volatilityBreakout",
                    "side": "Buy",
                    "confidence": confidence,
                    "reason": f"High volatility breakout to upside with volume confirmation (ATR: {atr_percent*100:.2f}%)"
                }
        
        # Bearish breakout: new low with volume
        elif regime.get("isBearish") and current_low <= recent_low * 1.002:  # Near or below recent low
            if volume_spike:
                confidence = 0.75
                if current_low < recent_low:
                    confidence = 0.78  # Strong breakdown
                return {
                    "strategy": "volatilityBreakout",
                    "side": "Sell",
                    "confidence": confidence,
                    "reason": f"High volatility breakdown to downside with volume confirmation (ATR: {atr_percent*100:.2f}%)"
                }
        
        return None
    
    def multi_timeframe(
        self,
        candles_m1: pd.DataFrame,
        candles_m5: pd.DataFrame,
        candles_m15: pd.DataFrame,
        regime: Dict[str, Any],
        indicators: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Strategy 8: Multi-Timeframe Analysis with EMA Alignment (all markets)"""
        if (candles_m1.empty or candles_m5.empty or candles_m15.empty or
            len(candles_m5) < 50 or len(candles_m15) < 50):
            return None
        
        # Calculate EMAs for each timeframe
        from trading.indicators import Indicators
        ind_calc = Indicators()
        
        ema21_m1 = ind_calc.ema(candles_m1["close"], 21)
        ema21_m5 = ind_calc.ema(candles_m5["close"], 21)
        ema21_m15 = ind_calc.ema(candles_m15["close"], 21)
        
        ema50_m5 = ind_calc.ema(candles_m5["close"], 50)
        ema50_m15 = ind_calc.ema(candles_m15["close"], 50)
        
        # Get current prices and EMAs
        price_m1 = candles_m1.iloc[-1]["close"]
        price_m5 = candles_m5.iloc[-1]["close"]
        price_m15 = candles_m15.iloc[-1]["close"]
        
        ema21_m1_val = ema21_m1.iloc[-1] if len(ema21_m1) > 0 else price_m1
        ema21_m5_val = ema21_m5.iloc[-1] if len(ema21_m5) > 0 else price_m5
        ema21_m15_val = ema21_m15.iloc[-1] if len(ema21_m15) > 0 else price_m15
        ema50_m5_val = ema50_m5.iloc[-1] if len(ema50_m5) > 0 else price_m5
        ema50_m15_val = ema50_m15.iloc[-1] if len(ema50_m15) > 0 else price_m15
        
        # Check EMA alignment (bullish: price > EMA21 > EMA50 across timeframes)
        m1_bullish = price_m1 > ema21_m1_val
        m5_bullish = price_m5 > ema21_m5_val > ema50_m5_val
        m15_bullish = price_m15 > ema21_m15_val > ema50_m15_val
        
        # Check EMA alignment (bearish: price < EMA21 < EMA50 across timeframes)
        m1_bearish = price_m1 < ema21_m1_val
        m5_bearish = price_m5 < ema21_m5_val < ema50_m5_val
        m15_bearish = price_m15 < ema21_m15_val < ema50_m15_val
        
        # Calculate RSI for momentum confirmation
        rsi = indicators.get("rsi", 50)
        rsi_bullish = 45 < rsi < 75  # Not oversold, but not overbought yet
        rsi_bearish = 25 < rsi < 55  # Not overbought, but not oversold yet
        
        # Bullish alignment with momentum
        if m1_bullish and m5_bullish and m15_bullish and regime.get("isBullish"):
            confidence = 0.76
            if rsi_bullish:
                confidence = 0.80  # Boost confidence with RSI confirmation
            return {
                "strategy": "multiTimeframe",
                "side": "Buy",
                "confidence": confidence,
                "reason": "Bullish EMA alignment across M1, M5, M15 with momentum confirmation"
            }
        
        # Bearish alignment with momentum
        elif m1_bearish and m5_bearish and m15_bearish and regime.get("isBearish"):
            confidence = 0.76
            if rsi_bearish:
                confidence = 0.80  # Boost confidence with RSI confirmation
            return {
                "strategy": "multiTimeframe",
                "side": "Sell",
                "confidence": confidence,
                "reason": "Bearish EMA alignment across M1, M5, M15 with momentum confirmation"
            }
        
        return None
    
    def run_all_strategies(
        self,
        indicators: Dict[str, float],
        regime: Dict[str, Any],
        price: float,
        candles_m1: Optional[pd.DataFrame] = None,
        candles_m5: Optional[pd.DataFrame] = None,
        candles_m15: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Run all strategies and filter by regime
        
        Args:
            indicators: Dictionary with indicator values
            regime: Regime dictionary
            price: Current price
            candles_m1: M1 candles DataFrame
            candles_m5: M5 candles DataFrame
            candles_m15: M15 candles DataFrame
            
        Returns:
            List of strategy signals
        """
        signals = []
        
        # Accept legacy kwargs (klines, klines_m5, klines_m15)
        candles_m1 = kwargs.get("klines", candles_m1)
        candles_m5 = kwargs.get("klines_m5", candles_m5 if candles_m5 is not None else candles_m1)
        candles_m15 = kwargs.get("klines_m15", candles_m15 if candles_m15 is not None else candles_m1)

        # Strategy regime mapping
        strategy_regimes = {
            "emaTrend": ["trending"],
            "macdTrend": ["trending"],
            "rsiMeanReversion": ["ranging"],
            "bollingerMeanReversion": ["ranging"],
            "adxTrend": ["trending"],
            "volumeProfile": ["all"],
            "volatilityBreakout": ["volatile"],
            "multiTimeframe": ["all"]
        }
        
        # Run all strategies (with updated signatures)
        cm1 = candles_m1
        cm5 = candles_m5 if candles_m5 is not None else candles_m1
        cm15 = candles_m15 if candles_m15 is not None else candles_m1

        strategy_results = [
            self.ema_trend(indicators, regime, price),
            self.macd_trend(indicators, regime),
            self.rsi_mean_reversion(indicators, regime),
            self.bollinger_mean_reversion(indicators, regime, price),
            self.adx_trend(indicators, regime),
            self.volume_profile(cm1, regime, indicators),
            self.volatility_breakout(indicators, regime, price, cm1),
            self.multi_timeframe(cm1, cm5, cm15, regime, indicators)
        ]
        
        # Filter by regime and collect valid signals
        for signal in strategy_results:
            if signal is None:
                continue
            
            strategy_name = signal["strategy"]
            allowed_regimes = strategy_regimes.get(strategy_name, [])
            
            # Check if strategy is allowed for current regime
            if "all" in allowed_regimes or regime["type"] in allowed_regimes:
                signals.append(signal)
        
        return signals

