"""Script to run Genetic Algorithm parameter optimization"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml
import logging
from src.ml.genetic_optimizer import GeneticAlgorithmOptimizer
from src.ml.backtest_runner import BacktestRunner
from src.utils.logger import setup_logger

# Setup logging
setup_logger()
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def define_parameter_bounds(config: dict) -> dict:
    """
    Define parameter bounds for genetic algorithm optimization
    
    Args:
        config: Base configuration
        
    Returns:
        Dictionary mapping parameter names to (min, max) bounds
    """
    bounds = {}
    
    # Strategy weights (0.0 to 2.0)
    if "strategies" in config:
        for strategy_name in config["strategies"].keys():
            bounds[f"strategy_weight_{strategy_name}"] = (0.0, 2.0)
    
    # Risk parameters
    if "risk" in config:
        bounds["risk_riskPct"] = (0.01, 0.05)  # 1% to 5%
        bounds["risk_minRR"] = (1.0, 3.0)  # Risk:Reward 1:1 to 1:3
        if "kelly" in config["risk"]:
            bounds["risk_kellyFraction"] = (0.1, 0.5)  # Kelly fraction 10% to 50%
    
    # Ensemble thresholds
    if "ensemble" in config:
        bounds["minConfidence"] = (0.4, 0.8)  # 40% to 80%
        bounds["minQualityScore"] = (0.3, 0.7)  # 30% to 70%
    
    # Strategy parameters (example - adjust based on actual strategies)
    bounds["ema_fast_period"] = (5, 15)  # Fast EMA period
    bounds["ema_slow_period"] = (20, 50)  # Slow EMA period
    bounds["rsi_oversold"] = (20, 35)  # RSI oversold level
    bounds["rsi_overbought"] = (65, 80)  # RSI overbought level
    
    logger.info(f"Defined {len(bounds)} parameters for optimization")
    return bounds


def main():
    """Main optimization script"""
    logger.info("=" * 60)
    logger.info("Genetic Algorithm Parameter Optimization")
    logger.info("=" * 60)
    
    # Load configuration
    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return
    
    config = load_config(config_path)
    if not config:
        logger.error("Failed to load configuration")
        return
    
    # Database path
    database_path = config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
    if not os.path.exists(database_path):
        logger.error(f"Database not found: {database_path}")
        logger.info("Please run collect_historical_data.py first to generate trades")
        return
    
    # Define parameter bounds
    parameter_bounds = define_parameter_bounds(config)
    if not parameter_bounds:
        logger.error("No parameter bounds defined")
        return
    
    # Initialize components
    logger.info("Initializing components...")
    optimizer = GeneticAlgorithmOptimizer(
        parameter_bounds=parameter_bounds,
        population_size=config.get("ml", {}).get("geneticAlgorithm", {}).get("populationSize", 50),
        mutation_rate=config.get("ml", {}).get("geneticAlgorithm", {}).get("mutationRate", 0.1),
        crossover_rate=config.get("ml", {}).get("geneticAlgorithm", {}).get("crossoverRate", 0.7),
        elite_size=config.get("ml", {}).get("geneticAlgorithm", {}).get("eliteSize", 5)
    )
    
    backtest_runner = BacktestRunner(
        database_path=database_path,
        rolling_window_trades=config.get("ml", {}).get("geneticAlgorithm", {}).get("rollingWindowTrades", 500),
        initial_equity=config.get("risk", {}).get("paperEquity", 10000.0)
    )
    
    # Create fitness function
    logger.info("Creating fitness function...")
    fitness_function = backtest_runner.create_fitness_function(config)
    
    # Run optimization
    logger.info("Starting genetic algorithm evolution...")
    logger.info(f"Population size: {optimizer.population_size}")
    logger.info(f"Parameters to optimize: {list(parameter_bounds.keys())}")
    
    max_generations = config.get("ml", {}).get("geneticAlgorithm", {}).get("maxGenerations", 50)
    
    best_individual = optimizer.evolve(
        fitness_function=fitness_function,
        max_generations=max_generations,
        min_fitness_improvement=0.001,
        stagnation_generations=10
    )
    
    # Save results
    output_dir = Path("models")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "optimized_params.json"
    optimizer.save_parameters(str(output_file))
    
    logger.info("=" * 60)
    logger.info("Optimization Complete!")
    logger.info("=" * 60)
    logger.info(f"Best Fitness: {best_individual.fitness:.4f}")
    logger.info(f"Best Parameters:")
    for key, value in best_individual.genes.items():
        logger.info(f"  {key}: {value}")
    logger.info(f"Results saved to: {output_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

