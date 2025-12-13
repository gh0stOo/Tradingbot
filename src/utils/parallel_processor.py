"""Parallel Processing for Coin Analysis"""

import concurrent.futures
import threading
from typing import List, Callable, Any, Optional, Dict
from functools import partial
import logging

logger = logging.getLogger(__name__)


class ParallelProcessor:
    """Process multiple coins in parallel with rate limit awareness"""
    
    def __init__(
        self,
        max_workers: int = 5,
        rate_limit_semaphore: Optional[threading.Semaphore] = None
    ):
        """
        Initialize Parallel Processor
        
        Args:
            max_workers: Maximum number of worker threads
            rate_limit_semaphore: Semaphore for rate limiting (optional)
        """
        self.max_workers = max_workers
        self.rate_limit_semaphore = rate_limit_semaphore
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    
    def process_items(
        self,
        items: List[Any],
        process_func: Callable,
        *args,
        **kwargs
    ) -> List[Any]:
        """
        Process list of items in parallel
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            *args: Additional arguments for process_func
            **kwargs: Additional keyword arguments for process_func
            
        Returns:
            List of results (in order of input items)
        """
        # Create partial function with args/kwargs
        func = partial(self._process_with_rate_limit, process_func, *args, **kwargs)
        
        # Submit all tasks
        futures = [self.executor.submit(func, item) for item in items]
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error in parallel processing: {e}", exc_info=True)
                results.append(None)
        
        return results
    
    def _process_with_rate_limit(
        self,
        process_func: Callable,
        item: Any,
        *args,
        **kwargs
    ) -> Any:
        """
        Process item with rate limiting
        
        Args:
            process_func: Function to call
            item: Item to process
            *args: Additional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Function result
        """
        # Acquire semaphore if provided
        if self.rate_limit_semaphore:
            self.rate_limit_semaphore.acquire()
            try:
                return process_func(item, *args, **kwargs)
            finally:
                self.rate_limit_semaphore.release()
        else:
            return process_func(item, *args, **kwargs)
    
    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown executor
        
        Args:
            wait: Whether to wait for pending tasks
        """
        self.executor.shutdown(wait=wait)
        logger.info("Parallel processor shutdown")


def process_coins_parallel(
    coins: List[Dict[str, Any]],
    process_func: Callable,
    max_workers: int = 5,
    batch_size: Optional[int] = None,
    rate_limit: Optional[int] = None,
    *args,
    **kwargs
) -> List[Any]:
    """
    Process coins in parallel batches
    
    Args:
        coins: List of coin dictionaries
        process_func: Function to process each coin
        max_workers: Maximum worker threads
        batch_size: Process in batches of this size (None = all at once)
        rate_limit: Maximum concurrent API calls (creates semaphore)
        *args: Additional arguments for process_func
        **kwargs: Additional keyword arguments for process_func
        
    Returns:
        List of results
    """
    # Create semaphore for rate limiting if specified
    semaphore = threading.Semaphore(rate_limit) if rate_limit else None
    
    processor = ParallelProcessor(max_workers=max_workers, rate_limit_semaphore=semaphore)
    
    try:
        if batch_size:
            # Process in batches
            all_results = []
            for i in range(0, len(coins), batch_size):
                batch = coins[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(coins)-1)//batch_size + 1} ({len(batch)} coins)")
                batch_results = processor.process_items(batch, process_func, *args, **kwargs)
                all_results.extend(batch_results)
            return all_results
        else:
            # Process all at once
            return processor.process_items(coins, process_func, *args, **kwargs)
    finally:
        processor.shutdown(wait=True)

