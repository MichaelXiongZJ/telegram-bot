"""
Centralized configuration with enhanced translation settings using Pydantic V2
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, ConfigDict
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
import os

load_dotenv()

class PathConfig:
    """Enhanced path configuration"""
    def __init__(self):
        self.db_dir = Path('database')
        self.user_db = self.db_dir / 'user_activity.db'
        self.config_db = self.db_dir / 'server_config.db'
        self.translation_db = self.db_dir / 'translation_cache.db'
        self.logs_dir = Path('logs')
        
        # Create necessary directories
        self.db_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

class BotConfig(BaseSettings):
    """Enhanced bot configuration with Pydantic V2 validation"""
    # Basic bot settings
    TOKEN: str
    BOT_OWNER_ID: int
    
    # OpenAI settings
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # Default chat settings
    DEFAULT_RATE_LIMIT: int = 2
    DEFAULT_RATE_WINDOW: int = 1
    DEFAULT_INACTIVE_DAYS: int = 30
    
    # Translation settings
    TRANSLATION_CACHE_DAYS: int = 30
    TRANSLATION_MIN_QUALITY: float = 0.9
    TRANSLATION_BATCH_SIZE: int = 5
    
    # Advanced settings
    ADULT_CONTENT_MODE: bool = True
    PATTERN_THRESHOLD: float = 0.5
    MAX_BATCH_SIZE: int = 10

    # Model config
    model_config = ConfigDict(case_sensitive=True, env_file='.env')

    # Validators
    @field_validator('TOKEN')
    @classmethod
    def validate_token(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("Invalid Telegram bot token")
        return v

    @field_validator('BOT_OWNER_ID')
    @classmethod
    def validate_owner_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Bot owner ID must be positive")
        return v

    @field_validator('OPENAI_API_KEY')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("Invalid OpenAI API key")
        return v

    @field_validator('OPENAI_MODEL')
    @classmethod
    def validate_model(cls, v: str) -> str:
        allowed_models = [
            "gpt-4-1106-preview",
            "gpt-4",
            "gpt-3.5-turbo"
        ]
        if v not in allowed_models:
            raise ValueError(f"Model must be one of: {', '.join(allowed_models)}")
        return v

    @field_validator('DEFAULT_RATE_LIMIT')
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        if not 1 <= v <= 100:
            raise ValueError("Rate limit must be between 1 and 100")
        return v

    @field_validator('DEFAULT_RATE_WINDOW')
    @classmethod
    def validate_rate_window(cls, v: int) -> int:
        if not 1 <= v <= 3600:
            raise ValueError("Rate window must be between 1 and 3600 seconds")
        return v

    @field_validator('DEFAULT_INACTIVE_DAYS')
    @classmethod
    def validate_inactive_days(cls, v: int) -> int:
        if not 1 <= v <= 365:
            raise ValueError("Inactive days must be between 1 and 365")
        return v

    @field_validator('TRANSLATION_CACHE_DAYS')
    @classmethod
    def validate_cache_days(cls, v: int) -> int:
        if not 1 <= v <= 90:
            raise ValueError("Cache days must be between 1 and 90")
        return v

    @field_validator('TRANSLATION_MIN_QUALITY')
    @classmethod
    def validate_quality(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Quality score must be between 0.0 and 1.0")
        return v

    @field_validator('TRANSLATION_BATCH_SIZE', 'MAX_BATCH_SIZE')
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("Batch size must be between 1 and 20")
        return v

    @field_validator('PATTERN_THRESHOLD')
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("Pattern threshold must be between 0.0 and 1.0")
        return v

    @property
    def paths(self) -> PathConfig:
        """Get path configuration"""
        return PathConfig()

@lru_cache()
def get_config() -> BotConfig:
    """Get cached bot configuration"""
    return BotConfig()