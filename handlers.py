# --- handlers.py ---
"""
Command and Message Handlers
"""
from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime
import logging
from typing import Any, Dict
from deep_translator import GoogleTranslator
from langdetect import detect
import re
from database import DatabaseManager, DatabaseError
from config import BotConfig
from logging_utils import log_command, log_message

logger = logging.getLogger(__name__)
translator = GoogleTranslator(source='auto', target='zh-CN')

# Move is_admin to top of the file, before any other functions
async def is_admin(update: Update, context: CallbackContext, config: BotConfig) -> bool:
    """Check if user is admin, creator, or bot owner"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return False
            
        # Check if user is bot owner
        if user.id == config.BOT_OWNER_ID:
            logger.info(f"User {user.id} is bot owner")
            return True
            
        # Get member info
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ['administrator', 'creator']
        logger.info(f"User {user.id} admin status check: {is_admin} ({member.status})")
        return is_admin
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

@log_command
async def start(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle /start command"""
    await update.message.reply_text('Hello! I am a bot made by Kuma, I will make the group clean and active.')

@log_command
async def help_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle /help command with detailed usage information"""
    help_text = (
        "🤖 *Bot Commands and Features*\n\n"
        "*Basic Commands:*\n"
        "• `/start` - Start the bot and receive welcome message\n"
        "• `/help` - Show this help message\n\n"
        
        "*Admin Commands:*\n"
        "• `/whitelist <user_id> [add/remove]` - Manage whitelist\n"
        "  Examples:\n"
        "  `/whitelist 123456 add` - Add user to whitelist\n"
        "  `/whitelist 123456 remove` - Remove user from whitelist\n\n"
        
        "• `/feature <feature> <on/off>` - Enable/disable features\n"
        "  (Also works with /toggle or /configure)\n"
        "  Available features:\n"
        "  - `inactive_kick` - Auto-remove inactive users\n"
        "  - `translation` - English to Chinese translation\n"
        "  Examples:\n"
        "  `/feature translation on` - Enable translation\n"
        "  `/feature inactive_kick off` - Disable inactive user kick\n\n"
        
        "*Automatic Features:*\n"
        "• *Activity Tracking*\n"
        "  - Bot tracks user activity for inactive user management\n"
        "  - Users inactive for " + str(config.INACTIVE_DAYS_THRESHOLD) + " days may be removed\n"
        "  - Whitelisted users are exempt from removal\n\n"
        
        "• *Translation*\n"
        "  - Automatically translates English messages to Chinese\n"
        "  - Must contain at least 2 words to be translated\n"
        "  - Can be disabled using `/feature translation off`\n\n"
        
        "*Rate Limiting:*\n"
        f"• Limited to {config.RATE_LIMIT_MESSAGES} commands per {config.RATE_LIMIT_WINDOW} seconds\n\n"
        
        "*Note:*\n"
        "• Admin commands can only be used by group administrators\n"
        "• Bot owner has access to all commands in all groups\n"
        "• Features can be configured independently for each group"
    )
    
    try:
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error sending formatted help: {e}")
        await update.message.reply_text(help_text)

@log_command
async def whitelist_user(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle /whitelist command"""
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return
        
    if not context.args or len(context.args) not in [1, 2]:
        await update.message.reply_text('Usage: /whitelist <user_id> [add/remove]')
        return
        
    try:
        user_id = int(context.args[0])
        action = context.args[1].lower() if len(context.args) > 1 else 'add'
        
        if action not in ['add', 'remove']:
            await update.message.reply_text('Invalid action. Use "add" or "remove".')
            return
            
        await db.manage_whitelist(
            user_id,
            update.effective_chat.id,
            update.effective_user.id,
            add=(action == 'add')
        )
        
        action_text = 'whitelisted' if action == 'add' else 'removed from whitelist'
        await update.message.reply_text(f'User {user_id} has been {action_text}.')
    except ValueError:
        await update.message.reply_text('Invalid user ID.')
    except Exception as e:
        logger.error(f"Whitelist operation failed: {e}")
        await update.message.reply_text('Failed to update whitelist.')

@log_command
async def feature_command(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle feature command"""
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return
        
    if len(context.args) != 2:
        await update.message.reply_text('Usage: /feature <feature_name> <on/off>')
        return
        
    feature, state = context.args[0].lower(), context.args[1].lower()
    
    if feature not in config.DEFAULT_FEATURES:
        features_list = ', '.join(config.DEFAULT_FEATURES.keys())
        await update.message.reply_text(f'Invalid feature. Available features: {features_list}')
        return
        
    if state not in ['on', 'off']:
        await update.message.reply_text('Invalid state. Use "on" or "off".')
        return
        
    try:
        enabled = (state == 'on')
        await db.set_chat_setting(update.effective_chat.id, feature, enabled)
        await update.message.reply_text(f'Feature "{feature}" has been turned {state}.')
    except Exception as e:
        logger.error(f"Feature toggle failed: {e}")
        await update.message.reply_text('Failed to toggle feature.')

async def track_activity(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Track user activity and log message"""
    try:
        # Log the message first
        await log_message(update)
        
        # Then track activity
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

        text = update.message.text
        # Check if message contains enough text
        if len(text.split()) >= 2:
            try:
                # Detect language
                lang = detect(text)
                if lang == 'en':
                    translated = translator.translate(text)
                    await update.message.reply_text(f'Translation: {translated}')
                    logger.info(f"Translated message:\nOriginal: {text}\nTranslated: {translated}")
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
        async with db.get_connection() as conn:
            cursor = await conn.execute('SELECT DISTINCT chat_id FROM chat_settings WHERE feature_inactive_kick = TRUE')
            chat_ids = [row[0] for row in await cursor.fetchall()]

        for chat_id in chat_ids:
            try:
                inactive_users = await db.get_inactive_users(
                    chat_id,
                    config.INACTIVE_DAYS_THRESHOLD
                )
                
                for user_id in inactive_users:
                    try:
                        logger.info(f"Would kick inactive user {user_id} from chat {chat_id}")
                        # Note: Implement actual kick logic here
                    except Exception as e:
                        logger.error(f"Failed to kick user {user_id} from chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Error processing chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error in kick_inactive_members: {e}")