# --- handlers.py ---
"""
Command and Message Handlers
- Manages user commands like start, help, whitelist, and configure.
- Translates messages and handles inactive user kicks.
- Implements rate limiting and async database persistence.
- Translates English messages to Chinese.
"""

from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime
from googletrans import Translator
import re
import logging
from rate_limiter import rate_limit
from database import DatabaseManager

translator = Translator()
db = DatabaseManager()
FEATURES = {
    'inactive_user_kick': True,
    'whitelisting': True
}

async def start(update: Update, context: CallbackContext) -> None:
    if rate_limit(update.message.from_user.id, 5, 60):
        await update.message.reply_text('Too many requests. Please wait.')
        return
    await update.message.reply_text('Hello! I am a bot made by Kuma, I will make the group clean and active.')

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/whitelist <user_id> - Whitelist a user (admin only)\n"
        "/toggle <feature> - Toggle feature on/off (admin only)\n"
        "/configure <feature> <on/off> - Configure bot features (admin only)"
    )
    await update.message.reply_text(help_text)

async def track_activity(update: Update, context: CallbackContext) -> None:
    await db.update_user_activity(update.message.from_user.id)

async def translate_message(update: Update, context: CallbackContext) -> None:
    # Match if there are multiple consecutive English words
    if re.search(r'\b[a-zA-Z]{3,}\b', update.message.text):
        try:
            translated = translator.translate(update.message.text, dest='zh-cn').text
            await update.message.reply_text(f'Translation: {translated}')
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            await update.message.reply_text('Translation service is currently unavailable.')

async def kick_inactive_members() -> None:
    logger.info("Kicking inactive users...")
    inactive_users = await db.get_inactive_users(days=30)
    for user_id in inactive_users:
        try:
            await db.kick_user(user_id)
            logger.info(f"Kicked inactive user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to kick user {user_id}: {e}")
