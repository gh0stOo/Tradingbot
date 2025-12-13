"""Thread-safe Event Queue"""

import queue
import threading
import logging
from typing import Optional
from datetime import datetime
from events.event import BaseEvent

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Thread-safe event queue for event-driven architecture.
    
    Uses queue.Queue for thread-safety and simplicity.
    Supports both blocking and non-blocking operations.
    """
    
    def __init__(self, maxsize: int = 1000) -> None:
        """
        Initialize event queue.
        
        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._queue: queue.Queue[BaseEvent] = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_dropped": 0,
        }
        logger.info(f"EventQueue initialized with maxsize={maxsize}")
    
    def put(self, event: BaseEvent, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Put event into queue.
        
        Args:
            event: Event to enqueue
            block: If True, block until space is available
            timeout: Timeout in seconds (only if block=True)
            
        Returns:
            True if event was enqueued, False if dropped
        """
        try:
            self._queue.put(event, block=block, timeout=timeout)
            with self._lock:
                self._stats["total_enqueued"] += 1
            logger.debug(f"Event enqueued: {event}")
            return True
        except queue.Full:
            with self._lock:
                self._stats["total_dropped"] += 1
            logger.warning(f"Event queue full, dropping event: {event}")
            return False
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[BaseEvent]:
        """
        Get event from queue.
        
        Args:
            block: If True, block until event is available
            timeout: Timeout in seconds (only if block=True)
            
        Returns:
            Event or None if queue is empty and block=False
        """
        try:
            event = self._queue.get(block=block, timeout=timeout)
            with self._lock:
                self._stats["total_dequeued"] += 1
            logger.debug(f"Event dequeued: {event}")
            return event
        except queue.Empty:
            return None
    
    def empty(self) -> bool:
        """Check if queue is empty"""
        return self._queue.empty()
    
    def qsize(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()
    
    def get_stats(self) -> dict:
        """Get queue statistics"""
        with self._lock:
            return self._stats.copy()
    
    def clear(self) -> None:
        """Clear all events from queue (use with caution)"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.warning("Event queue cleared")

