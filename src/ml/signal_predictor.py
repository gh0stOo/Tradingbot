"""
Signal Quality Predictor - Inference Module

Lädt trainiertes XGBoost Model und macht Vorhersagen über
Trade Success Wahrscheinlichkeit
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import joblib

from ml.features import FeatureEngineer


class SignalPredictor:
    """XGBoost Model für Signal Quality Prediction"""

    def __init__(self, model_path: str = "models/signal_predictor.pkl"):
        """
        Initialize Signal Predictor

        Args:
            model_path: Path to saved XGBoost model
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = Path(model_path)
        self.scaler_path = self.model_path.parent / "scaler.pkl"
        self.feature_names_path = self.model_path.parent / "feature_names.json"

        self.model = None
        self.scaler = None
        self.feature_names = None

        self.logger.info(f"SignalPredictor initialized (model_path: {model_path})")

    def load(self) -> bool:
        """
        Load model, scaler and feature names

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.model_path.exists():
                self.logger.warning(f"Model not found: {self.model_path}")
                return False

            self.model = joblib.load(self.model_path)
            self.logger.info(f"✅ Loaded model: {self.model_path}")

            if self.scaler_path.exists():
                self.scaler = joblib.load(self.scaler_path)
                self.logger.info(f"✅ Loaded scaler: {self.scaler_path}")

            if self.feature_names_path.exists():
                with open(self.feature_names_path, 'r') as f:
                    self.feature_names = json.load(f)
                self.logger.info(f"✅ Loaded feature names: {len(self.feature_names)} features")

            return True

        except Exception as e:
            self.logger.error(f"Error loading model: {e}")
            return False

    def predict(
        self,
        indicators: Dict,
        price: float,
        klines: pd.DataFrame
    ) -> Dict:
        """
        Predict signal quality

        Args:
            indicators: Technical indicators dict
            price: Current price
            klines: Historical klines DataFrame

        Returns:
            {
                'success_probability': float (0-1),
                'confidence': float (0-1),
                'model_enhanced': bool
            }
        """
        try:
            if self.model is None:
                self.logger.warning("Model not loaded. Call load() first.")
                return {
                    'success_probability': 0.5,
                    'confidence': 0,
                    'model_enhanced': False
                }

            # Engineer features
            features_dict = FeatureEngineer.engineer_features(
                indicators, price, klines
            )

            # Convert to array in correct order
            if self.feature_names:
                features = np.array([
                    features_dict.get(name, 0.0)
                    for name in self.feature_names
                ]).reshape(1, -1)
            else:
                # Fallback: convert dict to array
                features = np.array(list(features_dict.values())).reshape(1, -1)

            # Normalize
            if self.scaler is not None:
                features = self.scaler.transform(features)

            # Predict
            success_prob = float(self.model.predict_proba(features)[0, 1])

            return {
                'success_probability': success_prob,
                'confidence': min(success_prob, 1.0 - success_prob) * 2,  # Confidence 0-1
                'model_enhanced': True
            }

        except Exception as e:
            self.logger.error(f"Error in predict: {e}")
            return {
                'success_probability': 0.5,
                'confidence': 0,
                'model_enhanced': False
            }

    def predict_batch(
        self,
        indicators_list: list,
        prices: list,
        klines_list: list
    ) -> list:
        """
        Batch prediction for multiple signals

        Args:
            indicators_list: List of indicator dicts
            prices: List of prices
            klines_list: List of klines DataFrames

        Returns:
            List of predictions
        """
        results = []
        for indicators, price, klines in zip(indicators_list, prices, klines_list):
            result = self.predict(indicators, price, klines)
            results.append(result)
        return results

    @staticmethod
    def load_model(model_path: str = "models/signal_predictor.pkl") -> 'SignalPredictor':
        """
        Static method to load and initialize predictor

        Args:
            model_path: Path to model file

        Returns:
            Initialized and loaded SignalPredictor
        """
        predictor = SignalPredictor(model_path)
        if predictor.load():
            return predictor
        return None
