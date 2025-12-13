"""Pytest configuration and fixtures"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict, Any


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing"""
    return {
        "trading": {
            "mode": "PAPER"
        },
        "risk": {
            "riskPct": 0.02,
            "atrMultiplierSL": 2.0,
            "atrMultiplierTP": 4.0,
            "minRR": 2.0,
            "paperEquity": 10000.0,
            "kelly": {
                "enabled": True,
                "fraction": 0.25,
                "minWinRate": 0.40
            }
        },
        "strategies": {
            "emaTrend": {"weight": 1.0},
            "macdTrend": {"weight": 1.0},
            "rsiMeanReversion": {"weight": 1.0},
            "bollingerMeanReversion": {"weight": 1.0},
            "adxTrend": {"weight": 1.0},
            "volumeProfile": {"weight": 1.0},
            "volatilityBreakout": {"weight": 1.0},
            "multiTimeframe": {"weight": 1.0}
        }
    }


@pytest.fixture
def sample_klines() -> pd.DataFrame:
    """Sample kline data for testing"""
    length = 100
    dates = pd.date_range(start='2024-01-01', periods=length, freq='1min')
    base_price = 100.0
    returns = np.random.randn(length) * 0.01
    prices = base_price * (1 + returns).cumprod()
    
    return pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': prices * (1 + np.abs(np.random.randn(length) * 0.01)),
        'low': prices * (1 - np.abs(np.random.randn(length) * 0.01)),
        'close': prices,
        'volume': np.random.rand(length) * 1000
    })


@pytest.fixture
def sample_indicators() -> Dict[str, float]:
    """Sample indicators for testing"""
    return {
        "ema8": 100.0,
        "ema21": 99.0,
        "ema50": 98.0,
        "ema200": 97.0,
        "rsi": 50.0,
        "atr": 2.0,
        "macd": 0.5,
        "macdSignal": 0.3,
        "macdHist": 0.2,
        "bbUpper": 105.0,
        "bbLower": 95.0,
        "bbMiddle": 100.0,
        "vwap": 100.0,
        "stochastic": 50.0,
        "adx": 25.0,
        "volatility": 0.02,
        "currentPrice": 101.0
    }

