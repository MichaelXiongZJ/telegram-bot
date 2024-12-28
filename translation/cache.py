"""
Translation caching system with SQLite backend
"""
import aiosqlite
from datetime import datetime, timedelta
import logging
from pathlib import Path
import hashlib
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)

class TranslationCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection = None
        Path(db_path).parent.mkdir(exist_ok=True)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            await self._ensure_tables()
        return self._connection

    async def _ensure_tables(self):
        """Create necessary tables if they don't exist"""
        conn = await self._get_connection()
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                text_hash TEXT PRIMARY KEY,
                original_text TEXT,
                translated_text TEXT,
                source_lang TEXT,
                target_lang TEXT,
                quality_score REAL,
                use_count INTEGER DEFAULT 1,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # Create indexes
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_translations_last_used 
            ON translations(last_used)
        ''')
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_translations_quality 
            ON translations(quality_score)
        ''')
        
        await conn.commit()

    def _get_text_hash(self, text: str, source_lang: str, target_lang: str) -> str:
        """Generate unique hash for translation request"""
        return hashlib.md5(
            f"{text}{source_lang}{target_lang}".encode()
        ).hexdigest()

    async def get_cached_translation(self, text: str, source_lang: str, 
                                   target_lang: str) -> Optional[Dict]:
        """Get cached translation if available"""
        conn = await self._get_connection()
        text_hash = self._get_text_hash(text, source_lang, target_lang)
        
        cursor = await conn.execute('''
            SELECT translated_text, quality_score, use_count, metadata
            FROM translations 
            WHERE text_hash = ? AND last_used > ?
        ''', (text_hash, datetime.now() - timedelta(days=30)))
        
        result = await cursor.fetchone()
        if result:
            # Update usage statistics
            await conn.execute('''
                UPDATE translations 
                SET use_count = use_count + 1, last_used = ? 
                WHERE text_hash = ?
            ''', (datetime.now(), text_hash))
            await conn.commit()
            
            return {
                'translation': result[0],
                'quality_score': result[1],
                'cache_hits': result[2],
                'metadata': json.loads(result[3]) if result[3] else {}
            }
        return None

    async def store_translation(self, text: str, translation: str, source_lang: str,
                              target_lang: str, quality_score: float,
                              metadata: Dict = None):
        """Store translation in cache"""
        conn = await self._get_connection()
        text_hash = self._get_text_hash(text, source_lang, target_lang)
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        await conn.execute('''
            INSERT OR REPLACE INTO translations 
            (text_hash, original_text, translated_text, source_lang, 
             target_lang, quality_score, last_used, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (text_hash, text, translation, source_lang, target_lang,
              quality_score, datetime.now(), metadata_json))
        
        await conn.commit()

    async def cleanup(self, max_days: int = 30):
        """Clean old or unused cache entries"""
        if self._connection:
            await self._connection.execute('''
                DELETE FROM translations 
                WHERE last_used < ? OR 
                      (use_count = 1 AND created_at < ?)
            ''', (
                datetime.now() - timedelta(days=max_days),
                datetime.now() - timedelta(days=7)
            ))
            await self._connection.commit()

    async def _get_cache_stats(self) -> Dict:
        """Get detailed cache statistics"""
        conn = await self._get_connection()
        cursor = await conn.execute('''
            SELECT 
                COUNT(*) as total_entries,
                AVG(quality_score) as avg_quality,
                AVG(use_count) as avg_use_count,
                SUM(use_count) as total_uses,
                COUNT(CASE WHEN last_used > ? THEN 1 END) as active_entries,
                COUNT(CASE WHEN quality_score > 0.9 THEN 1 END) as high_quality
            FROM translations
        ''', (datetime.now() - timedelta(days=7),))
        
        row = await cursor.fetchone()
        
        return {
            'total_entries': row[0],
            'avg_quality': row[1],
            'avg_use_count': row[2],
            'total_uses': row[3],
            'active_entries': row[4],
            'high_quality_entries': row[5],
            'hit_rate': row[3] / max(row[0], 1)
        }

    async def get_translation_history(self, limit: int = 100) -> list:
        """Get recent translation history"""
        conn = await self._get_connection()
        cursor = await conn.execute('''
            SELECT original_text, translated_text, quality_score, 
                   last_used, use_count
            FROM translations
            ORDER BY last_used DESC
            LIMIT ?
        ''', (limit,))
        
        return await cursor.fetchall()