# --- config.py ---
"""
Configuration management using Pydantic
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class BotConfig(BaseSettings):
    TOKEN: str
    CHAT_ID: int | None = None
    BOT_OWNER_ID: int
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 60
    INACTIVE_DAYS_THRESHOLD: int = 30
    TRANSLATION_ENABLED: bool = True

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
