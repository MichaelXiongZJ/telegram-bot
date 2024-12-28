# --- main.py ---
"""
Main bot application with detailed logging
"""
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import DatabaseManager
from server_config import ServerConfigManager
from config import get_config
from handlers import (
    help_command, configure_command, handle_message,
    toggle_translation_en_to_zh, toggle_translation_zh_to_en,
    kick_inactive_members, handle_new_members, 
    print_database_command, import_users_command
)

logger = logging.getLogger(__name__)

def setup_logging() -> None:
    """Configure logging with detailed formatting and size limit"""
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler with rotation
    log_file = 'bot_debug.log'
    max_log_size = 5 * 1024 * 1024  # 5 MB
    backup_count = 3

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_log_size,
        backupCount=backup_count
    )
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

    logger.info("Logging system initialized with size limit")

async def post_init(application: Application, db: DatabaseManager) -> None:
    logger.info("Running post-init setup")
    try:
        # Initialize scheduler
        application.bot_data['scheduler'] = AsyncIOScheduler()
        
        # Add kick inactive members job
        application.bot_data['scheduler'].add_job(
            lambda: kick_inactive_members(
                db,
                application
            ),
            'interval',
            days=1
        )
        
        # Add database cleanup job
        application.bot_data['scheduler'].add_job(
            lambda: db.cleanup_old_chats(90),  # Cleanup chats inactive for 90 days
            'interval',
            days=7  # Run weekly
        )
        
        application.bot_data['scheduler'].start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Error in post_init: {e}", exc_info=True)

async def shutdown(application: Application) -> None:
    """Cleanup resources on shutdown"""
    logger.info("Running shutdown cleanup")
    try:
        # Stop scheduler
        if 'scheduler' in application.bot_data:
            application.bot_data['scheduler'].shutdown()
            
        # Cleanup database connections
        if 'config_manager' in application.bot_data:
            await application.bot_data['config_manager'].cleanup()
            
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

def main() -> None:
    """Start the bot with detailed logging"""
    try:
        # Setup logging
        setup_logging()
        logger.info("Starting bot initialization...")
        
        # Load global config
        logger.debug("Loading configuration")
        config = get_config()
        logger.info("Configuration loaded")

        # Initialize database and server config manager
        logger.debug("Initializing database and config manager")
        db = DatabaseManager(config)
        config_manager = ServerConfigManager(config)
        logger.info("Database and config manager initialized")

        # Initialize application
        logger.debug("Building application")
        application = (
            Application.builder()
            .token(config.TOKEN)
            .post_init(lambda app: post_init(app, db))
            .post_shutdown(shutdown)
            .build()
        )
        logger.info("Application built")
        
        # Store dependencies
        logger.debug("Storing dependencies in application context")
        application.bot_data['config'] = config
        application.bot_data['db'] = db
        application.bot_data['config_manager'] = config_manager

        # Setup handler dependencies
        def get_handler_deps(context):
            return {
                'db': context.application.bot_data['db'],
                'config': context.application.bot_data['config'],
                'config_manager': context.application.bot_data['config_manager']
            }

        # Add handlers
        logger.debug("Adding command handlers")
        application.add_handler(CommandHandler("help", 
            lambda update, context: help_command(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("configure",
            lambda update, context: configure_command(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("toggle_translation_en_to_zh",
            lambda update, context: toggle_translation_en_to_zh(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("toggle_translation_zh_to_en",
            lambda update, context: toggle_translation_zh_to_en(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("print_db", 
            lambda update, context: print_database_command(update, context, **get_handler_deps(context))))
        application.add_handler(CommandHandler("import_users", 
            lambda update, context: import_users_command(update, context, **get_handler_deps(context))))

        logger.debug("Adding message handlers")
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: handle_message(update, context, **get_handler_deps(context))))
        
        # Add new member handler
        logger.debug("Adding new member handler")
        application.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            lambda update, context: handle_new_members(update, context, **get_handler_deps(context))))
        
        logger.info("All handlers added successfully")
        
        # Start bot
        logger.info("Starting polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.critical("Fatal error during initialization", exc_info=True)
        raise

if __name__ == "__main__":
    main()