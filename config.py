# --- config.py ---
"""
Bot configuration for global settings
"""
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class BotConfig(BaseSettings):
    TOKEN: str
    BOT_OWNER_ID: int
    
    class Config:
        env_file = '.env'
