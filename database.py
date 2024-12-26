# --- database.py ---
"""
Database Manager (Async with aiosqlite)
- Handles user activity and whitelisting persistence using SQLite
- Implements singleton pattern with async initialization
"""

import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

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

    async def get_connection(self):
        """Get database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_name)
        return self._connection

    async def create_tables(self) -> None:
        """Create necessary database tables"""
        connection = await self.get_connection()
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                last_active TIMESTAMP,
                UNIQUE(user_id, chat_id)
            )
        ''')
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, chat_id)
            )
        ''')
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                feature_inactive_kick BOOLEAN DEFAULT TRUE,
                feature_translation BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await connection.commit()

    async def close(self) -> None:
        """Close the database connection"""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def update_user_activity(self, user_id: int, chat_id: int) -> None:
        """Update user's last activity time"""
        connection = await self.get_connection()
        await connection.execute('''
            INSERT INTO user_activity (user_id, chat_id, last_active)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, chat_id)
            DO UPDATE SET last_active = excluded.last_active
        ''', (user_id, chat_id, datetime.now()))
        await connection.commit()

    async def get_inactive_users(self, chat_id: int, days: int) -> List[int]:
        """Get users inactive for specified number of days"""
        threshold = datetime.now() - timedelta(days=days)
        connection = await self.get_connection()
        cursor = await connection.execute('''
            SELECT user_id FROM user_activity
            WHERE chat_id = ? AND last_active < ?
            AND user_id NOT IN (SELECT user_id FROM whitelist WHERE chat_id = ?)
        ''', (chat_id, threshold, chat_id))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def add_to_whitelist(self, user_id: int, chat_id: int) -> None:
        """Add user to whitelist"""
        connection = await self.get_connection()
        await connection.execute('''
            INSERT OR REPLACE INTO whitelist (user_id, chat_id)
            VALUES (?, ?)
        ''', (user_id, chat_id))
        await connection.commit()

    async def remove_from_whitelist(self, user_id: int, chat_id: int) -> None:
        """Remove user from whitelist"""
        connection = await self.get_connection()
        await connection.execute('''
            DELETE FROM whitelist
            WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        await connection.commit()

    async def is_whitelisted(self, user_id: int, chat_id: int) -> bool:
        """Check if user is whitelisted"""
        connection = await self.get_connection()
        cursor = await connection.execute('''
            SELECT 1 FROM whitelist
            WHERE user_id = ? AND chat_id = ?
        ''', (user_id, chat_id))
        return bool(await cursor.fetchone())

    async def get_chat_setting(self, chat_id: int, feature: str) -> bool:
        """Get chat feature setting"""
        connection = await self.get_connection()
        cursor = await connection.execute(f'''
            SELECT feature_{feature} FROM chat_settings
            WHERE chat_id = ?
        ''', (chat_id,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else True

    async def set_chat_setting(self, chat_id: int, feature: str, enabled: bool) -> None:
        """Set chat feature setting"""
        connection = await self.get_connection()
        await connection.execute(f'''
            INSERT INTO chat_settings (chat_id, feature_{feature})
            VALUES (?, ?)
            ON CONFLICT(chat_id)
            DO UPDATE SET feature_{feature} = excluded.feature_{feature}
        ''', (chat_id, enabled))
        await connection.commit()