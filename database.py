# --- database.py ---
"""
Resource-optimized database manager with single connection pattern
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from typing import List, Dict
from config import BotConfig
import csv

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config: BotConfig):
        self.db_path = str(config.paths.user_db)
        self._connection = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create the database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
        return self._connection

    async def cleanup(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def _get_table_name(self, chat_id: int) -> str:
        """Generate table name for a specific chat"""
        chat_id = int(chat_id)  # Ensure it's an integer
        if chat_id < 0:
            return f"chat_n{abs(chat_id)}"
        return f"chat_{chat_id}"

    async def _ensure_chat_table(self, conn: aiosqlite.Connection, chat_id: int) -> None:
        """Create chat-specific table if it doesn't exist"""
        table_name = self._get_table_name(chat_id)
        await conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                user_id INTEGER PRIMARY KEY,
                last_active TIMESTAMP NOT NULL,
                messages_count INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Create index for last_active for better performance
        await conn.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_{table_name}_last_active 
            ON {table_name}(last_active)
        ''')
        await conn.commit()

    async def update_user_activity(self, user_id: int, chat_id: int) -> None:
        """Update user's last activity time"""
        conn = await self._get_connection()
        await self._ensure_chat_table(conn, chat_id)
        table_name = self._get_table_name(chat_id)
        
        await conn.execute(f'''
            INSERT INTO {table_name} (user_id, last_active, messages_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET 
                last_active = excluded.last_active,
                messages_count = messages_count + 1
        ''', (user_id, datetime.now()))
        await conn.commit()

    async def get_inactive_users(self, chat_id: int, days: int) -> List[int]:
        """Get users inactive for specified number of days"""
        conn = await self._get_connection()
        await self._ensure_chat_table(conn, chat_id)
        table_name = self._get_table_name(chat_id)
        
        cursor = await conn.execute(f'''
            SELECT user_id 
            FROM {table_name} 
            WHERE last_active < ?
        ''', (datetime.now() - timedelta(days=days),))
        
        return [row[0] for row in await cursor.fetchall()]

    async def get_chat_statistics(self, chat_id: int) -> Dict[str, any]:
        """Get statistics for a specific chat"""
        conn = await self._get_connection()
        await self._ensure_chat_table(conn, chat_id)
        table_name = self._get_table_name(chat_id)
        
        cursor = await conn.execute(f'''
            SELECT 
                COUNT(*) as total_users,
                COALESCE(SUM(messages_count), 0) as total_messages,
                COALESCE(AVG(messages_count), 0) as avg_messages_per_user,
                MAX(last_active) as last_activity
            FROM {table_name}
        ''')
        
        row = await cursor.fetchone()
        return {
            'total_users': row[0],
            'total_messages': row[1],
            'avg_messages_per_user': row[2],
            'last_activity': row[3] or datetime.now()
        }

    async def get_all_chat_ids(self) -> List[int]:
        """Get all chat IDs from the database"""
        conn = await self._get_connection()
        cursor = await conn.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'chat_%' OR name LIKE 'chat_n%'
        ''')
        tables = await cursor.fetchall()
        
        chat_ids = []
        for (table_name,) in tables:
            try:
                if table_name.startswith('chat_n'):
                    # Handle negative chat IDs
                    chat_id = -int(table_name[6:])
                else:
                    # Handle positive chat IDs
                    chat_id = int(table_name[5:])
                chat_ids.append(chat_id)
            except ValueError:
                continue
                
        return chat_ids

    async def get_chat_user_activity(self, chat_id: int, limit: int = 50) -> List[Dict]:
        """Get user activity data for a specific chat"""
        conn = await self._get_connection()
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

    async def cleanup_old_chats(self, max_days_inactive: int = 120) -> None:
        """Remove tables for chats that have been completely inactive"""
        conn = await self._get_connection()
        threshold = datetime.now() - timedelta(days=max_days_inactive)
        
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
            
            if last_active and last_active[0] and last_active[0] < threshold:
                await conn.execute(f'DROP TABLE {table_name}')
        
        await conn.commit()

    async def import_users_from_file(self, file_path: str, default_chat_id: int = None) -> Dict[str, any]:
        """Import user IDs from a CSV file"""
        stats = {'processed': 0, 'success': 0, 'errors': 0, 'error_details': []}
        
        with open(file_path, newline='') as csvfile:
            header = csvfile.readline().strip().lower()
            csvfile.seek(0)
            
            has_chat_id = 'chat_id' in header
            reader = csv.DictReader(csvfile)
            
            if not has_chat_id and default_chat_id is None:
                raise ValueError("No chat_id column and no default_chat_id provided")
            
            conn = await self._get_connection()
            for row in reader:
                stats['processed'] += 1
                try:
                    user_id = int(row['user_id'])
                    chat_id = int(row['chat_id']) if has_chat_id else default_chat_id
                    
                    await self._ensure_chat_table(conn, chat_id)
                    await conn.execute(f'''
                        INSERT INTO {self._get_table_name(chat_id)} 
                        (user_id, last_active, messages_count)
                        VALUES (?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                        last_active = excluded.last_active
                    ''', (user_id, datetime.now(), 0))
                    stats['success'] += 1
                    
                except Exception as e:
                    stats['errors'] += 1
                    stats['error_details'].append(f"Row {stats['processed']}: {str(e)}")
            
            await conn.commit()
            return stats