# --- rate_limiter.py ---
"""
Rate limiter with improved per-chat configuration
"""
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        self._rate_limits: Dict[int, Dict[int, List[datetime]]] = defaultdict(lambda: defaultdict(list))
        
    def check_rate_limit(self, chat_id: int, user_id: int, limit: int, window: int) -> bool:
        """
        Check if user exceeds rate limit for specific chat
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            limit: Maximum allowed actions
            window: Time window in seconds
            
        Returns:
            bool: True if rate limit exceeded, False otherwise
        """
        try:
            current_time = datetime.now()
            window_start = current_time - timedelta(seconds=window)
            
            # Clean old entries
            self._rate_limits[chat_id][user_id] = [
                time for time in self._rate_limits[chat_id][user_id]
                if time > window_start
            ]
            
            # Check if limit exceeded
            if len(self._rate_limits[chat_id][user_id]) >= limit:
                logger.warning(f"Rate limit exceeded for user {user_id} in chat {chat_id}")
                return True
                
            # Add new action
            self._rate_limits[chat_id][user_id].append(current_time)
            return False
            
        except Exception as e:
            logger.error(f"Error in rate limiter: {e}", exc_info=True)
            return False
            
    def cleanup_old_data(self, max_age: int = 3600) -> None:
        """
        Remove old rate limit data
        
        Args:
            max_age: Maximum age of data in seconds (default: 1 hour)
        """
        try:
            cutoff = datetime.now() - timedelta(seconds=max_age)
            
            for chat_id in list(self._rate_limits.keys()):
                for user_id in list(self._rate_limits[chat_id].keys()):
                    # Remove old timestamps
                    self._rate_limits[chat_id][user_id] = [
                        time for time in self._rate_limits[chat_id][user_id]
                        if time > cutoff
                    ]
                    
                    # Remove empty user entries
                    if not self._rate_limits[chat_id][user_id]:
                        del self._rate_limits[chat_id][user_id]
                        
                # Remove empty chat entries
                if not self._rate_limits[chat_id]:
                    del self._rate_limits[chat_id]
                    
            logger.debug("Rate limiter cleanup completed")
            
        except Exception as e:
            logger.error(f"Error cleaning up rate limiter: {e}", exc_info=True)