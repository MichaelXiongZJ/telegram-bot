# --- server_config.py ---
"""
Server-specific configuration management
"""
import aiosqlite
from datetime import datetime
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager
import json
from config import BotConfig

logger = logging.getLogger(__name__)

class ServerConfigManager:
    def __init__(self, config: BotConfig):
        self.db_path = str(config.paths.config_db)
        self._connection = None
        self._initialized = False
        self.default_config = {
            'rate_limit_messages': config.DEFAULT_RATE_LIMIT,
            'rate_limit_window': config.DEFAULT_RATE_WINDOW,
            'inactive_days_threshold': config.DEFAULT_INACTIVE_DAYS,
            'translate_en_to_zh': False,
            'translate_zh_to_en': False
        }

    async def _init_db(self):
        """Initialize database connection and tables"""
        if not self._initialized:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            self._initialized = True

    async def _create_tables(self) -> None:
        """Create server configuration table"""
        try:
            await self._connection.execute('''
                CREATE TABLE IF NOT EXISTS server_config (
                    chat_id INTEGER PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    last_updated TIMESTAMP NOT NULL
                )
            ''')
            await self._connection.commit()
            logger.info("Server config table created successfully")
        except Exception as e:
            logger.error(f"Error creating server config table: {e}", exc_info=True)
            raise

    async def get_config(self, chat_id: int) -> Dict[str, Any]:
        """Get server-specific configuration"""
        try:
            await self._init_db()
            cursor = await self._connection.execute('''
                SELECT config_json FROM server_config WHERE chat_id = ?
            ''', (chat_id,))
            row = await cursor.fetchone()
            
            if row:
                return json.loads(row[0])
            else:
                # Return default config and create entry
                await self.update_config(chat_id, self.default_config)
                return self.default_config.copy()
                
        except Exception as e:
            logger.error(f"Error getting server config: {e}", exc_info=True)
            return self.default_config.copy()

    async def update_config(self, chat_id: int, config: Dict[str, Any]) -> None:
        """Update server-specific configuration"""
        try:
            await self._init_db()
            config_json = json.dumps(config)
            
            await self._connection.execute('''
                INSERT INTO server_config (chat_id, config_json, last_updated)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    config_json = excluded.config_json,
                    last_updated = excluded.last_updated
            ''', (chat_id, config_json, datetime.now()))
            await self._connection.commit()
            
        except Exception as e:
            logger.error(f"Error updating server config: {e}", exc_info=True)
            raise

    async def cleanup(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._initialized = False