# --- utils/logging_utils.py ---
"""
Utilities for logging messages and commands
"""
import logging
import functools
from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime

logger = logging.getLogger(__name__)

def log_command(func):
    """Decorator to log command usage"""
    @functools.wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user = update.effective_user
        chat = update.effective_chat
        command = update.message.text
        
        log_message = (
            f"Command: {command}\n"
            f"User: {user.id} (@{user.username} - {user.first_name} {user.last_name})\n"
            f"Chat: {chat.id} ({chat.type} - {chat.title if chat.type != 'private' else 'Private'})\n"
            f"Time: {datetime.now()}"
        )
        logger.info(log_message)
        
        return await func(update, context, *args, **kwargs)
    return wrapper

async def log_message(update: Update) -> None:
    """Log message details"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        message = update.message
        
        log_message = (
            f"Message: {message.text}\n"
            f"User: {user.id} (@{user.username} - {user.first_name} {user.last_name})\n"
            f"Chat: {chat.id} ({chat.type} - {chat.title if chat.type != 'private' else 'Private'})\n"
            f"Time: {datetime.now()}\n"
            f"Message Type: {'Text' if message.text else 'Media/Other'}"
        )
        
        # Additional media logging
        if message.photo:
            log_message += "\nMedia: Photo"
        elif message.video:
            log_message += "\nMedia: Video"
        elif message.document:
            log_message += f"\nMedia: Document ({message.document.file_name})"
        elif message.sticker:
            log_message += "\nMedia: Sticker"
        elif message.voice:
            log_message += "\nMedia: Voice Message"
        elif message.audio:
            log_message += "\nMedia: Audio"
            
        logger.info(log_message)
    except Exception as e:
        logger.error(f"Error logging message: {e}")