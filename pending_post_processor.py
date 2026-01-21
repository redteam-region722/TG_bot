import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database import db
import config

logger = logging.getLogger(__name__)

class PendingPostProcessor:
    def __init__(self, bot):
        self.bot = bot
    
    def get_channel_id(self, server_id):
        """Get channel ID for a server"""
        if not config.CHANNEL_IDS:
            return None
        
        if server_id is None:
            logger.error("server_id is None when trying to get channel ID")
            return None
        
        try:
            server_index = server_id - 1
            if 0 <= server_index < len(config.CHANNEL_IDS):
                channel_id = config.CHANNEL_IDS[server_index].strip()
                try:
                    # Try to convert to int if it's numeric
                    if channel_id.lstrip('-').isdigit():
                        return int(channel_id)
                    # If it's a username without @, add it
                    elif not channel_id.startswith('@') and not channel_id.startswith('-'):
                        return f"@{channel_id}"
                    else:
                        return channel_id
                except:
                    return channel_id
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid server_id {server_id}: {e}")
            return None
        
        return None
    
    async def send_to_channel(self, server_id, message_text, photo_id=None, reply_markup=None):
        """Send post to the appropriate channel"""
        channel_id = self.get_channel_id(server_id)
        
        if not channel_id:
            logger.warning(f"No channel ID configured for server {server_id}")
            return None
        
        try:
            if photo_id:
                result = await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_id,
                    caption=message_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                result = await self.bot.send_message(
                    chat_id=channel_id,
                    text=message_text,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            return result.message_id if result else None
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            # If invalid URL, try again with button (Telegram might accept it)
            if 'invalid' in error_msg_lower and 'url' in error_msg_lower:
                logger.warning(f"Invalid URL in button, retrying with button: {error_msg}")
                try:
                    if photo_id:
                        result = await self.bot.send_photo(
                            chat_id=channel_id,
                            photo=photo_id,
                            caption=message_text,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    else:
                        result = await self.bot.send_message(
                            chat_id=channel_id,
                            text=message_text,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    logger.info(f"✅ Sent with button (may show error on click): {result.message_id}")
                    return result.message_id if result else None
                except Exception as retry_error:
                    # If still fails, send without button
                    logger.warning(f"Still failed with button, sending without: {retry_error}")
                    if photo_id:
                        result = await self.bot.send_photo(
                            chat_id=channel_id,
                            photo=photo_id,
                            caption=message_text,
                            parse_mode='HTML'
                        )
                    else:
                        result = await self.bot.send_message(
                            chat_id=channel_id,
                            text=message_text,
                            parse_mode='HTML'
                        )
                    logger.info(f"✅ Sent without button: {result.message_id}")
                    return result.message_id if result else None
            
            logger.error(f"Failed to send to channel {channel_id} for server {server_id}: {error_msg}")
            
            # Provide more helpful error message
            if "Chat not found" in error_msg or "chat not found" in error_msg_lower:
                raise Exception(
                    f"Channel not found. Please check:\n"
                    f"• Channel ID '{channel_id}' is correct\n"
                    f"• Bot is added to the channel as administrator\n"
                    f"• For usernames, use format: @channelname\n"
                    f"• For numeric IDs, use format: -1001234567890"
                )
            else:
                raise
    
    async def process_pending_posts(self):
        """Process all pending posts that are ready to be sent"""
        try:
            pending_posts = db.get_pending_posts_ready()
            
            if not pending_posts:
                return
            
            logger.info(f"Processing {len(pending_posts)} pending posts")
            
            for post in pending_posts:
                try:
                    await self.send_pending_post(post)
                except Exception as e:
                    logger.error(f"Error sending pending post {post['_id']}: {e}")
        
        except Exception as e:
            logger.error(f"Error processing pending posts: {e}")
    
    async def send_pending_post(self, post):
        """Send a single pending post"""
        server_id = post['server_id']
        user_id = post['user_id']
        message_text = post.get('message_text', '')
        photo_id = post.get('photo_id')
        
        # Get server config
        config_data = db.get_server_config(server_id)
        footer = config_data.get('footer_text', '')
        
        # Add footer if exists
        if footer:
            full_content = f"{message_text}\n\n{footer}" if message_text else footer
        else:
            full_content = message_text
        
        # Create buttons if configured - don't validate URL, just add if text and URL exist
        buttons = []
        
        btn1_text = config_data.get('button1_text', '').strip() if config_data.get('button1_text') else ''
        btn1_url = config_data.get('button1_url', '').strip() if config_data.get('button1_url') else ''
        
        if btn1_text and btn1_url:
            try:
                buttons.append([InlineKeyboardButton(btn1_text, url=btn1_url)])
                logger.info(f"Added button1: '{btn1_text}' -> '{btn1_url}'")
            except Exception as e:
                logger.warning(f"Failed to create button1: {e}")
        
        btn2_text = config_data.get('button2_text', '').strip() if config_data.get('button2_text') else ''
        btn2_url = config_data.get('button2_url', '').strip() if config_data.get('button2_url') else ''
        
        if btn2_text and btn2_url:
            try:
                buttons.append([InlineKeyboardButton(btn2_text, url=btn2_url)])
                logger.info(f"Added button2: '{btn2_text}' -> '{btn2_url}'")
            except Exception as e:
                logger.warning(f"Failed to create button2: {e}")
        
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        
        # Send to actual channel
        channel_message_id = None
        try:
            channel_message_id = await self.send_to_channel(
                server_id, 
                full_content, 
                photo_id=photo_id, 
                reply_markup=reply_markup
            )
            logger.info(f"Posted to channel for server {server_id}, message_id: {channel_message_id}")
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            # If invalid URL error, try to send with button anyway
            if 'invalid' in error_msg_lower and 'url' in error_msg_lower:
                logger.warning(f"Invalid URL in button, but trying to send with button anyway: {error_msg}")
                try:
                    channel_message_id = await self.send_to_channel(
                        server_id, 
                        full_content, 
                        photo_id=photo_id, 
                        reply_markup=reply_markup
                    )
                    logger.info(f"✅ Sent with button (may show error on click): {channel_message_id}")
                except Exception as retry_error:
                    # If still fails, send without button as last resort
                    logger.warning(f"Still failed with button, sending without: {retry_error}")
                    try:
                        channel_message_id = await self.send_to_channel(
                            server_id, 
                            full_content, 
                            photo_id=photo_id, 
                            reply_markup=None
                        )
                        logger.info(f"✅ Sent without button: {channel_message_id}")
                    except Exception as final_error:
                        logger.error(f"Failed to send post to channel for server {server_id}: {final_error}")
                        raise
            else:
                logger.error(f"Failed to send post to channel for server {server_id}: {e}")
                raise
        
        # Notify the user who created the post
        try:
            post_type = "photo post" if photo_id else "post"
            content_preview = message_text[:100] if message_text else "[Photo only]"
            
            await self.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>Pending {post_type.title()} Sent!</b>\n\n"
                    f"Your {post_type} to Server {server_id} has been published.\n\n"
                    f"<b>Content:</b>\n{content_preview}{'...' if len(message_text) > 100 else ''}"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Could not notify user {user_id}: {e}")
        
        # Save post record with channel message ID
        db.save_post(server_id, user_id, message_text, channel_message_id=channel_message_id, photo_id=photo_id)
        
        # Mark as sent
        db.mark_pending_post_sent(post['_id'])
        
        logger.info(f"Sent pending post {post['_id']} to Server {server_id} (channel message_id: {channel_message_id})")
