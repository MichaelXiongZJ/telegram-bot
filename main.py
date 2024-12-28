"""
Main bot application with enhanced translation support
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import DatabaseManager
from server_config import ServerConfigManager
from config import get_config, BotConfig
from handlers import (
    help_command, configure_command, handle_message,
    toggle_translation_en_to_zh, toggle_translation_zh_to_en,
    kick_inactive_members, handle_new_members, 
    print_database_command, import_users_command,
    translation_stats_command, translation_cache_command
)
from translation.translation_manager import TranslationManager
import asyncio
import nest_asyncio
import signal

# Apply nest_asyncio to handle nested event loops
nest_asyncio.apply()

logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging with detailed formatting"""
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(logs_dir, f'bot_debug_{timestamp}.log')

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    
    logger.info("Logging system initialized")

async def init_components(config: BotConfig):
    """Initialize all components"""
    logger.info("Initializing components...")
    
    db = DatabaseManager(config)
    config_manager = ServerConfigManager(config)
    
    translation_manager = TranslationManager(
        api_key=config.OPENAI_API_KEY,
        cache_db_path=str(config.paths.translation_db),
        model=config.OPENAI_MODEL
    )
    
    return db, config_manager, translation_manager

def setup_handlers(application: Application):
    """Setup all command and message handlers"""
    def get_handler_deps(context):
        return {
            'db': context.application.bot_data['db'],
            'config': context.application.bot_data['config'],
            'config_manager': context.application.bot_data['config_manager'],
            'translation_manager': context.application.bot_data['translation_manager']
        }

    # Command handlers
    application.add_handler(CommandHandler(
        "help", 
        lambda update, context: help_command(update, context, **get_handler_deps(context))
    ))
    application.add_handler(CommandHandler(
        "configure",
        lambda update, context: configure_command(update, context, **get_handler_deps(context))
    ))
    application.add_handler(CommandHandler(
        "toggle_translation_en_to_zh",
        lambda update, context: toggle_translation_en_to_zh(update, context, **get_handler_deps(context))
    ))
    application.add_handler(CommandHandler(
        "toggle_translation_zh_to_en",
        lambda update, context: toggle_translation_zh_to_en(update, context, **get_handler_deps(context))
    ))
    application.add_handler(CommandHandler(
        "print_db", 
        lambda update, context: print_database_command(update, context, **get_handler_deps(context))))
    application.add_handler(CommandHandler(
        "import_users", 
        lambda update, context: import_users_command(update, context, **get_handler_deps(context))))
    application.add_handler(CommandHandler(
        "translation_stats",
        lambda update, context: translation_stats_command(update, context, **get_handler_deps(context))
    ))
    application.add_handler(CommandHandler(
        "translation_cache",
        lambda update, context: translation_cache_command(update, context, **get_handler_deps(context))
    ))

    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        lambda update, context: handle_message(update, context, **get_handler_deps(context))
    ))

    # New member handler
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        lambda update, context: handle_new_members(update, context, **get_handler_deps(context))
    ))

def setup_scheduler(application: Application, db: DatabaseManager):
    """Setup scheduler jobs"""
    scheduler = AsyncIOScheduler()
    
    # Kick inactive members for each chat based on their individual thresholds
    async def kick_all_inactive():
        chat_ids = await db.get_all_chat_ids()
        for chat_id in chat_ids:
            context = application.bot_data.get('context')
            if context:
                context.bot_data['chat_id'] = chat_id
                await kick_inactive_members(db, context)
    
    scheduler.add_job(
        lambda: asyncio.create_task(kick_all_inactive()),
        'interval',
        days=1
    )
    
    scheduler.add_job(
        lambda: application.bot_data['translation_manager'].cleanup(),
        'interval',
        days=1
    )
    
    scheduler.add_job(
        lambda: application.bot_data['db'].cleanup_old_chats(90),
        'interval',
        days=7
    )
    
    scheduler.start()
    application.bot_data['scheduler'] = scheduler

async def shutdown(application: Application):
    """Shutdown the bot gracefully"""
    logger.info("Shutting down gracefully...")

    # Stop the scheduler
    if 'scheduler' in application.bot_data:
        logger.info("Stopping scheduler...")
        application.bot_data['scheduler'].shutdown()

    # Stop the application
    await application.stop()  
    await application.shutdown()  # Use shutdown to clean up resources properly
    logger.info("Bot shutdown completed.")


async def main():
    try:
        setup_logging()
        logger.info("Starting bot...")

        config = get_config()
        db, config_manager, translation_manager = await init_components(config)

        application = Application.builder().token(config.TOKEN).build()
        application.bot_data.update({
            'config': config,
            'db': db,
            'config_manager': config_manager,
            'translation_manager': translation_manager
        })

        setup_handlers(application)
        setup_scheduler(application, db)

        loop = asyncio.get_running_loop()

        # Register shutdown handler for signals (SIGINT, SIGTERM)
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(application)))

        logger.info("Bot initialized successfully")
        try:
            await application.run_polling()
        except RuntimeError as e:
            if "Cannot close a running event loop" not in str(e):
                raise
            logger.warning("Event loop close error ignored.")
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.info("Running inside an existing loop...")
            nest_asyncio.apply()  # Allow nested event loops
            task = loop.create_task(main())  # Run bot inside the current loop
            loop.run_until_complete(task)
        else:
            asyncio.run(main())  # Standard asyncio.run if no loop exists
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}", exc_info=True)

