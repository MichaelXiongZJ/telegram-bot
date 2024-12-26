# --- config.py ---
"""
Configuration management using Pydantic
"""
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from typing import Dict, Any

load_dotenv()

class BotConfig(BaseSettings):
    # Bot Configuration
    TOKEN: str
    CHAT_ID: int | None = None
    BOT_OWNER_ID: int
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # User Management
    INACTIVE_DAYS_THRESHOLD: int = 30
    
    # Features
    TRANSLATION_ENABLED: bool = True
    DEFAULT_FEATURES: Dict[str, bool] = {
        "inactive_kick": True,
        "translation": True
    }
    
    # Database
    DB_NAME: str = "bot_data.db"
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        
    def get_feature_state(self, feature: str) -> bool:
        """Get default state for a feature"""
        return self.DEFAULT_FEATURES.get(feature, False)