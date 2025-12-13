"""Slippage Modeling - Market Impact and Liquidity-Based Slippage"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SlippageModel:
    """Calculate slippage based on order size, liquidity, and market conditions"""
    
    # Base slippage rates (percentage as decimal)
    BASE_SLIPPAGE_BUY = 0.0001  # 0.01% base for buy orders
    BASE_SLIPPAGE_SELL = 0.0001  # 0.01% base for sell orders
    
    def __init__(
        self,
        base_slippage_buy: float = 0.0001,
        base_slippage_sell: float = 0.0001
    ):
        """
        Initialize Slippage Model
        
        Args:
            base_slippage_buy: Base slippage for buy orders (default: 0.01%)
            base_slippage_sell: Base slippage for sell orders (default: 0.01%)
        """
        self.base_slippage_buy = base_slippage_buy
        self.base_slippage_sell = base_slippage_sell
    
    def calculate_market_impact(
        self,
        order_size_usd: float,
        volume_24h_usd: float,
        side: str = "Buy"
    ) -> float:
        """
        Calculate market impact based on order size relative to 24h volume
        
        Args:
            order_size_usd: Order size in USD
            volume_24h_usd: 24-hour trading volume in USD
            side: Order side ("Buy" or "Sell")
            
        Returns:
            Market impact as decimal (e.g., 0.001 = 0.1%)
        """
        if volume_24h_usd <= 0:
            # No volume data, use conservative estimate
            return 0.002 if side == "Buy" else 0.002  # 0.2% default
        
        # Calculate order size as percentage of daily volume
        volume_pct = (order_size_usd / volume_24h_usd) * 100
        
        # Market impact model:
        # - <0.1% of volume: 0.01% slippage
        # - 0.1-1% of volume: 0.05% slippage
        # - 1-5% of volume: 0.1% slippage
        # - 5-10% of volume: 0.2% slippage
        # - >10% of volume: 0.5%+ slippage (exponential)
        
        if volume_pct < 0.1:
            impact = 0.0001  # 0.01%
        elif volume_pct < 1.0:
            impact = 0.0005  # 0.05%
        elif volume_pct < 5.0:
            impact = 0.001  # 0.1%
        elif volume_pct < 10.0:
            impact = 0.002  # 0.2%
        else:
            # Exponential increase for large orders
            impact = 0.002 + (volume_pct - 10.0) * 0.00005  # 0.2% + 0.005% per % over 10%
            impact = min(impact, 0.01)  # Cap at 1%
        
        # Sell orders typically have slightly higher impact (liquidity asymmetry)
        if side == "Sell":
            impact *= 1.1
        
        return impact
    
    def calculate_slippage(
        self,
        price: float,
        order_size_usd: float,
        volume_24h_usd: Optional[float] = None,
        side: str = "Buy",
        volatility: Optional[float] = None,
        asset_type: str = "linear"  # linear, inverse, spot
    ) -> float:
        """
        Calculate expected slippage for an order
        
        Args:
            price: Current market price
            order_size_usd: Order size in USD
            volume_24h_usd: 24-hour trading volume in USD (optional)
            side: Order side ("Buy" or "Sell")
            volatility: Asset volatility (optional, for volatility adjustment)
            asset_type: Asset type ("linear", "inverse", "spot")
            
        Returns:
            Slippage amount in price units (not percentage)
        """
        # Base slippage
        base_slippage_pct = self.base_slippage_buy if side == "Buy" else self.base_slippage_sell
        
        # Market impact
        if volume_24h_usd:
            market_impact_pct = self.calculate_market_impact(order_size_usd, volume_24h_usd, side)
        else:
            # No volume data, use conservative estimate
            market_impact_pct = 0.0005  # 0.05% default
        
        # Volatility adjustment
        volatility_adjustment = 1.0
        if volatility:
            # Higher volatility = higher slippage
            # Normalize volatility (assuming typical crypto volatility ~2-5%)
            if volatility > 0.05:  # Very high volatility (>5%)
                volatility_adjustment = 1.5
            elif volatility > 0.03:  # High volatility (>3%)
                volatility_adjustment = 1.3
            elif volatility > 0.02:  # Medium volatility (>2%)
                volatility_adjustment = 1.1
        
        # Asset type adjustment
        asset_adjustment = 1.0
        if asset_type == "inverse":
            asset_adjustment = 1.2  # Inverse contracts typically less liquid
        elif asset_type == "spot":
            asset_adjustment = 0.9  # Spot markets often more liquid
        
        # Total slippage percentage
        total_slippage_pct = (base_slippage_pct + market_impact_pct) * volatility_adjustment * asset_adjustment
        
        # Convert to price units
        slippage_amount = price * total_slippage_pct
        
        logger.debug(
            f"Slippage calculation: price={price}, size={order_size_usd}, "
            f"volume_24h={volume_24h_usd}, side={side}, "
            f"slippage={slippage_amount:.4f} ({total_slippage_pct*100:.3f}%)"
        )
        
        return slippage_amount
    
    def estimate_fill_price(
        self,
        target_price: float,
        order_size_usd: float,
        volume_24h_usd: Optional[float] = None,
        side: str = "Buy",
        volatility: Optional[float] = None,
        asset_type: str = "linear"
    ) -> float:
        """
        Estimate fill price after slippage
        
        Args:
            target_price: Target/limit price
            order_size_usd: Order size in USD
            volume_24h_usd: 24-hour trading volume in USD (optional)
            side: Order side ("Buy" or "Sell")
            volatility: Asset volatility (optional)
            asset_type: Asset type
            
        Returns:
            Estimated fill price
        """
        slippage = self.calculate_slippage(
            price=target_price,
            order_size_usd=order_size_usd,
            volume_24h_usd=volume_24h_usd,
            side=side,
            volatility=volatility,
            asset_type=asset_type
        )
        
        if side == "Buy":
            # Buy orders execute at higher price (slippage increases cost)
            fill_price = target_price + slippage
        else:
            # Sell orders execute at lower price (slippage reduces proceeds)
            fill_price = target_price - slippage
        
        return fill_price
    
    def get_slippage_stats(
        self,
        order_size_usd: float,
        volume_24h_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get slippage statistics for given order size
        
        Args:
            order_size_usd: Order size in USD
            volume_24h_usd: 24-hour trading volume in USD (optional)
            
        Returns:
            Dictionary with slippage statistics
        """
        stats = {
            "order_size_usd": order_size_usd,
            "volume_24h_usd": volume_24h_usd,
            "volume_pct": (order_size_usd / volume_24h_usd * 100) if volume_24h_usd else None
        }
        
        if volume_24h_usd:
            stats["market_impact_buy"] = self.calculate_market_impact(order_size_usd, volume_24h_usd, "Buy")
            stats["market_impact_sell"] = self.calculate_market_impact(order_size_usd, volume_24h_usd, "Sell")
        else:
            stats["market_impact_buy"] = 0.0005
            stats["market_impact_sell"] = 0.0005
        
        return stats

