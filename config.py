# --- config.py ---
"""
Bot configuration
"""
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class BotConfig(BaseSettings):
    # Bot Configuration
    TOKEN: str
    BOT_OWNER_ID: int
    
    # User Management (configurable via /configure command)
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 10  # seconds
    INACTIVE_DAYS_THRESHOLD: int = 60
    
    # Features
    TRANSLATE_EN_TO_ZH: bool = True  # English to Chinese toggle
    TRANSLATE_ZH_TO_EN: bool = True  # Chinese to English toggle
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'