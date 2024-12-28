# --- server_config.py ---
"""
Optimized server configuration management
"""
import aiosqlite
from datetime import datetime
import logging
from typing import Dict, Any
import json
from config import BotConfig

logger = logging.getLogger(__name__)

class ServerConfigManager:
    def __init__(self, config: BotConfig):
        self.db_path = str(config.paths.config_db)
        self._connection = None
        self.default_config = {
            'rate_limit_messages': config.DEFAULT_RATE_LIMIT,
            'rate_limit_window': config.DEFAULT_RATE_WINDOW,
            'inactive_days_threshold': config.DEFAULT_INACTIVE_DAYS,
            'translate_en_to_zh': False,
            'translate_zh_to_en': False
        }

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._ensure_table()
        return self._connection

    async def _ensure_table(self) -> None:
        """Create config table if it doesn't exist"""
        await self._connection.execute('''
            CREATE TABLE IF NOT EXISTS server_config (
                chat_id INTEGER PRIMARY KEY,
                config_json TEXT NOT NULL,
                last_updated TIMESTAMP NOT NULL
            )
        ''')
        await self._connection.commit()

    async def get_config(self, chat_id: int) -> Dict[str, Any]:
        """Get chat-specific configuration"""
        conn = await self._get_connection()
        cursor = await conn.execute('''
            SELECT config_json FROM server_config WHERE chat_id = ?
        ''', (chat_id,))
        row = await cursor.fetchone()
        
        if row:
            return json.loads(row[0])
        
        # Create default config if none exists
        await self.update_config(chat_id, self.default_config)
        return self.default_config.copy()

    async def update_config(self, chat_id: int, config: Dict[str, Any]) -> None:
        """Update chat-specific configuration"""
        conn = await self._get_connection()
        await conn.execute('''
            INSERT INTO server_config (chat_id, config_json, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                config_json = excluded.config_json,
                last_updated = excluded.last_updated
        ''', (chat_id, json.dumps(config), datetime.now()))
        await conn.commit()

    async def cleanup(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None