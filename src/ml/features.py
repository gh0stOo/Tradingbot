"""
Feature Engineering Module for ML Training

Generiert abgeleitete Features aus technischen Indikatoren für XGBoost und Random Forest Models
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


class FeatureEngineer:
    """Engineered Features aus rohen Indikatoren"""

    @staticmethod
    def engineer_features(indicators: Dict, price: float, klines: pd.DataFrame) -> Dict:
        """
        Generiere abgeleitete Features

        Args:
            indicators: Technische Indikatoren (RSI, MACD, ATR, etc.)
            price: Aktueller Preis
            klines: Historical klines DataFrame

        Returns:
            Dictionary mit allen Features (raw + engineered)
        """

        features = {}

        # ==================== DIREKTE FEATURES (17) ====================
        # Aus Indikatoren direkt
        features.update(FeatureEngineer._extract_raw_features(indicators))

        # ==================== TREND FEATURES ====================
        features.update(FeatureEngineer._engineer_trend_features(indicators, price))

        # ==================== MOMENTUM FEATURES ====================
        features.update(FeatureEngineer._engineer_momentum_features(indicators))

        # ==================== VOLATILITY FEATURES ====================
        features.update(FeatureEngineer._engineer_volatility_features(indicators, price))

        # ==================== VOLUME FEATURES ====================
        features.update(FeatureEngineer._engineer_volume_features(indicators, price))

        # ==================== MARKET STRUCTURE FEATURES ====================
        features.update(FeatureEngineer._engineer_structure_features(klines, price))

        return features

    @staticmethod
    def _extract_raw_features(indicators: Dict) -> Dict:
        """Extrahiere direkte Indikatoren"""
        return {
            # Trend
            'rsi': float(indicators.get('rsi', 50)),
            'adx': float(indicators.get('adx', 20)),
            'macd': float(indicators.get('macd', 0)),
            'macd_signal': float(indicators.get('macdSignal', 0)),
            'macd_hist': float(indicators.get('macdHist', 0)),

            # Volatility
            'atr': float(indicators.get('atr', 0.01)),
            'bb_upper': float(indicators.get('bbUpper', 0)),
            'bb_middle': float(indicators.get('bbMiddle', 0)),
            'bb_lower': float(indicators.get('bbLower', 0)),

            # Moving Averages
            'ema8': float(indicators.get('ema8', 0)),
            'ema21': float(indicators.get('ema21', 0)),
            'ema50': float(indicators.get('ema50', 0)),
            'ema200': float(indicators.get('ema200', 0)),

            # Stochastic
            'stoch_k': float(indicators.get('stochK', 50)),
            'stoch_d': float(indicators.get('stochD', 50)),

            # Volume & Price
            'vwap': float(indicators.get('vwap', 0)),
            'volatility': float(indicators.get('volatility', 0.01)),
        }

    @staticmethod
    def _engineer_trend_features(indicators: Dict, price: float) -> Dict:
        """Trend-basierte Features"""
        features = {}

        ema8 = indicators.get('ema8', price)
        ema21 = indicators.get('ema21', price)
        ema50 = indicators.get('ema50', price)
        ema200 = indicators.get('ema200', price)

        # EMA Alignment
        features['ema_aligned_bullish'] = float(
            (ema8 > ema21 > ema50 > ema200) and (ema8 > ema200 * 1.01)
        )
        features['ema_aligned_bearish'] = float(
            (ema8 < ema21 < ema50 < ema200) and (ema8 < ema200 * 0.99)
        )

        # Price vs EMA
        features['price_vs_ema50_pct'] = (price - ema50) / ema50 if ema50 > 0 else 0
        features['price_vs_ema200_pct'] = (price - ema200) / ema200 if ema200 > 0 else 0
        features['ema8_vs_ema50'] = (ema8 - ema50) / ema50 if ema50 > 0 else 0

        # Slope indicators
        macd = indicators.get('macd', 0)
        macd_hist = indicators.get('macdHist', 0)
        atr = indicators.get('atr', 0.01)

        features['macd_trend_strength'] = abs(macd_hist) / atr if atr > 0 else 0
        features['macd_positive'] = float(macd > 0)

        # ADX Strength
        adx = indicators.get('adx', 20)
        features['adx_strong_trend'] = float(adx > 25)
        features['adx_weak_trend'] = float(adx < 20)

        return features

    @staticmethod
    def _engineer_momentum_features(indicators: Dict) -> Dict:
        """Momentum-basierte Features"""
        features = {}

        rsi = indicators.get('rsi', 50)
        stoch_k = indicators.get('stochK', 50)
        stoch_d = indicators.get('stochD', 50)

        # RSI Zones
        features['rsi_oversold'] = float(rsi < 30)
        features['rsi_overbought'] = float(rsi > 70)
        features['rsi_neutral'] = float(30 <= rsi <= 70)
        features['rsi_extreme_oversold'] = float(rsi < 20)
        features['rsi_extreme_overbought'] = float(rsi > 80)

        # Stochastic
        features['stoch_oversold'] = float(stoch_k < 20)
        features['stoch_overbought'] = float(stoch_k > 80)
        features['stoch_momentum'] = stoch_k - stoch_d
        features['stoch_aligned_bullish'] = float(stoch_k > stoch_d and stoch_k > 50)
        features['stoch_aligned_bearish'] = float(stoch_k < stoch_d and stoch_k < 50)

        # Momentum direction
        features['momentum_bullish'] = float(rsi > 50 and stoch_k > 50)
        features['momentum_bearish'] = float(rsi < 50 and stoch_k < 50)

        return features

    @staticmethod
    def _engineer_volatility_features(indicators: Dict, price: float) -> Dict:
        """Volatility-basierte Features"""
        features = {}

        bb_upper = indicators.get('bbUpper', price * 1.02)
        bb_middle = indicators.get('bbMiddle', price)
        bb_lower = indicators.get('bbLower', price * 0.98)
        atr = indicators.get('atr', 0.01)
        volatility = indicators.get('volatility', 0.01)

        # Bollinger Bands Width
        bb_width = bb_upper - bb_lower
        bb_middle_val = bb_middle if bb_middle > 0 else 1
        features['bb_width_pct'] = bb_width / bb_middle_val

        # Price vs Bollinger Bands
        features['price_at_bb_upper'] = float(price >= bb_upper * 0.99)
        features['price_at_bb_lower'] = float(price <= bb_lower * 1.01)
        features['price_at_bb_middle'] = float(
            (price > bb_lower * 1.01) and (price < bb_upper * 0.99)
        )

        # Normalized price in bands
        if bb_width > 0:
            features['bb_position'] = (price - bb_lower) / bb_width
        else:
            features['bb_position'] = 0.5

        # Volatility
        features['atr_pct'] = atr / price if price > 0 else 0
        features['volatility_high'] = float(volatility > 0.02)
        features['volatility_low'] = float(volatility < 0.01)

        return features

    @staticmethod
    def _engineer_volume_features(indicators: Dict, price: float) -> Dict:
        """Volume-basierte Features"""
        features = {}

        vwap = indicators.get('vwap', price)

        # Price vs VWAP
        features['price_vs_vwap_pct'] = (price - vwap) / vwap if vwap > 0 else 0
        features['price_above_vwap'] = float(price > vwap)
        features['price_below_vwap'] = float(price < vwap)

        return features

    @staticmethod
    def _engineer_structure_features(klines: pd.DataFrame, price: float) -> Dict:
        """Market Structure Features"""
        features = {}

        if klines.empty or len(klines) < 5:
            return {
                'is_higher_high': 0,
                'is_lower_low': 0,
                'higher_lows': 0,
                'lower_highs': 0,
                'uptrend_strength': 0,
                'downtrend_strength': 0,
                'price_momentum_5': 0,
                'price_momentum_20': 0,
            }

        try:
            closes = klines['close'].values
            highs = klines['high'].values
            lows = klines['low'].values

            # Recent highs and lows
            recent_high = highs[-5:].max()
            recent_low = lows[-5:].min()
            prev_high = highs[-10:-5].max() if len(highs) >= 10 else recent_high
            prev_low = lows[-10:-5].min() if len(lows) >= 10 else recent_low

            # Higher highs, lower lows
            features['is_higher_high'] = float(recent_high > prev_high)
            features['is_lower_low'] = float(recent_low < prev_low)

            # Trend structure
            features['higher_lows'] = float(
                len(lows) >= 5 and lows[-1] > lows[-3]
            )
            features['lower_highs'] = float(
                len(highs) >= 5 and highs[-1] < highs[-3]
            )

            # Trend strength (5 and 20 period)
            if len(closes) >= 5:
                momentum_5 = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] > 0 else 0
                features['price_momentum_5'] = momentum_5
                features['uptrend_strength'] = max(0, momentum_5)
                features['downtrend_strength'] = max(0, -momentum_5)
            else:
                features['price_momentum_5'] = 0
                features['uptrend_strength'] = 0
                features['downtrend_strength'] = 0

            if len(closes) >= 20:
                momentum_20 = (closes[-1] - closes[-20]) / closes[-20] if closes[-20] > 0 else 0
                features['price_momentum_20'] = momentum_20
            else:
                features['price_momentum_20'] = 0

        except Exception as e:
            # Fallback bei Fehlern
            features['is_higher_high'] = 0
            features['is_lower_low'] = 0
            features['higher_lows'] = 0
            features['lower_highs'] = 0
            features['uptrend_strength'] = 0
            features['downtrend_strength'] = 0
            features['price_momentum_5'] = 0
            features['price_momentum_20'] = 0

        return features


class MLDataset:
    """Dataset-Vorbereitung für ML Training"""

    @staticmethod
    def prepare_dataset(
        trades_df: pd.DataFrame,
        indicators_df: pd.DataFrame,
        context_df: pd.DataFrame,
        klines_by_trade: Dict
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare full ML dataset

        Args:
            trades_df: Trades mit success labels
            indicators_df: Indikatoren pro Trade
            context_df: Market context
            klines_by_trade: Klines für jeden Trade

        Returns:
            X: Feature Matrix (n_trades, n_features)
            y: Labels (1=success, 0=failure)
            feature_names: Namen aller Features
        """

        features_list = []
        labels = []

        for idx, trade in trades_df.iterrows():
            trade_id = trade['id']

            try:
                # Get indicators
                indicators = indicators_df[indicators_df['trade_id'] == trade_id].iloc[0].to_dict()

                # Get market context
                context = context_df[context_df['trade_id'] == trade_id].iloc[0].to_dict()

                # Get klines (für letzten 50 candles)
                klines = klines_by_trade.get(trade_id, pd.DataFrame())

                # Extract price
                price = indicators.get('current_price', 0)

                # Engineer features
                engineered = FeatureEngineer.engineer_features(indicators, price, klines)

                # Add context features
                engineered['btc_price'] = float(context.get('btc_price', 0))
                engineered['funding_rate'] = float(context.get('funding_rate', 0))
                engineered['volume_24h'] = float(context.get('volume_24h', 0))

                features_list.append(engineered)
                labels.append(1 if trade['success'] else 0)

            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error processing trade {trade_id}: {e}", exc_info=True)
                continue

        # Convert to DataFrame for easier handling
        X_df = pd.DataFrame(features_list)
        feature_names = X_df.columns.tolist()

        # Convert to numpy arrays
        X = X_df.values
        y = np.array(labels)

        return X, y, feature_names

    @staticmethod
    def split_data(
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.15,
        val_size: float = 0.15
    ) -> Tuple[
        Tuple[np.ndarray, np.ndarray],
        Tuple[np.ndarray, np.ndarray],
        Tuple[np.ndarray, np.ndarray]
    ]:
        """
        Split data into train/val/test (TIME-AWARE!)

        Args:
            X: Features
            y: Labels
            test_size: Fraction for test (must be newest data)
            val_size: Fraction for validation

        Returns:
            (X_train, y_train), (X_val, y_val), (X_test, y_test)
        """

        n = len(X)
        test_idx = int(n * (1 - test_size))
        val_idx = int(test_idx * (1 - val_size))

        # Train: älteste Daten
        X_train = X[:val_idx]
        y_train = y[:val_idx]

        # Val: mittlere Daten
        X_val = X[val_idx:test_idx]
        y_val = y[val_idx:test_idx]

        # Test: neueste Daten
        X_test = X[test_idx:]
        y_test = y[test_idx:]

        return (X_train, y_train), (X_val, y_val), (X_test, y_test)
