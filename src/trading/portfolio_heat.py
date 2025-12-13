"""Portfolio Heat - Correlation Risk Management"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PortfolioHeat:
    """Manage portfolio correlation and diversification"""
    
    def __init__(
        self,
        max_correlation: float = 0.70,
        max_positions_per_sector: int = 2,
        min_diversification_score: float = 0.50
    ):
        """
        Initialize Portfolio Heat Manager
        
        Args:
            max_correlation: Maximum allowed correlation between positions (0.0-1.0)
            max_positions_per_sector: Maximum positions per sector/category
            min_diversification_score: Minimum diversification score (0.0-1.0)
        """
        self.max_correlation = max_correlation
        self.max_positions_per_sector = max_positions_per_sector
        self.min_diversification_score = min_diversification_score
        
        # Store price history for correlation calculation
        self.price_history: Dict[str, pd.Series] = {}
        
        # Sector/category mapping (simplified - could be enhanced with actual sector data)
        self.sector_map: Dict[str, str] = {}
    
    def update_price_history(self, symbol: str, prices: pd.Series) -> None:
        """
        Update price history for a symbol
        
        Args:
            symbol: Trading symbol
            prices: Price series (pd.Series with close prices)
        """
        self.price_history[symbol] = prices
        logger.debug(f"Updated price history for {symbol}: {len(prices)} data points")
    
    def classify_sector(self, symbol: str) -> str:
        """
        Classify symbol into a sector/category
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT")
            
        Returns:
            Sector name
        """
        # Simplified classification - can be enhanced with actual data
        symbol_upper = symbol.upper()
        
        if "BTC" in symbol_upper:
            return "Bitcoin"
        elif "ETH" in symbol_upper:
            return "Ethereum"
        elif any(x in symbol_upper for x in ["DEFI", "UNI", "AAVE", "SUSHI", "COMP", "MKR"]):
            return "DeFi"
        elif any(x in symbol_upper for x in ["LINK", "BAND", "DIA", "TRB"]):
            return "Oracle"
        elif any(x in symbol_upper for x in ["SOL", "AVAX", "ATOM", "DOT", "MATIC"]):
            return "Layer1"
        elif any(x in symbol_upper for x in ["LINK", "ADA", "ALGO"]):
            return "Altcoin"
        else:
            return "Other"
    
    def calculate_correlation(self, symbol1: str, symbol2: str, min_periods: int = 20) -> float:
        """
        Calculate correlation between two symbols
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            min_periods: Minimum periods for correlation
            
        Returns:
            Correlation coefficient (-1.0 to 1.0)
        """
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return 0.0
        
        prices1 = self.price_history[symbol1]
        prices2 = self.price_history[symbol2]
        
        # Align by index (timestamp)
        common_index = prices1.index.intersection(prices2.index)
        if len(common_index) < min_periods:
            return 0.0
        
        aligned_prices1 = prices1.loc[common_index]
        aligned_prices2 = prices2.loc[common_index]
        
        # Calculate percentage returns
        returns1 = aligned_prices1.pct_change().dropna()
        returns2 = aligned_prices2.pct_change().dropna()
        
        # Calculate correlation
        correlation = returns1.corr(returns2)
        
        if pd.isna(correlation):
            return 0.0
        
        return float(correlation)
    
    def build_correlation_matrix(self, symbols: List[str]) -> pd.DataFrame:
        """
        Build correlation matrix for given symbols
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Correlation matrix DataFrame
        """
        n = len(symbols)
        correlation_matrix = np.eye(n)  # Start with identity matrix
        
        for i in range(n):
            for j in range(i + 1, n):
                corr = self.calculate_correlation(symbols[i], symbols[j])
                correlation_matrix[i, j] = corr
                correlation_matrix[j, i] = corr  # Symmetric
        
        return pd.DataFrame(correlation_matrix, index=symbols, columns=symbols)
    
    def check_sector_limit(self, symbol: str, current_positions: List[str]) -> bool:
        """
        Check if adding symbol would exceed sector limit
        
        Args:
            symbol: Symbol to check
            current_positions: List of symbols in current positions
            
        Returns:
            True if allowed, False if would exceed limit
        """
        new_symbol_sector = self.classify_sector(symbol)
        
        # Count positions in same sector
        sector_count = sum(
            1 for pos_symbol in current_positions
            if self.classify_sector(pos_symbol) == new_symbol_sector
        )
        
        if sector_count >= self.max_positions_per_sector:
            logger.warning(
                f"Symbol {symbol} would exceed sector limit for {new_symbol_sector} "
                f"({sector_count}/{self.max_positions_per_sector})"
            )
            return False
        
        return True
    
    def check_correlation(self, new_symbol: str, current_positions: List[str]) -> bool:
        """
        Check if new symbol is too correlated with existing positions
        
        Args:
            new_symbol: Symbol to check
            current_positions: List of symbols in current positions
            
        Returns:
            True if correlation is acceptable, False if too high
        """
        for position_symbol in current_positions:
            correlation = abs(self.calculate_correlation(new_symbol, position_symbol))
            
            if correlation > self.max_correlation:
                logger.warning(
                    f"Symbol {new_symbol} has high correlation ({correlation:.2f}) "
                    f"with existing position {position_symbol}"
                )
                return False
        
        return True
    
    def calculate_diversification_score(self, positions: List[str]) -> float:
        """
        Calculate diversification score for portfolio
        
        Args:
            positions: List of position symbols
            
        Returns:
            Diversification score (0.0-1.0, higher = more diversified)
        """
        if not positions:
            return 1.0  # Empty portfolio is perfectly diversified
        
        if len(positions) == 1:
            return 0.5  # Single position has medium diversification
        
        # Count unique sectors
        sectors = [self.classify_sector(symbol) for symbol in positions]
        unique_sectors = len(set(sectors))
        total_positions = len(positions)
        
        # Sector diversity component (0.0-0.5)
        sector_diversity = min(unique_sectors / total_positions, 1.0) * 0.5
        
        # Correlation diversity component (0.0-0.5)
        if len(positions) > 1:
            correlations = []
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    corr = abs(self.calculate_correlation(positions[i], positions[j]))
                    correlations.append(corr)
            
            if correlations:
                avg_correlation = np.mean(correlations)
                # Lower average correlation = higher diversity
                correlation_diversity = (1.0 - avg_correlation) * 0.5
            else:
                correlation_diversity = 0.25
        else:
            correlation_diversity = 0.25
        
        total_score = sector_diversity + correlation_diversity
        return min(total_score, 1.0)
    
    def can_add_position(self, symbol: str, current_positions: List[str]) -> Tuple[bool, str]:
        """
        Check if new position can be added based on portfolio heat rules
        
        Args:
            symbol: Symbol to add
            current_positions: List of current position symbols
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Check sector limit
        if not self.check_sector_limit(symbol, current_positions):
            sector = self.classify_sector(symbol)
            return False, f"Sector limit exceeded for {sector}"
        
        # Check correlation
        if not self.check_correlation(symbol, current_positions):
            return False, f"Too high correlation with existing positions"
        
        # Check diversification score
        test_positions = current_positions + [symbol]
        diversification_score = self.calculate_diversification_score(test_positions)
        
        if diversification_score < self.min_diversification_score:
            return False, f"Diversification score too low: {diversification_score:.2f}"
        
        return True, "OK"
    
    def get_portfolio_heat_map(self, positions: List[str]) -> Dict[str, Any]:
        """
        Get portfolio heat map with correlation matrix and statistics
        
        Args:
            positions: List of position symbols
            
        Returns:
            Dictionary with heat map data
        """
        if not positions:
            return {
                "correlation_matrix": {},
                "sectors": {},
                "diversification_score": 1.0,
                "average_correlation": 0.0,
                "max_correlation": 0.0
            }
        
        # Build correlation matrix
        correlation_matrix = self.build_correlation_matrix(positions)
        
        # Calculate statistics
        correlations = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                corr = abs(correlation_matrix.loc[positions[i], positions[j]])
                correlations.append(corr)
        
        avg_correlation = np.mean(correlations) if correlations else 0.0
        max_correlation = np.max(correlations) if correlations else 0.0
        
        # Sector distribution
        sector_dist = defaultdict(int)
        for symbol in positions:
            sector = self.classify_sector(symbol)
            sector_dist[sector] += 1
        
        diversification_score = self.calculate_diversification_score(positions)
        
        return {
            "correlation_matrix": correlation_matrix.to_dict(),
            "sectors": dict(sector_dist),
            "diversification_score": round(diversification_score, 3),
            "average_correlation": round(avg_correlation, 3),
            "max_correlation": round(max_correlation, 3),
            "total_positions": len(positions)
        }

