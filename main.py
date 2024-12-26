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
    feature_command, translate_message, kick_inactive_members
)

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure logging with both file and console handlers"""
    # Root logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Set httpx logger to WARNING to suppress HTTP request logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Set apscheduler logger to WARNING
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    # Set telegram logger to WARNING
    logging.getLogger("telegram").setLevel(logging.WARNING)
    
    # File handlers
    # Main log file
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Messages only log file
    message_handler = logging.FileHandler('messages.log')
    message_handler.setLevel(logging.INFO)
    message_formatter = logging.Formatter('%(asctime)s - %(message)s')
    message_handler.setFormatter(message_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Create separate logger for messages
    message_logger = logging.getLogger('messages')
    message_logger.addHandler(message_handler)
    message_logger.propagate = False  # Don't propagate to root logger

    # Log uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical("Uncaught exception", 
                           exc_info=(exc_type, exc_value, exc_traceback))

    import sys
    sys.excepthook = handle_exception

    logger.info("Logging system initialized")

async def error_handler(update: Update, context: Any) -> None:
    """Handle errors in updates"""
    error_message = f"Exception while handling an update:\n{context.error}"
    logger.error(error_message)
    try:
        await context.bot.send_message(
            chat_id=context.application.bot_data['config'].BOT_OWNER_ID, 
            text=f"🚨 Error Alert:\n{error_message}"
        )
    except Exception as e:
        logger.error(f"Failed to send error message to owner: {e}")

async def post_init(application: Application) -> None:
    """Post initialization hook for the application"""
    # Load config
    config = BotConfig()
    application.bot_data['config'] = config
    logger.info("Configuration loaded")

    # Initialize database
    db = await DatabaseManager.get_instance(config.DB_NAME)
    application.bot_data['db'] = db
    logger.info("Database initialized")

    # Initialize scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: kick_inactive_members(db=db, config=config),
        'interval',
        weeks=1
    )
    scheduler.start()
    application.bot_data['scheduler'] = scheduler
    logger.info("Scheduler started")

def main() -> None:
    """Start the bot."""
    # Setup logging
    setup_logging()
    logger.info("Starting bot...")
    
    # Load config for token
    config = BotConfig()

    # Initialize application with post-init hook
    application = (
        Application.builder()
        .token(config.TOKEN)
        .post_init(post_init)
        .build()
    )

    # Setup handler dependencies (will be populated in post_init)
    def get_handler_deps(context):
        return {
            'db': context.application.bot_data['db'],
            'config': context.application.bot_data['config']
        }

    # Command Handlers
    application.add_handler(
        CommandHandler('start', 
            lambda update, context: start(update, context, **get_handler_deps(context)))
    )
    application.add_handler(
        CommandHandler('help', 
            lambda update, context: help_command(update, context, **get_handler_deps(context)))
    )
    application.add_handler(
        CommandHandler('whitelist',
            lambda update, context: whitelist_user(update, context, **get_handler_deps(context)),
            filters=filters.ChatType.GROUPS)
    )
    application.add_handler(
        CommandHandler(['feature', 'toggle', 'configure'],
            lambda update, context: feature_command(update, context, **get_handler_deps(context)),
            filters=filters.ChatType.GROUPS)
    )

    # Message Handlers
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: track_activity(update, context, **get_handler_deps(context))
        )
    )
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: translate_message(update, context, **get_handler_deps(context))
        )
    )

    # Error Handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()