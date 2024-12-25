# --- config.py ---
from pydantic import BaseSettings

class BotConfig(BaseSettings):
    TOKEN: str
    CHAT_ID: int
    BOT_OWNER_ID: int
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 60

    class Config:
        env_file = '.env'
