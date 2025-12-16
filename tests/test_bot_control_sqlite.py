"""Integration Tests for SQLite-based Bot Control"""

import pytest
import os
import tempfile
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import Database
from dashboard.bot_control_db import BotControlDB


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


class TestBotControlSQLite:
    """Test SQLite-based bot control"""
    
    def test_bot_control_table_created(self, temp_db):
        """Test that bot_control table is created"""
        db_path, db = temp_db
        
        # Check table exists
        control = db.get_bot_control()
        assert control is not None
        assert control["id"] == 1
        assert control["desired_state"] == "stopped"
        assert control["actual_state"] == "stopped"
    
    def test_set_desired_state(self, temp_db):
        """Test setting desired_state"""
        db_path, db = temp_db
        
        # Set desired_state to running
        db.set_bot_desired_state("running")
        db.flush_writes(timeout=2.0)
        
        # Verify
        control = db.get_bot_control()
        assert control["desired_state"] == "running"
        assert control["actual_state"] == "stopped"  # Should not change
    
    def test_update_actual_state(self, temp_db):
        """Test updating actual_state and heartbeat"""
        db_path, db = temp_db
        
        # Update actual_state
        db.update_bot_actual_state("running")
        db.flush_writes(timeout=2.0)
        
        # Verify
        control = db.get_bot_control()
        assert control["actual_state"] == "running"
        assert control["last_heartbeat"] is not None
    
    def test_update_heartbeat(self, temp_db):
        """Test heartbeat update"""
        db_path, db = temp_db
        
        # Get initial heartbeat
        control1 = db.get_bot_control()
        initial_heartbeat = control1["last_heartbeat"]
        
        # Wait a bit
        time.sleep(0.1)
        
        # Update heartbeat
        db.update_bot_heartbeat()
        db.flush_writes(timeout=2.0)
        
        # Verify heartbeat updated
        control2 = db.get_bot_control()
        assert control2["last_heartbeat"] != initial_heartbeat
    
    def test_bot_control_db_wrapper(self, temp_db):
        """Test BotControlDB wrapper class"""
        db_path, db = temp_db
        bot_control = BotControlDB(db_path)
        
        # Test get_desired_state
        desired = bot_control.get_desired_state()
        assert desired == "stopped"
        
        # Test set_desired_state
        bot_control.set_desired_state("running")
        db.flush_writes(timeout=2.0)
        assert bot_control.get_desired_state() == "running"
        
        # Test update_actual_state
        bot_control.update_actual_state("running")
        db.flush_writes(timeout=2.0)
        assert bot_control.get_actual_state() == "running"
        
        # Test update_heartbeat
        bot_control.update_heartbeat()
        db.flush_writes(timeout=2.0)
        control = bot_control.get_control_state()
        assert control["last_heartbeat"] is not None
    
    def test_state_transitions(self, temp_db):
        """Test state transitions"""
        db_path, db = temp_db
        bot_control = BotControlDB(db_path)
        
        # stopped -> running
        bot_control.set_desired_state("running")
        db.flush_writes(timeout=2.0)
        bot_control.update_actual_state("running")
        db.flush_writes(timeout=2.0)
        assert bot_control.get_actual_state() == "running"
        
        # running -> paused
        bot_control.set_desired_state("paused")
        db.flush_writes(timeout=2.0)
        bot_control.update_actual_state("paused")
        db.flush_writes(timeout=2.0)
        assert bot_control.get_actual_state() == "paused"
        
        # paused -> stopped
        bot_control.set_desired_state("stopped")
        db.flush_writes(timeout=2.0)
        bot_control.update_actual_state("stopped")
        db.flush_writes(timeout=2.0)
        assert bot_control.get_actual_state() == "stopped"
    
    def test_error_state(self, temp_db):
        """Test error state handling"""
        db_path, db = temp_db
        bot_control = BotControlDB(db_path)
        
        # Set error state
        bot_control.update_actual_state("error", "Test error message")
        db.flush_writes(timeout=2.0)
        
        control = bot_control.get_control_state()
        assert control["actual_state"] == "error"
        assert control["last_error"] == "Test error message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

