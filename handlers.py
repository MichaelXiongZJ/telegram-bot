# --- handlers.py ---
"""
Message and command handlers with improved database interactions
"""
from telegram import Update
from telegram.ext import CallbackContext
import logging
from deep_translator import GoogleTranslator
import os
import re
from typing import List, Dict
from config import BotConfig
from database import DatabaseManager
from server_config import ServerConfigManager

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

def detect_language(text: str) -> str:
    """Detect if text is primarily Chinese or English"""
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    chinese_chars = len(chinese_char_pattern.findall(text))
    total_chars = len(text.replace(" ", ""))
    return 'zh' if chinese_chars / total_chars > 0.5 else 'en'

async def handle_message(
    update: Update,
    context: CallbackContext,
    db,
    config_manager,
    **kwargs
) -> None:
    """Handle regular messages with translation support"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    
    logger.info(f"Handling message from user {user_id} in chat {chat_id}")

    try:
        # Get chat-specific config
        chat_config = await config_manager.get_config(chat_id)
        
        if (chat_config['translate_zh_to_en'] or chat_config['translate_en_to_zh']) and text:
            logger.debug("Translation is enabled")
            
            detected_lang = detect_language(text)
            logger.info(f"Detected language: {detected_lang}")
            
            if detected_lang == 'zh' and chat_config['translate_zh_to_en']:
                translated = translator_zh_to_en.translate(text)
            elif detected_lang == 'en' and chat_config['translate_en_to_zh']:
                translated = translator_en_to_zh.translate(text)
            else:
                translated = None

            if translated and translated != text:
                await update.message.reply_text(translated)
                logger.info(f"Translated message sent: {translated}")
        
        # Update activity time
        logger.debug(f"Updating activity time for user {user_id}")
        await db.update_user_activity(user_id, chat_id)
        
    except Exception as e:
        logger.error(f"Error in handle_message: {e}", exc_info=True)

async def help_command(
    update: Update,
    context: CallbackContext,
    config: BotConfig,
    config_manager,
    **kwargs
) -> None:
    """Show help message with available commands"""
    chat_id = update.effective_chat.id
    try:
        chat_config = await config_manager.get_config(chat_id)
        
        # Basic settings info for all users
        help_text = (
            "*Settings*\n"
            f"Rate limit: {chat_config['rate_limit_messages']} messages per {chat_config['rate_limit_window']}s\n"
            f"Inactive days threshold: {chat_config['inactive_days_threshold']} days\n"
            f"*Translations:*\n"
            "/toggle\\_translation\\_en\\_to\\_zh - Toggle EN→ZH translation\n"
            "/toggle\\_translation\\_zh\\_to\\_en - Toggle ZH→EN translation\n"
            "Current Setting: "
            f"EN→ZH {'on' if chat_config['translate_en_to_zh'] else 'off'}, "
            f"ZH→EN {'on' if chat_config['translate_zh_to_en'] else 'off'}\n"
        )

        # Add admin commands if user is admin
        if await is_admin(update, context, config):
            help_text += (
                "*Admin Commands*\n"
                "/configure rate\\_limit <number> - Set message rate limit\n"
                "/configure rate\\_window <seconds> - Set time window\n"
                "/import\\_user [filename] - Import member to database\n"
                "/print\\_db - Print the member database."
            )

        await update.message.reply_text(help_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("Error showing help. Please try again later.")

async def handle_new_members(
    update: Update,
    context: CallbackContext,
    db,
    **kwargs
) -> None:
    """Handle new members joining the chat"""
    if not update.message.new_chat_members:
        return
    chat_id = update.effective_chat.id
    for member in update.message.new_chat_members:
        if not member.is_bot:
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
    config_manager,
    **kwargs
) -> None:
    """Handle bot configuration"""
    chat_id = update.effective_chat.id
    
    if not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            'Usage: /configure <setting> <value>\n'
            'Available commands:\n'
            '• rate_limit - Messages per time window\n'
            '• rate_window - Time window in seconds\n'
            '• inactive_days - Days before user is considered inactive'
        )
        return

    setting, value = context.args[0].lower(), context.args[1]
    try:
        value = int(value)
        current_config = await config_manager.get_config(chat_id)
        
        if setting == 'rate_limit':
            if 1 <= value <= 100:
                current_config['rate_limit_messages'] = value
                await config_manager.update_config(chat_id, current_config)
                await update.message.reply_text(f'Rate limit set to {value} messages per {current_config["rate_limit_window"]} seconds')
            else:
                await update.message.reply_text('Rate limit must be between 1 and 100')
        elif setting == 'rate_window':
            if 1 <= value <= 3600:
                current_config['rate_limit_window'] = value
                await config_manager.update_config(chat_id, current_config)
                await update.message.reply_text(f'Rate limit window set to {value} seconds')
            else:
                await update.message.reply_text('Rate window must be between 10 and 3600 seconds')
        elif setting == 'inactive_days':
            if 1 <= value <= 365:
                current_config['inactive_days_threshold'] = value
                await config_manager.update_config(chat_id, current_config)
                await update.message.reply_text(f'Inactive threshold set to {value} days')
            else:
                await update.message.reply_text('Inactive days must be between 1 and 365')
        else:
            await update.message.reply_text('Invalid setting')
    except ValueError:
        await update.message.reply_text('Value must be a number')

async def toggle_translation_en_to_zh(
    update: Update,
    context: CallbackContext,
    config_manager,
    **kwargs
) -> None:
    """Toggle English to Chinese translation"""
    chat_id = update.effective_chat.id
    try:
        current_config = await config_manager.get_config(chat_id)
        new_state = not current_config['translate_en_to_zh']
        current_config['translate_en_to_zh'] = new_state
        await config_manager.update_config(chat_id, current_config)
        state_str = 'enabled' if new_state else 'disabled'
        await update.message.reply_text(f'English to Chinese translation has been {state_str}')
    except Exception as e:
        logger.error(f"Error toggling EN→ZH translation: {e}")
        await update.message.reply_text("Failed to toggle translation setting")

async def toggle_translation_zh_to_en(
    update: Update,
    context: CallbackContext,
    config_manager,
    **kwargs
) -> None:
    """Toggle Chinese to English translation"""
    chat_id = update.effective_chat.id
    try:
        current_config = await config_manager.get_config(chat_id)
        new_state = not current_config['translate_zh_to_en']
        current_config['translate_zh_to_en'] = new_state
        await config_manager.update_config(chat_id, current_config)
        state_str = 'enabled' if new_state else 'disabled'
        await update.message.reply_text(f'Chinese to English translation has been {state_str}')
    except Exception as e:
        logger.error(f"Error toggling ZH→EN translation: {e}")
        await update.message.reply_text("Failed to toggle translation setting")

async def print_database_command(
    update: Update, 
    context: CallbackContext,
    config: BotConfig,
    db: DatabaseManager,
    config_manager: ServerConfigManager,
    **kwargs
) -> None:
    """Print database information based on context and user permissions"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Check if it's the owner in DM
    is_owner = user_id == config.BOT_OWNER_ID
    is_private = chat_type == 'private'
    
    if not (is_owner and is_private) and not await is_admin(update, context, config):
        await update.message.reply_text('This command is only available to administrators.')
        return

    try:
        if is_owner and is_private:
            # Owner in DM - show all chats
            chat_ids = await db.get_all_chat_ids()
            for chat_id in chat_ids:
                try:
                    chat = await context.bot.get_chat(chat_id)
                    chat_title = chat.title or f"Chat {chat_id}"
                    
                    # Get chat config
                    chat_config = await config_manager.get_config(chat_id)
                    stats = await db.get_chat_statistics(chat_id)
                    users = await db.get_chat_user_activity(chat_id, limit=10)  # Top 10 active users
                    
                    # Format message for each chat
                    message = (
                        f"\n*{chat_title}*\n"
                        f"Chat ID: `{chat_id}`\n"
                        "\n*Configuration:*\n"
                        f"• Rate Limit: {chat_config['rate_limit_messages']} per {chat_config['rate_limit_window']}s\n"
                        f"• Translations: EN→ZH: {'on' if chat_config['translate_en_to_zh'] else 'off'}, "
                        f"ZH→EN: {'on' if chat_config['translate_zh_to_en'] else 'off'}\n"
                        f"• Inactive threshold: {chat_config['inactive_days_threshold']} days\n"
                        "\n*Statistics:*\n"
                        f"• Total Users: {stats['total_users']}\n"
                        f"• Total Messages: {stats['total_messages']}\n"
                        f"• Avg Messages/User: {stats['avg_messages_per_user']:.1f}\n"
                        "\n*Recent Active Users:*\n"
                    )
                    
                    # Add user activity information
                    for user in users:
                        try:
                            member = await context.bot.get_chat_member(chat_id, user['user_id'])
                            username = member.user.username or member.user.first_name
                            message += (
                                f"• {username} "
                                f"(msgs: {user['messages_count']}, "
                                f"last: {user['last_active'].split('.')[0]})\n"
                            )
                        except Exception:
                            message += f"• User {user['user_id']} (not found)\n"
                    
                    await update.message.reply_text(message, parse_mode='Markdown')
                    
                except Exception as e:
                    logger.error(f"Error processing chat {chat_id}: {e}")
                    await update.message.reply_text(f"Error processing chat {chat_id}")
        
        else:
            # Admin in group chat - show current chat only
            chat_config = await config_manager.get_config(chat_id)
            stats = await db.get_chat_statistics(chat_id)
            users = await db.get_chat_user_activity(chat_id)
            
            config_text = (
                "*Current Configuration:*\n"
                f"• Rate Limit: {chat_config['rate_limit_messages']} messages per {chat_config['rate_limit_window']}s\n"
                f"• Inactive threshold: {chat_config['inactive_days_threshold']} days\n"
                f"• EN→ZH Translation: {'on' if chat_config['translate_en_to_zh'] else 'off'}\n"
                f"• ZH→EN Translation: {'on' if chat_config['translate_zh_to_en'] else 'off'}\n"
                "\n*Statistics:*\n"
                f"• Total Users: {stats['total_users']}\n"
                f"• Total Messages: {stats['total_messages']}\n"
                f"• Average Messages/User: {stats['avg_messages_per_user']:.1f}\n"
                "\n*User Activity:*\n"
            )
            
            await update.message.reply_text(config_text, parse_mode='Markdown')
            
            # Send user activity in chunks to avoid message length limits
            user_text = ""
            for user in users:
                try:
                    member = await context.bot.get_chat_member(chat_id, user['user_id'])
                    username = member.user.username or member.user.first_name
                    user_line = (
                        f"• {username} "
                        f"(msgs: {user['messages_count']}, "
                        f"last: {user['last_active'].split('.')[0]})\n"
                    )
                    
                    if len(user_text) + len(user_line) > 3000:  # Telegram message limit safety
                        await update.message.reply_text(user_text, parse_mode='Markdown')
                        user_text = user_line
                    else:
                        user_text += user_line
                        
                except Exception:
                    continue
            
            if user_text:
                await update.message.reply_text(user_text, parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"Error processing print_db: {e}", exc_info=True)
        await update.message.reply_text("An error occurred while fetching database information.")

async def import_users_command(
    update: Update, 
    context: CallbackContext,
    config: BotConfig,
    db,
    **kwargs
) -> None:
    """Handle /import_users command"""
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

    try:
        stats = await db.import_users_from_file(
            file_path,
            default_chat_id=update.effective_chat.id
        )
        
        # Send detailed response
        response = (
            f"Import completed:\n"
            f"✅ Successful: {stats['success']}\n"
            f"❌ Errors: {stats['errors']}\n"
            f"📝 Total processed: {stats['processed']}"
        )
        
        if stats['errors'] > 0:
            response += "\n\nError details:\n" + "\n".join(stats['error_details'][:5])
            if len(stats['error_details']) > 5:
                response += f"\n...and {len(stats['error_details']) - 5} more errors"
                
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error during user import: {e}", exc_info=True)
        await update.message.reply_text(f"Failed to import users from {filename}: {str(e)}")

async def kick_inactive_members(
    db,
    context: CallbackContext
) -> None:
    """Kick inactive members from the group"""
    try:
        chat_id = context.bot_data.get('chat_id')
        if not chat_id:
            return

        # Get chat-specific config
        config_manager = context.bot_data['config_manager']
        chat_config = await config_manager.get_config(chat_id)
        
        inactive_users = await db.get_inactive_users(
            chat_id,
            chat_config['inactive_days_threshold']
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