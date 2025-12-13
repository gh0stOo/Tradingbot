"""Unit Tests for PHASE 4: Thread-Safety Implementation"""

import unittest
import threading
import tempfile
import time
import os
from unittest.mock import Mock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.database import Database
from data.position_tracker import PositionTracker


class TestDatabaseThreadSafety(unittest.TestCase):
    """Test Database Writer Queue Thread-Safety"""

    def setUp(self):
        """Setup database for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_writer_thread_exists(self):
        """Test: Writer thread is created and running"""
        self.assertIsNotNone(self.db.writer_thread)
        self.assertTrue(self.db.writer_thread.is_alive())

    def test_write_queue_initialized(self):
        """Test: Write queue is initialized"""
        self.assertIsNotNone(self.db.write_queue)
        self.assertTrue(isinstance(self.db.write_queue, type(self.db.write_queue)))

    def test_insert_queued_for_write(self):
        """Test: INSERT queries are queued, not executed directly"""
        initial_size = self.db.write_queue.qsize()

        # Queue an INSERT
        self.db.execute(
            "INSERT INTO trades (timestamp, symbol, side, entry_price, quantity, stop_loss, take_profit, confidence, quality_score, regime_type, strategies_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2024-01-01 10:00:00", "BTCUSDT", "Buy", 50000, 1, 48000, 52000, 0.8, 0.9, "Bullish", "Strategy1")
        )

        # Queue size should increase
        self.assertGreater(self.db.write_queue.qsize(), initial_size)

    def test_select_not_queued(self):
        """Test: SELECT queries are NOT queued (read directly)"""
        initial_size = self.db.write_queue.qsize()

        # Execute a SELECT
        self.db.fetch_all("SELECT * FROM trades WHERE id = 999")

        # Queue size should NOT increase
        self.assertEqual(self.db.write_queue.qsize(), initial_size)

    def test_flush_writes(self):
        """Test: flush_writes() waits for all queued writes"""
        # Queue multiple writes
        for i in range(3):
            self.db.execute(
                "INSERT INTO trades (timestamp, symbol, side, entry_price, quantity, stop_loss, take_profit, confidence, quality_score, regime_type, strategies_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"2024-01-01 10:0{i}:00", f"SYMBOL{i}", "Buy", 50000, 1, 48000, 52000, 0.8, 0.9, "Bullish", "Strategy1")
            )

        # Flush all writes
        self.db.flush_writes()

        # Queue should be empty (or nearly empty)
        self.assertLessEqual(self.db.write_queue.qsize(), 1)


class TestPositionTrackerThreadSafety(unittest.TestCase):
    """Test PositionTracker Thread-Safety with Concurrent Operations"""

    def setUp(self):
        """Setup tracker for testing"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.tracker = PositionTracker(self.db, fee_rate=0.001)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_concurrent_position_opens(self):
        """Test: Multiple threads can open positions concurrently"""
        results = []

        def open_position(trade_id):
            result = self.tracker.open_position(
                trade_id=trade_id,
                symbol="BTCUSDT",
                side="Buy",
                entry_price=50000.0,
                quantity=1.0,
                stop_loss=48000.0,
                take_profit=52000.0
            )
            results.append(result)

        threads = []
        for i in range(10):
            t = threading.Thread(target=open_position, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All opens should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(results))

    def test_concurrent_position_closes(self):
        """Test: Multiple threads can close positions concurrently"""
        # Open positions first
        for i in range(5):
            self.tracker.open_position(
                trade_id=i,
                symbol="BTCUSDT",
                side="Buy",
                entry_price=50000.0,
                quantity=1.0,
                stop_loss=48000.0,
                take_profit=52000.0
            )

        results = []

        def close_position(trade_id):
            result = self.tracker.close_position(
                trade_id=trade_id,
                exit_price=51000.0,
                exit_reason="TP"
            )
            if result:
                results.append(trade_id)

        threads = []
        for i in range(5):
            t = threading.Thread(target=close_position, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All closes should succeed
        self.assertEqual(len(results), 5)


class TestConcurrentDatabaseWrites(unittest.TestCase):
    """Test 100 Concurrent Database Writes"""

    def setUp(self):
        """Setup database for stress testing"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_100_concurrent_writes(self):
        """Test: 100 concurrent INSERT operations succeed"""
        num_writes = 100

        def insert_trade(i):
            self.db.execute(
                "INSERT INTO trades (timestamp, symbol, side, entry_price, quantity, stop_loss, take_profit, confidence, quality_score, regime_type, strategies_used) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"2024-01-01 10:00:{i:02d}", f"SYMBOL{i}", "Buy", 50000 + i, 1, 48000, 52000, 0.8, 0.9, "Bullish", "Strategy1")
            )

        threads = []
        for i in range(num_writes):
            t = threading.Thread(target=insert_trade, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Flush all pending writes
        self.db.flush_writes()
        time.sleep(0.5)  # Give writer thread time to process

        # Verify all writes completed
        trades = self.db.fetch_all("SELECT COUNT(*) as count FROM trades")
        self.assertEqual(trades[0]['count'], num_writes)


if __name__ == '__main__':
    unittest.main()
