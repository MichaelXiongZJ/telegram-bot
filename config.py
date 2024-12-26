# --- config.py ---
"""
Bot configuration
"""
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class BotConfig(BaseSettings):
    # Bot Configuration
    TOKEN: str
    BOT_OWNER_ID: int
    
    # User Management (configurable via /configure command)
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 60  # seconds
    INACTIVE_DAYS_THRESHOLD: int = 30
    
    # Features
    TRANSLATION_ENABLED: bool = True
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'