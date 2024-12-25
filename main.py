# --- main.py ---
"""
Main Application File
- Initializes the bot and loads environment variables.
- Sets up command and message handlers.
- Manages polling and error handling.
- Implements rate limiting, logging improvements, and async database persistence.
- Periodically kicks inactive users.
- Translates English messages to Chinese.
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
from config import BotConfig
from handlers import start, track_activity, whitelist_user, toggle_feature, configure_bot, help_command, translate_message, kick_inactive_members
from scheduler import schedule_jobs
from rate_limiter import rate_limit
from database import DatabaseManager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import ValidationError
import dotenv

# Load environment variables with error handling
try:
    config = BotConfig()
    TOKEN = config.TOKEN
    CHAT_ID = config.CHAT_ID
    BOT_OWNER_ID = config.BOT_OWNER_ID
    RATE_LIMIT_MESSAGES = config.RATE_LIMIT_MESSAGES
    RATE_LIMIT_WINDOW = config.RATE_LIMIT_WINDOW
except ValidationError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Configuration Error: {e}")
    exit(1)

# Initialize Database
try:
    db = DatabaseManager()
except Exception as e:
    logger.error(f"Database Initialization Failed: {e}")
    exit(1)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('bot.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Log a warning if CHAT_ID is missing but allow the bot to run
if not CHAT_ID:
    logger.warning("CHAT_ID is missing. Use /setchatid in the group to set it.")

# --- Error Handler --- #
async def error_handler(update: Update, context: CallbackContext) -> None:
    error_message = f"Exception while handling an update:\n{context.error}"
    logger.error(error_message)
    try:
        await context.bot.send_message(chat_id=BOT_OWNER_ID, text=f"🚨 Error Alert:\n{error_message}")
    except Exception as e:
        logger.error(f"Failed to send error message to owner: {e}")

# --- Periodic Inactive User Kick (Weekly) --- #
async def kick_inactive_users_weekly() -> None:
    logger.info("Running weekly inactive user kick...")
    await kick_inactive_members()
  
async def set_chat_id(update: Update, context: CallbackContext) -> None:
    global CHAT_ID
    CHAT_ID = update.message.chat_id
    dotenv.set_key('.env', 'CHAT_ID', str(CHAT_ID))
    await update.message.reply_text(f"Chat ID set to: {CHAT_ID}")
    logger.info(f"Chat ID {CHAT_ID} saved to .env")

# --- Main Application Setup --- #
def main() -> None:
    """Main bot application setup and start."""
    application = Application.builder().token(TOKEN).build()
    
    # Command Handlers with Rate Limiting
    application.add_handler(CommandHandler('setchatid', set_chat_id))
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('whitelist', whitelist_user, filters=filters.ChatType.GROUPS & filters.User.ADMIN))
    application.add_handler(CommandHandler('toggle', toggle_feature, filters=filters.ChatType.GROUPS & filters.User.ADMIN))
    application.add_handler(CommandHandler('configure', configure_bot, filters=filters.ChatType.GROUPS & filters.User.ADMIN))
    application.add_handler(CommandHandler('help', help_command))
    
    # Message Handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_activity))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))
    
    # Error Handler
    application.add_error_handler(error_handler)
    
    # Schedule Cleanup Jobs
    schedule_jobs(application)
    
    # Periodic Inactive User Kick (Weekly)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(kick_inactive_users_weekly, 'interval', weeks=1)
    scheduler.start()
    
    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
