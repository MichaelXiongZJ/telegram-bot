# --- main.py ---
"""
Main bot application with detailed logging
"""
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BotConfig
from database import DatabaseManager
from handlers import (
    help_command, configure_command, handle_message,
    toggle_command, kick_inactive_members
)

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure logging with detailed formatting"""
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to DEBUG for maximum detail

    # File handler for all logs
    file_handler = logging.FileHandler('bot_debug.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Console handler for INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy modules
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    logger.info("Logging system initialized")

async def post_init(application: Application) -> None:
    """Post initialization callback"""
    logger.info("Running post-init setup")
    try:
        # Store scheduler in application context
        logger.debug("Setting up scheduler")
        application.bot_data['scheduler'] = AsyncIOScheduler()
        
        # Add jobs
        logger.debug("Adding scheduler jobs")
        application.bot_data['scheduler'].add_job(
            lambda: kick_inactive_members(
                application.bot_data['db'],
                application.bot_data['config'],
                application
            ),
            'interval',
            days=1
        )
        
        # Start scheduler
        logger.debug("Starting scheduler")
        application.bot_data['scheduler'].start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Error in post_init: {e}", exc_info=True)
        raise

def main() -> None:
    """Start the bot with detailed logging"""
    try:
        # Setup logging
        setup_logging()
        logger.info("Starting bot initialization...")
        
        # Load config
        logger.debug("Loading configuration")
        config = BotConfig()
        logger.info("Configuration loaded")

        # Initialize database
        logger.debug("Initializing database")
        db = DatabaseManager()
        logger.info("Database initialized")

        # Initialize application
        logger.debug("Building application")
        application = (
            Application.builder()
            .token(config.TOKEN)
            .post_init(post_init)
            .build()
        )
        logger.info("Application built")
        
        # Store dependencies
        logger.debug("Storing dependencies in application context")
        application.bot_data['config'] = config
        application.bot_data['db'] = db

        # Setup handler dependencies
        def get_handler_deps(context):
            return {
                'db': context.application.bot_data['db'],
                'config': context.application.bot_data['config']
            }

        # Add handlers
        logger.debug("Adding command handlers")
        application.add_handler(CommandHandler("help", 
            lambda update, context: help_command(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("configure",
            lambda update, context: configure_command(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("toggle",
            lambda update, context: toggle_command(update, context, **get_handler_deps(context))))
            
        logger.debug("Adding message handler")
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: handle_message(update, context, **get_handler_deps(context))))
        
        logger.info("All handlers added successfully")
        
        # Start bot
        logger.info("Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.critical("Fatal error during initialization", exc_info=True)
        raise

if __name__ == "__main__":
    main()