# --- handlers.py ---
"""
Message and command handlers with professional language detection
"""
from telegram import Update
from telegram.ext import CallbackContext
from datetime import datetime
import logging
from deep_translator import GoogleTranslator
import re
from database import DatabaseManager
from config import BotConfig

logger = logging.getLogger(__name__)

# Initialize language detection
try:
    import spacy
    logger.info("Loading spaCy language model...")
    nlp = spacy.load("en_core_web_sm")
    
    def detect_english(text: str) -> bool:
        """Use spaCy for language detection"""
        try:
            # Use spaCy to analyze text
            doc = nlp(text[:100])  # Process first 100 chars for speed
            
            # Count English-like words and total words
            english_words = sum(1 for token in doc if token.is_alpha and token.lang_ == 'en')
            total_words = sum(1 for token in doc if token.is_alpha)
            
            # Text is considered English if more than 70% of words are English
            if total_words > 0:
                ratio = english_words / total_words
                logger.debug(f"English word ratio: {ratio}")
                return ratio > 0.7
            return False
            
        except Exception as e:
            logger.error(f"spaCy language detection error: {e}")
            return False
    logger.info("spaCy language detection initialized")

except ImportError:
    logger.warning("No language detection available, using basic detection")
    def detect_english(text: str) -> bool:
        """Fallback basic English detection"""
        english_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 
                        'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 
                        'do', 'at', 'this', 'but', 'his', 'by', 'from', 'they'}
        words = set(text.lower().split())
        return len(words.intersection(english_words)) >= 2

# Initialize translator
logger.info("Initializing translator...")
translator = None
try:
    translator = GoogleTranslator(source='auto', target='zh-CN')
    logger.info("Translator initialized successfully")
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

async def handle_message(
    update: Update,
    context: CallbackContext,
    db: DatabaseManager,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle regular messages"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"Handling message from user {user_id} in chat {chat_id}: {update.message.text}")
    
    try:
        # First try translation if enabled
        if config.TRANSLATION_ENABLED:
            logger.debug("Translation is enabled")
            if translator is None:
                logger.warning("Translator not initialized, skipping translation")
            else:
                text = update.message.text
                logger.debug(f"Processing text for translation: {text[:50]}...")
                
                # Use professional language detection
                if len(text.split()) >= 2:
                    logger.debug("Checking if text is English")
                    if detect_english(text):
                        logger.info("English text detected, translating")
                        try:
                            translated = translator.translate(text)
                            if translated and translated != text:
                                await update.message.reply_text(f'Translation: {translated}')
                                logger.info(f"Translated: {text[:50]} -> {translated[:50]}")
                        except Exception as e:
                            logger.error(f"Translation failed: {e}", exc_info=True)
                    else:
                        logger.debug("Text is not English, skipping translation")

        # Then update activity time
        logger.debug(f"Updating activity time for user {user_id}")
        await db.update_user_activity(user_id, chat_id)
        logger.debug("Activity time updated successfully")
        
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
        "*Kuma's Group Management Bot*\n\n"
        
        "*Commands:*\n"
        "/help - Show this help message\n"
        "/configure <setting> <value> - Configure bot settings (admin only)\n"
        "  • rate_limit <number> - Messages per minute limit\n"
        "  • inactive_days <number> - Days before user is considered inactive\n"
        "  • Example: `/configure rate_limit 5`\n"
        "/toggle <feature> - Toggle features on/off (admin only)\n"
        "  • translation - English to Chinese translation\n"
        "  • Example: `/toggle translation on`\n\n"
        
        "*Current Settings:*\n"
        f"• Rate limit: {config.RATE_LIMIT_MESSAGES} messages per {config.RATE_LIMIT_WINDOW} seconds\n"
        f"• Inactive threshold: {config.INACTIVE_DAYS_THRESHOLD} days\n"
        f"• Translation: {'Enabled' if config.TRANSLATION_ENABLED else 'Disabled'}\n"
    )
    
    try:
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending help: {e}")
        await update.message.reply_text(help_text)

async def configure_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
    **kwargs
) -> None:
    """Handle bot configuration"""
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            'Usage: /configure <setting> <value>\n'
            'Available settings:\n'
            '• rate_limit - Messages per minute\n'
            '• inactive_days - Days before user is considered inactive'
        )
        return

    setting, value = context.args[0].lower(), context.args[1]
    try:
        value = int(value)
        if setting == 'rate_limit':
            if 1 <= value <= 100:
                config.RATE_LIMIT_MESSAGES = value
                await update.message.reply_text(f'Rate limit set to {value} messages per minute')
            else:
                await update.message.reply_text('Rate limit must be between 1 and 100')
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
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            'Usage: /toggle <feature> <on/off>\n'
            'Available features:\n'
            '• translation - English to Chinese translation'
        )
        return

    feature, state = context.args[0].lower(), context.args[1].lower()
    if feature == 'translation':
        if state in ['on', 'off']:
            config.TRANSLATION_ENABLED = (state == 'on')
            await update.message.reply_text(f'Translation has been turned {state}')
        else:
            await update.message.reply_text('State must be "on" or "off"')
    else:
        await update.message.reply_text('Invalid feature')

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