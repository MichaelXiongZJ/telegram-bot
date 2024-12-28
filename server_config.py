# --- server_config.py ---
"""
Server-specific configuration management
"""
from pydantic_settings import BaseSettings
from datetime import datetime
import logging
from typing import Dict, Any
import aiosqlite
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ServerConfig(BaseSettings):
    """Default configuration values for each server"""
    rate_limit_messages: int = 5
    rate_limit_window: int = 10
    inactive_days_threshold: int = 60
    translate_en_to_zh: bool = False
    translate_zh_to_en: bool = False

class ServerConfigManager:
    def __init__(self, db_name: str = 'bot_data.db'):
        self.db_name = db_name
        self._initialized = False
        
    @asynccontextmanager
    async def get_connection(self):
        async with aiosqlite.connect(self.db_name) as conn:
            if not self._initialized:
                await self._create_tables(conn)
                self._initialized = True
            yield conn

    async def _create_tables(self, conn) -> None:
        """Create server configuration table"""
        try:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS server_config (
                    chat_id INTEGER PRIMARY KEY,
                    rate_limit_messages INTEGER NOT NULL,
                    rate_limit_window INTEGER NOT NULL,
                    inactive_days_threshold INTEGER NOT NULL,
                    translate_en_to_zh BOOLEAN NOT NULL,
                    translate_zh_to_en BOOLEAN NOT NULL,
                    last_updated TIMESTAMP NOT NULL
                )
            ''')
            await conn.commit()
            logger.info("Server config table created successfully")
        except Exception as e:
            logger.error(f"Error creating server config table: {e}", exc_info=True)
            raise

    async def get_config(self, chat_id: int) -> Dict[str, Any]:
        """Get server-specific configuration"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute('''
                    SELECT * FROM server_config WHERE chat_id = ?
                ''', (chat_id,))
                row = await cursor.fetchone()
                
                if row:
                    return {
                        'rate_limit_messages': row[1],
                        'rate_limit_window': row[2],
                        'inactive_days_threshold': row[3],
                        'translate_en_to_zh': bool(row[4]),
                        'translate_zh_to_en': bool(row[5])
                    }
                else:
                    # Return default config and create entry
                    default_config = ServerConfig().model_dump()
                    await self.update_config(chat_id, default_config)
                    return default_config
        except Exception as e:
            logger.error(f"Error getting server config: {e}", exc_info=True)
            return ServerConfig().model_dump()

    async def update_config(self, chat_id: int, config: Dict[str, Any]) -> None:
        """Update server-specific configuration"""
        try:
            async with self.get_connection() as conn:
                await conn.execute('''
                    INSERT INTO server_config (
                        chat_id, rate_limit_messages, rate_limit_window,
                        inactive_days_threshold, translate_en_to_zh,
                        translate_zh_to_en, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        rate_limit_messages = excluded.rate_limit_messages,
                        rate_limit_window = excluded.rate_limit_window,
                        inactive_days_threshold = excluded.inactive_days_threshold,
                        translate_en_to_zh = excluded.translate_en_to_zh,
                        translate_zh_to_en = excluded.translate_zh_to_en,
                        last_updated = excluded.last_updated
                ''', (
                    chat_id,
                    config['rate_limit_messages'],
                    config['rate_limit_window'],
                    config['inactive_days_threshold'],
                    config['translate_en_to_zh'],
                    config['translate_zh_to_en'],
                    datetime.now()
                ))
                await conn.commit()
                logger.info(f"Updated config for chat {chat_id}")
        except Exception as e:
            logger.error(f"Error updating server config: {e}", exc_info=True)
            raise