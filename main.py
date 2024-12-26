# --- main.py ---
"""
Main Application File
"""

import logging
from typing import Dict, Any
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BotConfig
from database import DatabaseManager
from handlers import (
    start, help_command, track_activity, whitelist_user,
    toggle_feature, configure_bot, translate_message,
    kick_inactive_members
)

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure logging"""
    logger.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

async def post_init(application: Application) -> None:
    """Post initialization hook for the application"""
    # Load config
    config = BotConfig()

    # Initialize database
    db = await DatabaseManager.get_instance()

    # Initialize scheduler with the same event loop as the application
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: kick_inactive_members(db=db, config=config),
        'interval',
        weeks=1
    )
    scheduler.start()

    # Setup handler dependencies
    handler_deps = {
        'db': db,
        'config': config
    }

    # Command Handlers
    application.add_handler(
        CommandHandler('start', 
            lambda update, context: start(update, context, **handler_deps))
    )
    application.add_handler(
        CommandHandler('help', 
            lambda update, context: help_command(update, context, **handler_deps))
    )
    application.add_handler(
        CommandHandler('whitelist',
            lambda update, context: whitelist_user(update, context, **handler_deps),
            filters=filters.ChatType.GROUPS)
    )
    application.add_handler(
        CommandHandler('toggle',
            lambda update, context: toggle_feature(update, context, **handler_deps),
            filters=filters.ChatType.GROUPS)
    )
    application.add_handler(
        CommandHandler('configure',
            lambda update, context: configure_bot(update, context, **handler_deps),
            filters=filters.ChatType.GROUPS)
    )

    # Message Handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: track_activity(update, context, **handler_deps)
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: translate_message(update, context, **handler_deps)
        )
    )

    # Error Handler
    async def error_handler(update: Update, context: Any) -> None:
        error_message = f"Exception while handling an update:\n{context.error}"
        logger.error(error_message)
        try:
            await context.bot.send_message(
                chat_id=config.BOT_OWNER_ID, 
                text=f"🚨 Error Alert:\n{error_message}"
            )
        except Exception as e:
            logger.error(f"Failed to send error message to owner: {e}")

    application.add_error_handler(error_handler)

def main() -> None:
    """Start the bot."""
    # Setup logging
    setup_logging()
    logger.info("Starting bot...")
    
    # Load config
    config = BotConfig()

    # Build and start application
    application = (
        Application.builder()
        .token(config.TOKEN)
        .post_init(post_init)
        .build()
    )
    
    logger.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()