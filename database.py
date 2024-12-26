# --- database.py ---
"""
Database manager with proper async connection handling
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import List
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_name: str = 'bot_data.db'):
        logger.info(f"Initializing DatabaseManager with database: {db_name}")
        self.db_name = db_name
        self._initialized = False

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection using context manager"""
        async with aiosqlite.connect(self.db_name) as conn:
            if not self._initialized:
                await self._create_tables(conn)
                self._initialized = True
            yield conn

    async def _create_tables(self, conn) -> None:
        """Create necessary tables"""
        logger.info("Creating database tables")
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id INTEGER,
                    chat_id INTEGER,
                    last_active TIMESTAMP,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            await conn.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}", exc_info=True)
            raise

    async def update_user_activity(self, user_id: int, chat_id: int) -> None:
        """Update user's last activity time"""
        logger.debug(f"Updating activity for user {user_id} in chat {chat_id}")
        try:
            async with self.get_connection() as conn:
                current_time = datetime.now()
                await conn.execute('''
                    INSERT INTO user_activity (user_id, chat_id, last_active)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, chat_id)
                    DO UPDATE SET last_active = excluded.last_active
                ''', (user_id, chat_id, current_time))
                await conn.commit()
            logger.debug(f"Activity updated successfully for user {user_id}")
        except Exception as e:
            logger.error(f"Error updating user activity: {e}", exc_info=True)
            raise

    async def get_inactive_users(self, chat_id: int, days: int) -> List[int]:
        """Get users inactive for specified number of days"""
        logger.debug(f"Getting inactive users for chat {chat_id} (threshold: {days} days)")
        try:
            threshold = datetime.now() - timedelta(days=days)
            async with self.get_connection() as conn:
                cursor = await conn.execute('''
                    SELECT user_id FROM user_activity
                    WHERE chat_id = ? AND last_active < ?
                ''', (chat_id, threshold))
                rows = await cursor.fetchall()
                inactive_users = [row[0] for row in rows]
                logger.info(f"Found {len(inactive_users)} inactive users in chat {chat_id}")
                return inactive_users
        except Exception as e:
            logger.error(f"Error getting inactive users: {e}", exc_info=True)
            raise