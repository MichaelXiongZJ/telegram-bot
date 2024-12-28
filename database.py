# --- database.py ---
"""
Database manager with separate tables per chat
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import List, Dict
import asyncio
from contextlib import asynccontextmanager
from config import BotConfig
import csv

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config: BotConfig):
        self.db_path = str(config.paths.user_db)
        self._connection_pool = {}
        self._pool_lock = asyncio.Lock()
        self._max_connections = 5
        self._initialized_tables = set()

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get a connection from the pool or create a new one"""
        async with self._pool_lock:
            for conn_id, (conn, in_use) in self._connection_pool.items():
                if not in_use:
                    self._connection_pool[conn_id] = (conn, True)
                    return conn

            if len(self._connection_pool) < self._max_connections:
                conn = await aiosqlite.connect(self.db_path)
                conn_id = id(conn)
                self._connection_pool[conn_id] = (conn, True)
                return conn

            raise RuntimeError("Connection pool exhausted")

    async def _release_connection(self, conn: aiosqlite.Connection) -> None:
        """Release a connection back to the pool"""
        async with self._pool_lock:
            conn_id = id(conn)
            if conn_id in self._connection_pool:
                self._connection_pool[conn_id] = (conn, False)

    @asynccontextmanager
    async def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = await self._get_connection()
            yield conn
        finally:
            if conn:
                await self._release_connection(conn)

    def _get_table_name(self, chat_id: int) -> str:
        """
        Generate table name for a specific chat.
        Prefixes negative IDs with 'n' to maintain the sign while being SQL-safe
        """
        chat_id = int(chat_id)  # Ensure it's an integer
        if chat_id < 0:
            return f"chat_n{abs(chat_id)}"
        return f"chat_{chat_id}"

    def _get_chat_id_from_table(self, table_name: str) -> int:
        """Extract original chat ID from table name"""
        # Remove 'chat_' prefix
        id_part = table_name.replace('chat_', '')
        # Handle negative IDs
        if id_part.startswith('n'):
            return -int(id_part[1:])
        return int(id_part)

    async def get_all_chat_ids(self) -> List[int]:
        """Get all chat IDs from database"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE 'chat_%'
                ''')
                tables = await cursor.fetchall()
                return [self._get_chat_id_from_table(table[0]) for table in tables]
        except Exception as e:
            logger.error(f"Error getting chat IDs: {e}", exc_info=True)
            return []

    async def _ensure_chat_table(self, conn: aiosqlite.Connection, chat_id: int) -> None:
        """Create chat-specific table if it doesn't exist"""
        table_name = self._get_table_name(chat_id)
        if table_name in self._initialized_tables:
            return

        sql = f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                user_id INTEGER PRIMARY KEY,
                last_active TIMESTAMP NOT NULL,
                messages_count INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        logger.debug(f"Creating table with SQL: {sql}")
        
        try:
            await conn.execute(sql)
            await conn.commit()
            self._initialized_tables.add(table_name)
            logger.info(f"Successfully created table: {table_name}")
        except Exception as e:
            logger.error(f"Error creating table. SQL: {sql}, Error: {str(e)}")
            raise

    async def update_user_activity(self, user_id: int, chat_id: int) -> None:
        """Update user's last activity time"""
        try:
            async with self.get_connection() as conn:
                await self._ensure_chat_table(conn, chat_id)
                table_name = self._get_table_name(chat_id)
                current_time = datetime.now()
                
                sql = f'''
                    INSERT INTO {table_name} (user_id, last_active, messages_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id) DO UPDATE SET 
                        last_active = excluded.last_active,
                        messages_count = messages_count + 1
                '''
                
                await conn.execute(sql, (user_id, current_time))
                await conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating user activity: {e}", exc_info=True)
            raise

    async def get_inactive_users(self, chat_id: int, days: int) -> List[int]:
        """Get users inactive for specified number of days"""
        try:
            threshold = datetime.now() - timedelta(days=days)
            async with self.get_connection() as conn:
                await self._ensure_chat_table(conn, chat_id)
                table_name = self._get_table_name(chat_id)
                
                sql = f'SELECT user_id FROM {table_name} WHERE last_active < ?'
                cursor = await conn.execute(sql, (threshold,))
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting inactive users: {e}", exc_info=True)
            raise

    async def get_chat_statistics(self, chat_id: int) -> Dict[str, any]:
        """Get statistics for a specific chat"""
        try:
            async with self.get_connection() as conn:
                await self._ensure_chat_table(conn, chat_id)
                table_name = self._get_table_name(chat_id)
                
                sql = f'''
                    SELECT 
                        COUNT(*) as total_users,
                        SUM(messages_count) as total_messages,
                        AVG(messages_count) as avg_messages_per_user,
                        MAX(last_active) as last_activity
                    FROM {table_name}
                '''
                logger.debug(f"Executing statistics query: {sql}")
                
                cursor = await conn.execute(sql)
                row = await cursor.fetchone()
                
                stats = {
                    'total_users': row[0] if row[0] is not None else 0,
                    'total_messages': row[1] if row[1] is not None else 0,
                    'avg_messages_per_user': row[2] if row[2] is not None else 0,
                    'last_activity': row[3] if row[3] is not None else datetime.now()
                }
                logger.debug(f"Retrieved statistics: {stats}")
                return stats
                
        except Exception as e:
            logger.error(f"Error getting chat statistics for chat {chat_id}: {str(e)}")
            # Return default statistics in case of error
            return {
                'total_users': 0,
                'total_messages': 0,
                'avg_messages_per_user': 0,
                'last_activity': datetime.now()
            }

    async def cleanup_old_chats(self, max_days_inactive: int = 120) -> None:
        """Remove tables for chats that have been completely inactive"""
        try:
            threshold = datetime.now() - timedelta(days=max_days_inactive)
            async with self.get_connection() as conn:
                cursor = await conn.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE 'chat_%'
                ''')
                tables = await cursor.fetchall()
                
                for (table_name,) in tables:
                    cursor = await conn.execute(f'''
                        SELECT MAX(last_active) FROM {table_name}
                    ''')
                    last_active = await cursor.fetchone()
                    
                    if last_active and last_active[0] < threshold:
                        await conn.execute(f'DROP TABLE {table_name}')
                        self._initialized_tables.discard(table_name)
                
                await conn.commit()
                
        except Exception as e:
            logger.error(f"Error cleaning up old chats: {e}", exc_info=True)
            raise

    async def import_users_from_file(self, file_path: str, default_chat_id: int = None) -> Dict[str, any]:
        """
        Import user IDs from a CSV file.
        
        Expected CSV format:
        - With chat_id column: "user_id,chat_id"
        - Without chat_id column: "user_id" (will use default_chat_id)
        """
        logger.info(f"Importing users from file {file_path}")
        stats = {
            'processed': 0,
            'success': 0,
            'errors': 0,
            'error_details': []
        }
        
        try:
            with open(file_path, newline='') as csvfile:
                # Read first line to check headers
                header = csvfile.readline().strip().lower()
                csvfile.seek(0)  # Reset file pointer
                
                has_chat_id = 'chat_id' in header
                reader = csv.DictReader(csvfile)
                
                if not has_chat_id and default_chat_id is None:
                    raise ValueError("CSV file doesn't contain chat_id column and no default_chat_id provided")
                
                for row in reader:
                    stats['processed'] += 1
                    try:
                        user_id = int(row['user_id'])
                        chat_id = int(row['chat_id']) if has_chat_id else default_chat_id
                        
                        async with self.get_connection() as conn:
                            await self._ensure_chat_table(conn, chat_id)
                            await conn.execute(f'''
                                INSERT INTO {self._get_table_name(chat_id)} 
                                (user_id, last_active, messages_count)
                                VALUES (?, ?, ?)
                                ON CONFLICT(user_id) DO UPDATE SET
                                last_active = excluded.last_active
                            ''', (user_id, datetime.now(), 0))
                            await conn.commit()
                        
                        stats['success'] += 1
                        
                    except Exception as e:
                        stats['errors'] += 1
                        stats['error_details'].append(f"Row {stats['processed']}: {str(e)}")
                        logger.error(f"Error importing user from row {stats['processed']}: {e}")
                        
            logger.info(f"Import completed: {stats['success']} successful, {stats['errors']} errors")
            return stats
            
        except Exception as e:
            logger.error(f"Error importing users from file: {e}", exc_info=True)
            raise

    async def get_all_chat_ids(self) -> List[int]:
        """Get all chat IDs from database"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name LIKE 'chat_%'
                ''')
                tables = await cursor.fetchall()
                return [int(table[0].split('_')[1]) for table in tables]
        except Exception as e:
            logger.error(f"Error getting chat IDs: {e}", exc_info=True)
            return []

    async def get_chat_user_activity(self, chat_id: int, limit: int = 50) -> List[Dict]:
        """Get user activity data for a specific chat"""
        try:
            async with self.get_connection() as conn:
                await self._ensure_chat_table(conn, chat_id)
                table_name = self._get_table_name(chat_id)
                
                cursor = await conn.execute(f'''
                    SELECT 
                        user_id,
                        last_active,
                        messages_count,
                        first_seen
                    FROM {table_name}
                    ORDER BY last_active DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = await cursor.fetchall()
                return [{
                    'user_id': row[0],
                    'last_active': row[1],
                    'messages_count': row[2],
                    'first_seen': row[3]
                } for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting user activity for chat {chat_id}: {e}", exc_info=True)
            return []