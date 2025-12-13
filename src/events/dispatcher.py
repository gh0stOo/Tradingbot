"""Event Dispatcher with Handler Registry"""

import logging
import threading
from typing import Callable, Dict, List, Optional, Type
from events.event import BaseEvent

logger = logging.getLogger(__name__)


HandlerFunction = Callable[[BaseEvent], None]


class EventDispatcher:
    """
    Event dispatcher with priority-based handler registry.
    
    Handlers are called in priority order (higher priority first).
    Errors in handlers do not block the queue.
    """
    
    def __init__(self) -> None:
        """Initialize event dispatcher"""
        self._handlers: Dict[Type[BaseEvent], List[tuple[int, HandlerFunction]]] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_dispatched": 0,
            "total_handled": 0,
            "total_errors": 0,
        }
        logger.info("EventDispatcher initialized")
    
    def register_handler(
        self,
        event_type: Type[BaseEvent],
        handler: HandlerFunction,
        priority: int = 100
    ) -> None:
        """
        Register event handler.
        
        Args:
            event_type: Event type to handle
            handler: Handler function (takes event as parameter)
            priority: Handler priority (higher = called first, default=100)
        """
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            
            # Add handler with priority
            self._handlers[event_type].append((priority, handler))
            
            # Sort by priority (descending)
            self._handlers[event_type].sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"Handler registered for {event_type.__name__} with priority {priority}")
    
    def unregister_handler(
        self,
        event_type: Type[BaseEvent],
        handler: HandlerFunction
    ) -> bool:
        """
        Unregister event handler.
        
        Args:
            event_type: Event type
            handler: Handler function to remove
            
        Returns:
            True if handler was removed, False if not found
        """
        with self._lock:
            if event_type not in self._handlers:
                return False
            
            # Find and remove handler
            handlers = self._handlers[event_type]
            for i, (priority, h) in enumerate(handlers):
                if h == handler:
                    handlers.pop(i)
                    if not handlers:
                        del self._handlers[event_type]
                    logger.info(f"Handler unregistered for {event_type.__name__}")
                    return True
        
        return False
    
    def dispatch(self, event: BaseEvent) -> int:
        """
        Dispatch event to all registered handlers.
        
        Args:
            event: Event to dispatch
            
        Returns:
            Number of handlers that processed the event
        """
        event_type = type(event)
        handlers_to_call: List[tuple[int, HandlerFunction]] = []
        
        # Get handlers (copy to avoid lock contention during execution)
        with self._lock:
            if event_type in self._handlers:
                handlers_to_call = self._handlers[event_type].copy()
        
        if not handlers_to_call:
            logger.debug(f"No handlers registered for {event_type.__name__}")
            return 0
        
        # Call handlers in priority order
        handled_count = 0
        for priority, handler in handlers_to_call:
            try:
                handler(event)
                handled_count += 1
                with self._lock:
                    self._stats["total_handled"] += 1
            except Exception as e:
                with self._lock:
                    self._stats["total_errors"] += 1
                logger.error(
                    f"Error in handler for {event_type.__name__} (priority {priority}): {e}",
                    exc_info=True
                )
                # Continue with next handler - errors don't block
        
        with self._lock:
            self._stats["total_dispatched"] += 1
        
        return handled_count
    
    def has_handlers(self, event_type: Type[BaseEvent]) -> bool:
        """Check if any handlers are registered for event type"""
        with self._lock:
            return event_type in self._handlers and len(self._handlers[event_type]) > 0
    
    def get_stats(self) -> dict:
        """Get dispatcher statistics"""
        with self._lock:
            return self._stats.copy()

