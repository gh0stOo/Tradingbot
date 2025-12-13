"""
ML Module - Machine Learning Models for Trading Bot

Includes:
- Feature Engineering (Phase 2.1)
- Signal Quality Prediction (XGBoost) (Phase 2.2)
- Regime Classification (Random Forest) (Phase 2.3)
- Genetic Algorithm Optimization (Phase 2.5)
- Online Learning (Phase 3)
- Training Scheduler (Phase 3)
"""

try:
    from ml.features import FeatureEngineer, MLDataset
    from ml.signal_predictor import SignalPredictor
    from ml.regime_classifier import RegimeClassifier
    from ml.genetic_optimizer import GeneticAlgorithmOptimizer
    from ml.backtest_runner import BacktestRunner
    from ml.parameter_scheduler import ParameterScheduler
    from ml.weight_optimizer import WeightOptimizer, OnlineLearningManager
    from ml.training_scheduler import TrainingScheduler, create_training_function
except ImportError:
    # Graceful fallback if ML dependencies not available
    FeatureEngineer = None
    MLDataset = None
    SignalPredictor = None
    RegimeClassifier = None
    GeneticAlgorithmOptimizer = None
    BacktestRunner = None
    ParameterScheduler = None
    WeightOptimizer = None
    OnlineLearningManager = None
    TrainingScheduler = None
    create_training_function = None

__all__ = [
    'FeatureEngineer',
    'MLDataset',
    'SignalPredictor',
    'RegimeClassifier',
    'GeneticAlgorithmOptimizer',
    'BacktestRunner',
    'ParameterScheduler',
    'WeightOptimizer',
    'OnlineLearningManager',
    'TrainingScheduler',
    'create_training_function'
]
