"""Statistics Calculator for Dashboard"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class StatsCalculator:
    """Calculate trading statistics from database"""
    
    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize Stats Calculator
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
    
    def _get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_all_trades(self, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all trades, optionally filtered by days
        
        Args:
            days: Optional number of days to filter (None = all trades)
            
        Returns:
            List of trade dictionaries
        """
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                cursor.execute("""
                    SELECT * FROM trades
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff_date,))
            else:
                cursor.execute("""
                    SELECT * FROM trades
                    ORDER BY timestamp DESC
                """)
            
            rows = cursor.fetchall()
            
            trades = []
            for row in rows:
                trade = dict(row)
                # Parse JSON fields
                if 'strategies_used' in trade and trade['strategies_used']:
                    try:
                        import json
                        trade['strategies_used'] = json.loads(trade['strategies_used'])
                    except (json.JSONDecodeError, ValueError, TypeError) as parse_error:
                        logger.warning(f"Failed to parse strategies_used JSON: {parse_error}")
                        trade['strategies_used'] = []
                trades.append(trade)
            
            return trades
        finally:
            if conn:
                conn.close()
    
    def calculate_stats(self, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive trading statistics
        
        Args:
            days: Optional number of days to analyze (None = all time)
            
        Returns:
            Dictionary with statistics
        """
        trades = self.get_all_trades(days)
        
        if not trades:
            return self._empty_stats()
        
        # Filter closed trades for realized PnL
        closed_trades = [t for t in trades if t.get('exit_time') is not None and t.get('realized_pnl') is not None]
        open_trades = [t for t in trades if t.get('exit_time') is None]
        
        # Basic counts
        total_trades = len(trades)
        closed_count = len(closed_trades)
        open_count = len(open_trades)
        
        # Win/Loss stats
        winning_trades = [t for t in closed_trades if t.get('success') is True]
        losing_trades = [t for t in closed_trades if t.get('success') is False]
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        win_rate = (win_count / closed_count * 100) if closed_count > 0 else 0.0
        
        # PnL calculations
        total_pnl = sum(t.get('realized_pnl', 0) or 0 for t in closed_trades)
        avg_win = sum(t.get('realized_pnl', 0) or 0 for t in winning_trades) / win_count if win_count > 0 else 0.0
        avg_loss = sum(t.get('realized_pnl', 0) or 0 for t in losing_trades) / loss_count if loss_count > 0 else 0.0
        largest_win = max((t.get('realized_pnl', 0) or 0 for t in winning_trades), default=0.0)
        largest_loss = min((t.get('realized_pnl', 0) or 0 for t in losing_trades), default=0.0)
        
        # Profit factor
        gross_profit = sum(t.get('realized_pnl', 0) or 0 for t in winning_trades)
        gross_loss = abs(sum(t.get('realized_pnl', 0) or 0 for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        
        # Sharpe Ratio (simplified - using daily returns)
        daily_returns = self._calculate_daily_returns(closed_trades, days)
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        
        # Max Drawdown
        cumulative_pnl = self._calculate_cumulative_pnl(closed_trades)
        max_drawdown = self._calculate_max_drawdown(cumulative_pnl)
        
        return {
            "totalTrades": total_trades,
            "closedTrades": closed_count,
            "openTrades": open_count,
            "winningTrades": win_count,
            "losingTrades": loss_count,
            "winRate": round(win_rate, 2),
            "totalPnL": round(total_pnl, 2),
            "averageWin": round(avg_win, 2),
            "averageLoss": round(avg_loss, 2),
            "largestWin": round(largest_win, 2),
            "largestLoss": round(largest_loss, 2),
            "profitFactor": round(profit_factor, 2),
            "sharpeRatio": round(sharpe_ratio, 2),
            "maxDrawdown": round(max_drawdown, 2),
            "maxDrawdownPercent": round(max_drawdown * 100, 2) if cumulative_pnl else 0.0
        }
    
    def get_daily_performance(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get daily performance data
        
        Args:
            days: Number of days to retrieve
            
        Returns:
            List of daily performance dictionaries
        """
        trades = self.get_all_trades(days)
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        
        # Group by date
        daily_pnl = {}
        for trade in closed_trades:
            exit_time = trade.get('exit_time')
            if exit_time:
                if isinstance(exit_time, str):
                    exit_date = datetime.fromisoformat(exit_time.replace('Z', '+00:00')).date()
                else:
                    exit_date = exit_time.date() if hasattr(exit_time, 'date') else exit_time
                
                date_str = exit_date.isoformat()
                if date_str not in daily_pnl:
                    daily_pnl[date_str] = 0.0
                daily_pnl[date_str] += trade.get('realized_pnl', 0) or 0
        
        # Convert to list and sort
        daily_performance = [
            {"date": date, "pnl": round(pnl, 2)}
            for date, pnl in sorted(daily_pnl.items())
        ]
        
        return daily_performance
    
    def get_weekly_performance(self, weeks: int = 12) -> List[Dict[str, Any]]:
        """Get weekly performance data"""
        days = weeks * 7
        trades = self.get_all_trades(days)
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        
        # Group by week
        weekly_pnl = {}
        for trade in closed_trades:
            exit_time = trade.get('exit_time')
            if exit_time:
                if isinstance(exit_time, str):
                    dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                else:
                    dt = exit_time
                
                # Get week start (Monday)
                days_since_monday = dt.weekday()
                week_start = dt - timedelta(days=days_since_monday)
                week_key = week_start.strftime("%Y-W%W")
                
                if week_key not in weekly_pnl:
                    weekly_pnl[week_key] = 0.0
                weekly_pnl[week_key] += trade.get('realized_pnl', 0) or 0
        
        weekly_performance = [
            {"week": week, "pnl": round(pnl, 2)}
            for week, pnl in sorted(weekly_pnl.items())
        ]
        
        return weekly_performance
    
    def get_monthly_performance(self, months: int = 12) -> List[Dict[str, Any]]:
        """Get monthly performance data"""
        days = months * 30
        trades = self.get_all_trades(days)
        closed_trades = [t for t in trades if t.get('exit_time') is not None]
        
        # Group by month
        monthly_pnl = {}
        for trade in closed_trades:
            exit_time = trade.get('exit_time')
            if exit_time:
                if isinstance(exit_time, str):
                    dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                else:
                    dt = exit_time
                
                month_key = dt.strftime("%Y-%m")
                
                if month_key not in monthly_pnl:
                    monthly_pnl[month_key] = 0.0
                monthly_pnl[month_key] += trade.get('realized_pnl', 0) or 0
        
        monthly_performance = [
            {"month": month, "pnl": round(pnl, 2)}
            for month, pnl in sorted(monthly_pnl.items())
        ]
        
        return monthly_performance
    
    def _calculate_daily_returns(self, trades: List[Dict], days: Optional[int]) -> List[float]:
        """Calculate daily returns for Sharpe Ratio"""
        daily_pnl = {}
        for trade in trades:
            exit_time = trade.get('exit_time')
            if exit_time:
                if isinstance(exit_time, str):
                    exit_date = datetime.fromisoformat(exit_time.replace('Z', '+00:00')).date()
                else:
                    exit_date = exit_time.date() if hasattr(exit_time, 'date') else exit_time
                
                date_str = exit_date.isoformat()
                if date_str not in daily_pnl:
                    daily_pnl[date_str] = 0.0
                daily_pnl[date_str] += trade.get('realized_pnl', 0) or 0
        
        returns = list(daily_pnl.values())
        return returns if returns else [0.0]
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe Ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        import numpy as np
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe Ratio (assuming 252 trading days)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return float(sharpe)
    
    def _calculate_cumulative_pnl(self, trades: List[Dict]) -> List[float]:
        """Calculate cumulative PnL"""
        sorted_trades = sorted(
            [t for t in trades if t.get('exit_time')],
            key=lambda x: x.get('exit_time', '')
        )
        
        cumulative = []
        running_total = 0.0
        for trade in sorted_trades:
            running_total += trade.get('realized_pnl', 0) or 0
            cumulative.append(running_total)
        
        return cumulative
    
    def _calculate_max_drawdown(self, cumulative_pnl: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not cumulative_pnl:
            return 0.0
        
        max_dd = 0.0
        peak = cumulative_pnl[0]
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _empty_stats(self) -> Dict[str, Any]:
        """Return empty stats structure"""
        return {
            "totalTrades": 0,
            "closedTrades": 0,
            "openTrades": 0,
            "winningTrades": 0,
            "losingTrades": 0,
            "winRate": 0.0,
            "totalPnL": 0.0,
            "averageWin": 0.0,
            "averageLoss": 0.0,
            "largestWin": 0.0,
            "largestLoss": 0.0,
            "profitFactor": 0.0,
            "sharpeRatio": 0.0,
            "maxDrawdown": 0.0,
            "maxDrawdownPercent": 0.0
        }

