# --- handlers.py ---
"""
Message and command handlers with professional language detection
"""
from telegram import Update
from telegram.ext import CallbackContext
import logging
from deep_translator import GoogleTranslator
from database import DatabaseManager
from config import BotConfig
import os
import re

logger = logging.getLogger(__name__)

# Initialize translator
logger.info("Initializing translators...")
try:
    translator_en_to_zh = GoogleTranslator(source='en', target='zh-CN')
    translator_zh_to_en = GoogleTranslator(source='zh-CN', target='en')
    logger.info("Translators initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize translator: {e}", exc_info=True)

async def is_admin(update: Update, context: CallbackContext, config: BotConfig) -> bool:
    """Check if user is admin, creator, or bot owner"""
    logger.debug(f"Checking admin status for user {update.effective_user.id}")
    try:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            logger.warning("No user or chat in update")
            return False
            
        if user.id == config.BOT_OWNER_ID:
            logger.info(f"User {user.id} is bot owner")
            return True
            
        member = await context.bot.get_chat_member(chat.id, user.id)
        is_admin = member.status in ['administrator', 'creator']
        logger.info(f"User {user.id} admin status: {is_admin} ({member.status})")
        return is_admin
    except Exception as e:
        logger.error(f"Error checking admin status: {e}", exc_info=True)
        return False

def count_chinese_chars(text: str) -> int:
    return sum(1 for char in text if '\u4e00' <= char <= '\u9fff')  # Unicode range for CJK Unified Ideographs

def detect_language(text: str) -> str:
    # Regex to match Chinese characters (Unicode range for CJK Unified Ideographs)
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')

    # Count Chinese characters
    chinese_chars = len(chinese_char_pattern.findall(text))
    
    # Calculate total length (excluding spaces)
    total_chars = len(text.replace(" ", "",))

    # If more than half the text is Chinese, classify it as Chinese
    if chinese_chars / total_chars > 0.5:
        return 'zh'
    else:
        return 'en'

async def handle_message(
        
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle regular messages with translation support"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    
    logger.info(f"Handling message from user {user_id} in chat {chat_id}: {text}")

    try:
        if (config.TRANSLATE_ZH_TO_EN or config.TRANSLATE_EN_TO_ZH) and text:
            logger.debug("Translation is enabled")
            
            detected_lang = detect_language(text)
            logger.info(f"Detected language: {detected_lang}")
            if detected_lang == 'zh' and config.TRANSLATE_ZH_TO_EN:
                translated = translator_zh_to_en.translate(text)
            elif detected_lang == 'en' and config.TRANSLATE_EN_TO_ZH:
                translated = translator_en_to_zh.translate(text)
            else:
                translated = None

            if translated and translated != text:
                await update.message.reply_text(translated)

            logger.info(f"Translated message: {translated}")
        
        # Update activity time
        logger.debug(f"Updating activity time for user {user_id}")
        await db.update_user_activity(user_id, chat_id)
        
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)


async def help_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
    **kwargs
) -> None:
    """Show help message"""
    help_text = (
        "*Current Settings:*\n"
        f"• Rate limit: {config.RATE_LIMIT_MESSAGES} messages\n"
        f"• Time window: {config.RATE_LIMIT_WINDOW} seconds\n"
        f"• Inactive threshold: {config.INACTIVE_DAYS_THRESHOLD} days\n"
        "*Current Translation Settings:*\n"
        "/toggle translation* on/off\n"
        f"• EN -> ZH: {'Enabled' if config.TRANSLATE_EN_TO_ZH else 'Disabled'}\n"
        f"• ZH -> EN: {'Enabled' if config.TRANSLATE_ZH_TO_EN else 'Disabled'}\n"
    )
    
    try:
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending help: {e}")
        await update.message.reply_text(help_text)

async def handle_new_members(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    **kwargs
) -> None:
    """Handle new members joining the chat"""
    if not update.message.new_chat_members:
        return
    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        if not member.is_bot:  # Don't track bots
            try:
                logger.info(f"New member {member.id} joined chat {chat_id}")
                await db.update_user_activity(member.id, chat_id)
                logger.debug(f"Added new member {member.id} to activity tracking")
            except Exception as e:
                logger.error(f"Error tracking new member {member.id}: {e}", exc_info=True)

async def configure_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
) -> None:
    """Handle bot configuration"""
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            'Usage: /configure <setting> <value>\n'
            'Available settings:\n'
            '• rate_limit - Messages per time window\n'
            '• rate_window - Time window in seconds\n'
            '• inactive_days - Days before user is considered inactive'
        )
        return

    setting, value = context.args[0].lower(), context.args[1]
    try:
        value = int(value)
        if setting == 'rate_limit':
            if 1 <= value <= 100:
                config.RATE_LIMIT_MESSAGES = value
                await update.message.reply_text(f'Rate limit set to {value} messages per {config.RATE_LIMIT_WINDOW} seconds')
            else:
                await update.message.reply_text('Rate limit must be between 1 and 100')
        elif setting == 'rate_window':
            if 11 <= value <= 3600:  # Between 1 seconds and 1 hour
                config.RATE_LIMIT_WINDOW = value
                await update.message.reply_text(f'Rate limit window set to {value} seconds')
            else:
                await update.message.reply_text('Rate window must be between 10 and 3600 seconds')
        elif setting == 'inactive_days':
            if 1 <= value <= 365:
                config.INACTIVE_DAYS_THRESHOLD = value
                await update.message.reply_text(f'Inactive threshold set to {value} days')
            else:
                await update.message.reply_text('Inactive days must be between 1 and 365')
        else:
            await update.message.reply_text('Invalid setting')
    except ValueError:
        await update.message.reply_text('Value must be a number')

async def toggle_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
    **kwargs
) -> None:
    """Toggle features on/off"""
    if len(context.args) != 2:
        await update.message.reply_text(
            'Usage: /toggle <feature> <on/off>\n'
            'Available features:\n'
            '• translation_en_to_zh - English to Chinese translation\n'
            '• translation_zh_to_en - Chinese to English translation'
        )
        return

    feature, state = context.args[0].lower(), context.args[1].lower()
    if feature == 'translation_en_to_zh':
        if state in ['on', 'off']:
            config.TRANSLATE_EN_TO_ZH = (state == 'on')
            await update.message.reply_text(f'Translation has been turned {state}')
        else:
            await update.message.reply_text('State must be "on" or "off"')
    elif feature == 'translation_zh_to_en':
        if state in ['on', 'off']:
            config.TRANSLATE_ZH_TO_EN = (state == 'on')
            await update.message.reply_text(f'Translation has been turned {state}')
        else:
            await update.message.reply_text('State must be "on" or "off"')
    else:
        await update.message.reply_text('Invalid feature')

async def print_database_command(
    update: Update, 
    context: CallbackContext, 
    config: BotConfig,
    db: DatabaseManager, 
    **kwargs
) -> None:
    """Print all database entries when the command /print_db is issued."""
    logger.info("Received /print_db command")
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return
    try:
        entries = await db.get_all_entries()
        if not entries:
            if update.effective_message:
                await update.effective_message.reply_text("No entries in the database.")
        else:
            entry_text = '\n'.join([f"User {e['user_id']} in Chat {e['chat_id']} - Last Active: {e['last_active']}" for e in entries])
            if update.effective_message:
                await update.effective_message.reply_text(f"*Database Entries:*\n{entry_text}", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error processing /print_db: {e}", exc_info=True)
        if update.effective_message:
            await update.effective_message.reply_text("Failed to fetch database entries.")

async def kick_inactive_members(
    db: DatabaseManager,
    config: BotConfig,
    context: CallbackContext
) -> None:
    """Kick inactive members from the group"""
    try:
        chat_id = context.bot_data.get('chat_id')
        if not chat_id:
            return

        inactive_users = await db.get_inactive_users(
            chat_id,
            config.INACTIVE_DAYS_THRESHOLD
        )
        
        for user_id in inactive_users:
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                await context.bot.unban_chat_member(chat_id, user_id)  # Unban so they can rejoin
                logger.info(f"Kicked inactive user {user_id} from chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to kick user {user_id}: {e}")
    except Exception as e:
        logger.error(f"Error in kick_inactive_members: {e}")

async def import_users_command(
    update: Update, 
    context: CallbackContext, 
    config: BotConfig,
    db: DatabaseManager
) -> None:
    """Handle /import_users [filename] command to import users from a file in csv directory."""
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /import_users [filename]")
        return

    filename = context.args[0]
    file_path = os.path.join('csv', filename)

    if not os.path.exists(file_path):
        await update.message.reply_text(f"File {filename} not found in csv directory.")
        return

    logger.info(f"Loading users from {file_path}")
    try:
        await db.import_users_from_file(file_path)
        await update.message.reply_text(f"Users imported successfully from {filename}.")
    except Exception as e:
        logger.error(f"Error during user import: {e}", exc_info=True)
        await update.message.reply_text(f"Failed to import users from {filename}.")

