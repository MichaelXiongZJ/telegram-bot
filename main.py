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
from config import get_config
from handlers import start, track_activity, whitelist_user, toggle_feature, configure_bot, help_command, translate_message, kick_inactive_members
from scheduler import schedule_jobs
from rate_limiter import rate_limit
from database import DatabaseManager
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Load environment variables
config = get_config()
TOKEN = config['TOKEN']
CHAT_ID = config['CHAT_ID']
BOT_OWNER_ID = config['BOT_OWNER_ID']
RATE_LIMIT_MESSAGES = config['RATE_LIMIT_MESSAGES']
RATE_LIMIT_WINDOW = config['RATE_LIMIT_WINDOW']

# Initialize Database
db = DatabaseManager()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('bot.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Ensure critical environment variables are present
if not TOKEN or not CHAT_ID or not BOT_OWNER_ID:
    logger.error("Bot token, chat ID, or bot owner ID is missing. Check .env file.")
    exit(1)

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

async def get_chat_id(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Chat ID: {update.message.chat_id}")


# --- Main Application Setup --- #
def main() -> None:
    """Main bot application setup and start."""
    application = Application.builder().token(TOKEN).build()
    
    # Command Handlers with Rate Limiting
    application.add_handler(CommandHandler('getchatid', get_chat_id))
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
