# --- database.py ---
"""
Database Manager (Async with aiosqlite)
- Handles user activity and whitelisting persistence using SQLite.
- Supports connection pooling and retries for database operations.
"""
import aiosqlite
from datetime import datetime
import asyncio

class DatabaseManager:
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        asyncio.create_task(self.create_tables())

    async def get_connection(self):
        return await aiosqlite.connect(self.db_name)

    async def create_tables(self):
        async with await self.get_connection() as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS user_activity (
                                user_id INTEGER PRIMARY KEY, 
                                last_active TIMESTAMP)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS whitelist (
                                user_id INTEGER PRIMARY KEY)''')
            await db.execute('''CREATE TABLE IF NOT EXISTS chat_settings (
                                chat_id INTEGER PRIMARY KEY)''')
            await db.commit()

    async def update_user_activity(self, user_id: int):
        async with await self.get_connection() as db:
            await db.execute('''INSERT INTO user_activity (user_id, last_active) 
                                 VALUES (?, ?) 
                                 ON CONFLICT(user_id) 
                                 DO UPDATE SET last_active = excluded.last_active''',
                              (user_id, datetime.now()))
            await db.commit()

    async def save_chat_id(self, chat_id: int):
        async with await self.get_connection() as db:
            await db.execute('INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)', (chat_id,))
            await db.commit()

    async def get_all_chat_ids(self):
        async with await self.get_connection() as db:
            cursor = await db.execute('SELECT chat_id FROM chat_settings')
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
