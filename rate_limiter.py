# --- rate_limiter.py ---
"""
Memory-efficient rate limiter using SQLite
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, db_path: str = 'database/rate_limits.db'):
        self.db_path = db_path
        self._connection = None
        # Ensure database directory exists
        Path(db_path).parent.mkdir(exist_ok=True)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._ensure_table()
        return self._connection

    async def _ensure_table(self) -> None:
        """Create rate limits table if it doesn't exist"""
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                chat_id INTEGER,
                user_id INTEGER,
                timestamp TIMESTAMP,
                PRIMARY KEY (chat_id, user_id, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_rate_limits_cleanup 
            ON rate_limits(timestamp);
        ''')
        await self._connection.commit()

    async def check_rate_limit(self, chat_id: int, user_id: int, limit: int, window: int) -> bool:
        """Check if user exceeds rate limit"""
        conn = await self._get_connection()
        current_time = datetime.now()
        window_start = current_time - timedelta(seconds=window)
        
        # Periodically clean old entries (with 10% probability to reduce overhead)
        if hash(str(current_time)) % 10 == 0:
            await conn.execute('DELETE FROM rate_limits WHERE timestamp < ?', (window_start,))
        
        # Count recent actions
        cursor = await conn.execute('''
            SELECT COUNT(*) FROM rate_limits
            WHERE chat_id = ? AND user_id = ? AND timestamp > ?
        ''', (chat_id, user_id, window_start))
        count = (await cursor.fetchone())[0]
        
        if count >= limit:
            return True
        
        # Add new action
        await conn.execute('''
            INSERT INTO rate_limits (chat_id, user_id, timestamp)
            VALUES (?, ?, ?)
        ''', (chat_id, user_id, current_time))
        await conn.commit()
        
        return False

    async def cleanup(self):
        """Close database connection and clean old entries"""
        if self._connection:
            # Clean old entries before closing
            await self._connection.execute('''
                DELETE FROM rate_limits 
                WHERE timestamp < ?
            ''', (datetime.now() - timedelta(hours=1),))
            await self._connection.commit()
            await self._connection.close()
            self._connection = None