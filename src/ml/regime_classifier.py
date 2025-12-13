"""
Regime Classifier - Inference Module

Lädt trainiertes Random Forest Model und macht Vorhersagen über
Market Regime (trending/ranging/volatile)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import joblib

from ml.features import FeatureEngineer


class RegimeClassifier:
    """Random Forest Model für Market Regime Classification"""

    REGIME_NAMES = {
        0: 'trending',
        1: 'ranging',
        2: 'volatile'
    }

    def __init__(self, model_path: str = "models/regime_classifier.pkl"):
        """
        Initialize Regime Classifier

        Args:
            model_path: Path to saved Random Forest model
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = Path(model_path)
        self.scaler_path = self.model_path.parent / "scaler_regime.pkl"
        self.feature_names_path = self.model_path.parent / "feature_names.json"

        self.model = None
        self.scaler = None
        self.feature_names = None

        self.logger.info(f"RegimeClassifier initialized (model_path: {model_path})")

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
        Predict market regime

        Args:
            indicators: Technical indicators dict
            price: Current price
            klines: Historical klines DataFrame

        Returns:
            {
                'type': str ('trending', 'ranging', 'volatile'),
                'confidence': float (0-1),
                'probabilities': {
                    'trending': float,
                    'ranging': float,
                    'volatile': float
                },
                'model_enhanced': bool
            }
        """
        try:
            if self.model is None:
                self.logger.warning("Model not loaded. Call load() first.")
                return {
                    'type': 'ranging',
                    'confidence': 0,
                    'probabilities': {
                        'trending': 0.33,
                        'ranging': 0.33,
                        'volatile': 0.33
                    },
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
                features = np.array(list(features_dict.values())).reshape(1, -1)

            # Normalize
            if self.scaler is not None:
                features = self.scaler.transform(features)

            # Predict
            regime_idx = int(self.model.predict(features)[0])
            regime_probs = self.model.predict_proba(features)[0]

            regime_type = self.REGIME_NAMES.get(regime_idx, 'ranging')

            return {
                'type': regime_type,
                'confidence': float(regime_probs[regime_idx]),
                'probabilities': {
                    'trending': float(regime_probs[0]),
                    'ranging': float(regime_probs[1]) if len(regime_probs) > 1 else 0.0,
                    'volatile': float(regime_probs[2]) if len(regime_probs) > 2 else 0.0
                },
                'model_enhanced': True
            }

        except Exception as e:
            self.logger.error(f"Error in predict: {e}")
            return {
                'type': 'ranging',
                'confidence': 0,
                'probabilities': {
                    'trending': 0.33,
                    'ranging': 0.33,
                    'volatile': 0.33
                },
                'model_enhanced': False
            }

    @staticmethod
    def load_model(model_path: str = "models/regime_classifier.pkl") -> 'RegimeClassifier':
        """
        Static method to load and initialize classifier

        Args:
            model_path: Path to model file

        Returns:
            Initialized and loaded RegimeClassifier
        """
        classifier = RegimeClassifier(model_path)
        if classifier.load():
            return classifier
        return None
