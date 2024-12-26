# --- database.py ---
"""
Database Manager with improved error handling and consistent connection management
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import List, Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Base exception for database operations"""
    pass

class DatabaseManager:
    _instance = None
    
    def __init__(self, db_name: str = 'bot_data.db'):
        self.db_name = db_name
        self._initialized = False
        self._connection = None
    
    @classmethod
    async def get_instance(cls, db_name: str = 'bot_data.db'):
        """Get or create singleton instance"""
        if not cls._instance:
            cls._instance = cls(db_name)
            await cls._instance.initialize()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize database and create tables"""
        if not self._initialized:
            await self.create_tables()
            self._initialized = True

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection using context manager"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_name)
        try:
            yield self._connection
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise DatabaseError(f"Database operation failed: {e}")

    async def create_tables(self) -> None:
        """Create necessary database tables"""
        async with self.get_connection() as conn:
            await conn.executescript('''
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id INTEGER,
                    chat_id INTEGER,
                    last_active TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS whitelist (
                    user_id INTEGER,
                    chat_id INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    added_by INTEGER,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id INTEGER PRIMARY KEY,
                    feature_inactive_kick BOOLEAN DEFAULT TRUE,
                    feature_translation BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS rate_limits (
                    user_id INTEGER,
                    chat_id INTEGER,
                    action_time TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id, action_time)
                );
            ''')
            await conn.commit()

    async def update_user_activity(self, user_id: int, chat_id: int) -> None:
        """Update user's last activity time"""
        async with self.get_connection() as conn:
            await conn.execute('''
                INSERT INTO user_activity (user_id, chat_id, last_active)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, chat_id)
                DO UPDATE SET last_active = excluded.last_active
            ''', (user_id, chat_id, datetime.now()))
            await conn.commit()

    async def get_inactive_users(self, chat_id: int, days: int) -> List[int]:
        """Get users inactive for specified number of days"""
        threshold = datetime.now() - timedelta(days=days)
        async with self.get_connection() as conn:
            cursor = await conn.execute('''
                SELECT user_id FROM user_activity
                WHERE chat_id = ? AND last_active < ?
                AND user_id NOT IN (SELECT user_id FROM whitelist WHERE chat_id = ?)
            ''', (chat_id, threshold, chat_id))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def check_rate_limit(self, user_id: int, chat_id: int, window: int, limit: int) -> bool:
        """Check if user has exceeded rate limit"""
        async with self.get_connection() as conn:
            # Clean old entries
            await conn.execute('''
                DELETE FROM rate_limits
                WHERE action_time < ?
            ''', (datetime.now() - timedelta(seconds=window),))
            
            # Count recent actions
            cursor = await conn.execute('''
                SELECT COUNT(*) FROM rate_limits
                WHERE user_id = ? AND chat_id = ?
                AND action_time > ?
            ''', (user_id, chat_id, datetime.now() - timedelta(seconds=window)))
            count = (await cursor.fetchone())[0]
            
            # Add new action if under limit
            if count < limit:
                await conn.execute('''
                    INSERT INTO rate_limits (user_id, chat_id, action_time)
                    VALUES (?, ?, ?)
                ''', (user_id, chat_id, datetime.now()))
                await conn.commit()
                return False
            return True

    async def manage_whitelist(self, user_id: int, chat_id: int, admin_id: int, add: bool = True) -> None:
        """Add or remove user from whitelist"""
        async with self.get_connection() as conn:
            if add:
                await conn.execute('''
                    INSERT OR REPLACE INTO whitelist (user_id, chat_id, added_by)
                    VALUES (?, ?, ?)
                ''', (user_id, chat_id, admin_id))
            else:
                await conn.execute('''
                    DELETE FROM whitelist
                    WHERE user_id = ? AND chat_id = ?
                ''', (user_id, chat_id))
            await conn.commit()

    async def get_chat_setting(self, chat_id: int, feature: str) -> bool:
        """Get chat feature setting"""
        if not feature.isalnum():
            raise ValueError("Invalid feature name")
            
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                f'SELECT feature_{feature} FROM chat_settings WHERE chat_id = ?',
                (chat_id,)
            )
            row = await cursor.fetchone()
            return bool(row[0]) if row else True

    async def set_chat_setting(self, chat_id: int, feature: str, enabled: bool) -> None:
        """Set chat feature setting"""
        if not feature.isalnum():
            raise ValueError("Invalid feature name")
            
        async with self.get_connection() as conn:
            await conn.execute(
                f'''
                INSERT INTO chat_settings (chat_id, feature_{feature})
                VALUES (?, ?)
                ON CONFLICT(chat_id)
                DO UPDATE SET feature_{feature} = excluded.feature_{feature}
                ''',
                (chat_id, enabled)
            )
            await conn.commit()