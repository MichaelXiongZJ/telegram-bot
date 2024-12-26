# --- handlers.py ---
"""
Command and Message Handlers
- Manages user commands and message processing
- Implements feature toggles and admin controls
- Handles translations and user activity tracking
"""

from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime
import logging
from typing import Any, Dict
from deep_translator import GoogleTranslator
import re
from database import DatabaseManager
from config import BotConfig

logger = logging.getLogger(__name__)
translator = GoogleTranslator(source='auto', target='zh-CN')

async def is_admin(update: Update, context: CallbackContext) -> bool:
    """Check if the user is an admin in the current chat"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return False
            
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def start(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle /start command"""
    await update.message.reply_text('Hello! I am a bot made by Kuma, I will make the group clean and active.')

async def help_command(
    update: Update,
    context: CallbackContext,
    **kwargs
) -> None:
    """Handle /help command"""
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/whitelist <user_id> - Whitelist a user (admin only)\n"
        "/toggle <feature> - Toggle feature on/off (admin only)\n"
        "/configure <feature> <on/off> - Configure bot features (admin only)"
    )
    await update.message.reply_text(help_text)

async def track_activity(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Track user activity"""
    try:
        await db.update_user_activity(
            update.message.from_user.id,
            update.message.chat_id
        )
    except Exception as e:
        logger.error(f"Error tracking activity: {e}")

async def translate_message(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Translate English messages to Chinese"""
    if not config.TRANSLATION_ENABLED:
        return

    try:
        chat_id = update.message.chat_id
        translation_enabled = await db.get_chat_setting(chat_id, 'translation')
        
        if not translation_enabled:
            return

        if re.search(r'\b[a-zA-Z]{3,}\b', update.message.text):
            try:
                translated = translator.translate(update.message.text)
                await update.message.reply_text(f'Translation: {translated}')
            except Exception as e:
                logger.error(f"Translation failed: {e}")
                await update.message.reply_text('Translation service is currently unavailable.')
    except Exception as e:
        logger.error(f"Error in translation handler: {e}")

async def kick_inactive_members(
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Kick inactive members from all chats"""
    logger.info("Starting inactive user kick job")
    try:
        async with await db.get_connection() as conn:
            cursor = await conn.execute('SELECT DISTINCT chat_id FROM user_activity')
            chat_ids = [row[0] for row in await cursor.fetchall()]

        for chat_id in chat_ids:
            try:
                feature_enabled = await db.get_chat_setting(chat_id, 'inactive_kick')
                if not feature_enabled:
                    continue

                inactive_users = await db.get_inactive_users(
                    chat_id,
                    config.INACTIVE_DAYS_THRESHOLD
                )
                
                for user_id in inactive_users:
                    try:
                        # Note: Implement actual kick logic here using bot API
                        logger.info(f"Would kick inactive user {user_id} from chat {chat_id}")
                    except Exception as e:
                        logger.error(f"Failed to kick user {user_id} from chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error in kick_inactive_members: {e}")

async def whitelist_user(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Handle /whitelist command"""
    if not await is_admin(update, context):
        await update.message.reply_text('This command is only available to administrators.')
        return
        
    if not context.args:
        await update.message.reply_text('Usage: /whitelist <user_id>')
        return
        
    try:
        user_id = int(context.args[0])
        chat_id = update.message.chat_id
        await db.add_to_whitelist(user_id, chat_id)
        await update.message.reply_text(f'User {user_id} has been whitelisted.')
    except ValueError:
        await update.message.reply_text('Invalid user ID.')
    except Exception as e:
        logger.error(f"Whitelist operation failed: {e}")
        await update.message.reply_text('Failed to whitelist user.')

async def toggle_feature(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Handle /toggle command"""
    if not await is_admin(update, context):
        await update.message.reply_text('This command is only available to administrators.')
        return
        
    if len(context.args) < 2:
        await update.message.reply_text('Usage: /toggle <feature> <on/off>')
        return
        
    feature, state = context.args[0], context.args[1].lower()
    valid_features = ['inactive_kick', 'translation']
    
    if feature not in valid_features or state not in ['on', 'off']:
        await update.message.reply_text(
            f'Invalid feature or state. Valid features are: {", ".join(valid_features)}'
        )
        return
        
    try:
        chat_id = update.message.chat_id
        enabled = (state == 'on')
        await db.set_chat_setting(chat_id, feature, enabled)
        await update.message.reply_text(f'Feature {feature} has been turned {state}.')
    except Exception as e:
        logger.error(f"Feature toggle failed: {e}")
        await update.message.reply_text('Failed to toggle feature.')

async def configure_bot(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Handle /configure command"""
    if not await is_admin(update, context):
        await update.message.reply_text('This command is only available to administrators.')
        return
        
    if len(context.args) < 2:
        await update.message.reply_text('Usage: /configure <feature> <on/off>')
        return
        
    feature, state = context.args[0], context.args[1].lower()
    valid_features = ['inactive_kick', 'translation']
    
    if feature not in valid_features or state not in ['on', 'off']:
        await update.message.reply_text(
            f'Invalid feature or state. Valid features are: {", ".join(valid_features)}'
        )
        return
        
    try:
        chat_id = update.message.chat
    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        await update.message.reply_text('Failed to configure feature.')