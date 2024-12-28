# --- config.py ---
"""
Centralized configuration with simplified paths
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
import os

load_dotenv()

class PathConfig:
    """Simple path configuration"""
    def __init__(self):
        self.db_dir = Path('database')
        self.user_db = self.db_dir / 'user_activity.db'
        self.config_db = self.db_dir / 'server_config.db'
        
        # Create database directory if it doesn't exist
        self.db_dir.mkdir(exist_ok=True)

class BotConfig(BaseSettings):
    """Bot configuration"""
    TOKEN: str
    BOT_OWNER_ID: int
    
    # Default chat settings
    DEFAULT_RATE_LIMIT: int = 1
    DEFAULT_RATE_WINDOW: int = 1
    DEFAULT_INACTIVE_DAYS: int = 30
    
    class Config:
        env_file = '.env'
        case_sensitive = True

    @property
    def paths(self) -> PathConfig:
        """Get path configuration"""
        return PathConfig()

@lru_cache()
def get_config() -> BotConfig:
    """Get cached bot configuration"""
    return BotConfig()