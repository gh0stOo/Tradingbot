"""Genetic Algorithm for Parameter Optimization"""

import random
import copy
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
import logging
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class Individual:
    """Represents a single individual in the genetic algorithm population"""
    genes: Dict[str, Any]  # Parameter values
    fitness: float = -float('inf')  # Fitness score
    generation: int = 0  # Generation when created
    
    def __repr__(self):
        return f"Individual(fitness={self.fitness:.4f}, gen={self.generation})"


class GeneticAlgorithmOptimizer:
    """
    Genetic Algorithm for optimizing trading strategy parameters.
    
    Optimizes:
    - Strategy weights
    - Strategy parameters (EMA periods, RSI levels, etc.)
    - Filter thresholds (minConfidence, minQualityScore)
    - Risk parameters (Position Size %, Kelly Fraction, Max Exposure)
    """
    
    def __init__(
        self,
        parameter_bounds: Dict[str, Tuple[float, float]],
        population_size: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        elite_size: int = 5,
        tournament_size: int = 3
    ):
        """
        Initialize Genetic Algorithm Optimizer
        
        Args:
            parameter_bounds: Dictionary mapping parameter names to (min, max) bounds
                            Example: {"ema_period": (5, 25), "rsi_level": (20, 80)}
            population_size: Number of individuals in population
            mutation_rate: Probability of mutation (0.0-1.0)
            crossover_rate: Probability of crossover (0.0-1.0)
            elite_size: Number of best individuals to keep unchanged
            tournament_size: Size of tournament for selection
        """
        self.parameter_bounds = parameter_bounds
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_size = elite_size
        self.tournament_size = tournament_size
        
        self.population: List[Individual] = []
        self.generation = 0
        self.best_individual: Optional[Individual] = None
        self.fitness_history: List[float] = []
        
        logger.info(f"GeneticAlgorithmOptimizer initialized: pop_size={population_size}, mutation={mutation_rate}, crossover={crossover_rate}")
    
    def _create_random_individual(self) -> Individual:
        """Create a random individual with genes within bounds"""
        genes = {}
        for param_name, (min_val, max_val) in self.parameter_bounds.items():
            if isinstance(min_val, int) and isinstance(max_val, int):
                genes[param_name] = random.randint(min_val, max_val)
            else:
                genes[param_name] = random.uniform(min_val, max_val)
        
        return Individual(genes=genes, generation=self.generation)
    
    def initialize_population(self) -> None:
        """Initialize random population"""
        self.population = [self._create_random_individual() for _ in range(self.population_size)]
        logger.info(f"Initialized population of {self.population_size} individuals")
    
    def _mutate(self, individual: Individual) -> Individual:
        """Mutate an individual's genes"""
        mutated = copy.deepcopy(individual)
        
        for param_name, (min_val, max_val) in self.parameter_bounds.items():
            if random.random() < self.mutation_rate:
                # Apply mutation
                if isinstance(min_val, int) and isinstance(max_val, int):
                    mutated.genes[param_name] = random.randint(min_val, max_val)
                else:
                    # Gaussian mutation around current value
                    current = mutated.genes[param_name]
                    std = (max_val - min_val) * 0.1  # 10% of range
                    new_val = current + random.gauss(0, std)
                    mutated.genes[param_name] = np.clip(new_val, min_val, max_val)
        
        mutated.generation = self.generation
        return mutated
    
    def _crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """Perform crossover between two parents"""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)
        
        child1 = copy.deepcopy(parent1)
        child2 = copy.deepcopy(parent2)
        
        # Single-point crossover
        params = list(self.parameter_bounds.keys())
        crossover_point = random.randint(1, len(params) - 1)
        
        for i, param_name in enumerate(params):
            if i < crossover_point:
                child1.genes[param_name] = parent2.genes[param_name]
                child2.genes[param_name] = parent1.genes[param_name]
            else:
                child1.genes[param_name] = parent1.genes[param_name]
                child2.genes[param_name] = parent2.genes[param_name]
        
        child1.generation = self.generation
        child2.generation = self.generation
        
        return child1, child2
    
    def _tournament_selection(self) -> Individual:
        """Select an individual using tournament selection"""
        tournament = random.sample(self.population, min(self.tournament_size, len(self.population)))
        return max(tournament, key=lambda ind: ind.fitness)
    
    def _calculate_fitness(self, individual: Individual, fitness_function: callable) -> float:
        """
        Calculate fitness for an individual using the provided fitness function
        
        Args:
            individual: Individual to evaluate
            fitness_function: Function that takes genes dict and returns fitness score
            
        Returns:
            Fitness score (higher is better)
        """
        try:
            fitness = fitness_function(individual.genes)
            if not isinstance(fitness, (int, float)) or np.isnan(fitness) or np.isinf(fitness):
                return -float('inf')
            return float(fitness)
        except Exception as e:
            logger.warning(f"Error calculating fitness: {e}")
            return -float('inf')
    
    def evolve(
        self,
        fitness_function: callable,
        max_generations: int = 50,
        min_fitness_improvement: float = 0.001,
        stagnation_generations: int = 10
    ) -> Individual:
        """
        Evolve the population
        
        Args:
            fitness_function: Function that takes genes dict and returns fitness score
            max_generations: Maximum number of generations
            min_fitness_improvement: Minimum fitness improvement to continue
            stagnation_generations: Stop if no improvement for N generations
            
        Returns:
            Best individual found
        """
        if not self.population:
            self.initialize_population()
        
        # Evaluate initial population
        logger.info("Evaluating initial population...")
        for individual in self.population:
            individual.fitness = self._calculate_fitness(individual, fitness_function)
        
        self.population.sort(key=lambda ind: ind.fitness, reverse=True)
        self.best_individual = copy.deepcopy(self.population[0])
        self.fitness_history = [self.best_individual.fitness]
        
        logger.info(f"Generation 0: Best fitness = {self.best_individual.fitness:.4f}")
        
        last_improvement_generation = 0
        
        for generation in range(1, max_generations + 1):
            self.generation = generation
            
            # Elitism: Keep best individuals
            new_population = self.population[:self.elite_size].copy()
            
            # Generate offspring
            while len(new_population) < self.population_size:
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()
                
                child1, child2 = self._crossover(parent1, parent2)
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)
                
                # Evaluate children
                child1.fitness = self._calculate_fitness(child1, fitness_function)
                child2.fitness = self._calculate_fitness(child2, fitness_function)
                
                new_population.extend([child1, child2])
            
            # Trim to population size
            new_population = new_population[:self.population_size]
            new_population.sort(key=lambda ind: ind.fitness, reverse=True)
            
            self.population = new_population
            
            # Update best
            if self.population[0].fitness > self.best_individual.fitness:
                improvement = self.population[0].fitness - self.best_individual.fitness
                self.best_individual = copy.deepcopy(self.population[0])
                last_improvement_generation = generation
                logger.info(f"Generation {generation}: New best fitness = {self.best_individual.fitness:.4f} (+{improvement:.4f})")
            else:
                logger.debug(f"Generation {generation}: Best fitness = {self.population[0].fitness:.4f} (no improvement)")
            
            self.fitness_history.append(self.best_individual.fitness)
            
            # Check for stagnation
            if generation - last_improvement_generation >= stagnation_generations:
                logger.info(f"Stopped due to stagnation after {generation} generations")
                break
            
            # Check for convergence
            if len(self.fitness_history) > 5:
                recent_improvement = max(self.fitness_history[-5:]) - min(self.fitness_history[-5:])
                if recent_improvement < min_fitness_improvement:
                    logger.info(f"Stopped due to convergence after {generation} generations")
                    break
        
        logger.info(f"Evolution complete. Best fitness: {self.best_individual.fitness:.4f}")
        logger.info(f"Best parameters: {self.best_individual.genes}")
        
        return self.best_individual
    
    def get_best_parameters(self) -> Dict[str, Any]:
        """Get best parameters found"""
        if self.best_individual:
            return self.best_individual.genes
        return {}
    
    def get_fitness_history(self) -> List[float]:
        """Get fitness history across generations"""
        return self.fitness_history
    
    def save_parameters(self, filepath: str) -> None:
        """Save optimized parameters to JSON file"""
        if self.best_individual:
            data = {
                "parameters": self.best_individual.genes,
                "fitness": self.best_individual.fitness,
                "generation": self.best_individual.generation,
                "fitness_history": self.fitness_history
            }
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved optimized parameters to {filepath}")
    
    def load_parameters(self, filepath: str) -> Dict[str, Any]:
        """Load optimized parameters from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded optimized parameters from {filepath}")
            return data.get("parameters", {})
        except Exception as e:
            logger.error(f"Error loading parameters: {e}")
            return {}

