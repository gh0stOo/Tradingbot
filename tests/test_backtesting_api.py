"""Integration Tests for Backtesting API"""

import pytest
import os
import tempfile
import time
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import Database


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    db = Database(db_path)
    yield db_path, db
    
    # Cleanup
    db.close()
    os.unlink(db_path)


class TestBacktestingAPI:
    """Test Backtesting API endpoints"""
    
    def test_create_backtest(self, temp_db):
        """Test creating a backtest record"""
        db_path, db = temp_db
        
        backtest_id = "bt_test_123"
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()
        
        db.create_backtest(
            backtest_id=backtest_id,
            start_date=start_date,
            end_date=end_date,
            symbols='["BTCUSDT"]',
            initial_equity=10000.0
        )
        db.flush_writes(timeout=2.0)
        
        # Verify
        backtest = db.get_backtest(backtest_id)
        assert backtest is not None
        assert backtest["id"] == backtest_id
        assert backtest["status"] == "running"
        assert backtest["progress"] == 0
        assert backtest["initial_equity"] == 10000.0
    
    def test_update_backtest_status(self, temp_db):
        """Test updating backtest status"""
        db_path, db = temp_db
        
        backtest_id = "bt_test_456"
        start_date = datetime.utcnow().isoformat()
        end_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        
        # Create backtest
        db.create_backtest(backtest_id, start_date, end_date, None, 10000.0)
        db.flush_writes(timeout=2.0)
        
        # Update progress
        db.update_backtest_status(backtest_id, "running", progress=50)
        db.flush_writes(timeout=2.0)
        
        backtest = db.get_backtest(backtest_id)
        assert backtest["status"] == "running"
        assert backtest["progress"] == 50
        
        # Complete backtest
        results_json = '{"totalReturn": 10.5, "winRate": 0.65}'
        db.update_backtest_status(backtest_id, "completed", progress=100, results=results_json)
        db.flush_writes(timeout=2.0)
        
        backtest = db.get_backtest(backtest_id)
        assert backtest["status"] == "completed"
        assert backtest["progress"] == 100
        assert backtest["results"] == results_json
        assert backtest["completed_at"] is not None
    
    def test_backtest_error_handling(self, temp_db):
        """Test backtest error handling"""
        db_path, db = temp_db
        
        backtest_id = "bt_test_error"
        start_date = datetime.utcnow().isoformat()
        end_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
        
        # Create backtest
        db.create_backtest(backtest_id, start_date, end_date, None, 10000.0)
        db.flush_writes(timeout=2.0)
        
        # Set error
        db.update_backtest_status(
            backtest_id,
            "error",
            error="Test error",
            error_type="ValueError",
            error_details='{"message": "Test error"}'
        )
        db.flush_writes(timeout=2.0)
        
        backtest = db.get_backtest(backtest_id)
        assert backtest["status"] == "error"
        assert backtest["error"] == "Test error"
        assert backtest["error_type"] == "ValueError"
    
    def test_list_backtests(self, temp_db):
        """Test listing backtests"""
        db_path, db = temp_db
        
        # Create multiple backtests
        for i in range(3):
            backtest_id = f"bt_test_{i}"
            start_date = datetime.utcnow().isoformat()
            end_date = (datetime.utcnow() + timedelta(days=1)).isoformat()
            db.create_backtest(backtest_id, start_date, end_date, None, 10000.0)
        
        db.flush_writes(timeout=2.0)
        
        # List backtests
        backtests = db.list_backtests(limit=10)
        assert len(backtests) == 3
        assert all(bt["status"] == "running" for bt in backtests)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

