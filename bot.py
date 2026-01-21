import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from datetime import datetime

import config
from database import db
from keyboards import *

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_MANAGER_PASSWORD = 0
WAITING_POST_TIME, WAITING_POST_CONFIRMATION = range(1, 3)

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self._setup_handlers()
    
    def _is_authorized(self, user_id):
        """Check if user is authorized (admin or manager)"""
        return user_id == config.ADMIN_ID or user_id in config.MANAGER_IDS
    
    def _get_channel_id(self, server_id):
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
    
    async def _send_post_to_channel(self, server_id, message_text, photo_id=None, context=None):
        """Send post to the appropriate channel with footer and buttons"""
        channel_id = self._get_channel_id(server_id)
        
        if not channel_id:
            logger.warning(f"No channel ID configured for server {server_id}")
            return None
        
        # Get server config
        config_data = db.get_server_config(server_id)
        footer = config_data.get('footer_text', '')
        
        # Add footer if exists
        if footer:
            full_content = f"{message_text}\n\n{footer}" if message_text else footer
        else:
            full_content = message_text
        
        # Create buttons if configured - don't validate URL, just add if text and URL exist
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
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
        
        # Use context.bot if available, otherwise use application.bot
        bot = context.bot if context else self.application.bot
        
        # Debug logging
        if reply_markup:
            logger.info(f"📤 Sending to channel {channel_id} with {len(reply_markup.inline_keyboard)} button row(s)")
        else:
            logger.info(f"📤 Sending to channel {channel_id} WITHOUT buttons")
        
        try:
            if photo_id:
                result = await bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_id,
                    caption=full_content,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                result = await bot.send_message(
                    chat_id=channel_id,
                    text=full_content,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            logger.info(f"✅ Successfully posted to channel {channel_id} for server {server_id}, message_id: {result.message_id}")
            return result.message_id if result else None
        except Exception as e:
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            # If invalid URL error, try to send with button anyway (Telegram might accept it)
            if 'invalid' in error_msg_lower and 'url' in error_msg_lower:
                logger.warning(f"Invalid URL in button, but trying to send with button anyway: {error_msg}")
                try:
                    # Try again with the same button - sometimes Telegram accepts it
                    if photo_id:
                        result = await bot.send_photo(
                            chat_id=channel_id,
                            photo=photo_id,
                            caption=full_content,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    else:
                        result = await bot.send_message(
                            chat_id=channel_id,
                            text=full_content,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    logger.info(f"✅ Sent with button (may show error on click): {result.message_id}")
                    return result.message_id if result else None
                except Exception as retry_error:
                    # If still fails, send without button as last resort
                    logger.warning(f"Still failed with button, sending without: {retry_error}")
                    if photo_id:
                        result = await bot.send_photo(
                            chat_id=channel_id,
                            photo=photo_id,
                            caption=full_content,
                            parse_mode='HTML'
                        )
                    else:
                        result = await bot.send_message(
                            chat_id=channel_id,
                            text=full_content,
                            parse_mode='HTML'
                        )
                    logger.info(f"✅ Sent without button: {result.message_id}")
                    return result.message_id if result else None
            
            # Provide more helpful error message for other errors
            logger.error(f"Failed to send post to channel {channel_id} for server {server_id}: {error_msg}")
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
    
    async def _check_authorization(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check authorization and send access denied if not authorized"""
        user = update.effective_user
        if not self._is_authorized(user.id):
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "You are not authorized to use this bot.",
                parse_mode='HTML'
            )
            logger.warning(f"Unauthorized access attempt by user {user.id} (@{user.username})")
            return False
        return True
    
    def _setup_handlers(self):
        """Setup all command and message handlers"""
        
        # Start command
        self.application.add_handler(CommandHandler("start", self.start_command))
        
        # User commands
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        
        # Manager commands
        self.application.add_handler(CommandHandler("manager", self.manager_login_command))
        self.application.add_handler(CommandHandler("logout", self.logout_command))
        self.application.add_handler(CommandHandler("pending", self.pending_posts_command))
        self.application.add_handler(CommandHandler("post", self.post_to_server_menu))
        self.application.add_handler(CommandHandler("status", self.manager_stats))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("status", self.stats_command))
        self.application.add_handler(CommandHandler("setting", self.server_config_menu))
        
        # Manager password conversation
        manager_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.TEXT & filters.Regex("^/manager"), self.manager_login_command)],
            states={
                WAITING_MANAGER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.receive_manager_password)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_command)]
        )
        self.application.add_handler(manager_conv)
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"), self.help_command))
        self.application.add_handler(MessageHandler(filters.Regex("^⚙️ Settings$"), self.settings_command))
        
        # Manager message handlers - removed, using slash commands instead
        
        # Photo handler (must be before text handler)
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # General message handler for waiting states (must be last)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_input
        ))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        # Add user to database
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        # Determine user role
        if user.id == config.ADMIN_ID:
            # Admin gets direct access
            keyboard = get_admin_menu_keyboard()
            
            welcome_message = (
                f"👋 <b>Welcome {user.first_name}!</b>\n\n"
                f"Role: <b>Administrator</b>\n\n"
                "Use the menu below to manage the bot."
            )
            
            await update.message.reply_text(
                welcome_message,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            
        elif user.id in config.MANAGER_IDS:
            # Manager needs to authenticate first
            if db.is_manager_authenticated(user.id):
                # Already authenticated, show manager menu
                keyboard = get_manager_menu_keyboard()
                
                welcome_message = (
                    f"👋 <b>Welcome back {user.first_name}!</b>\n\n"
                    f"Role: <b>Manager</b>\n\n"
                    "Use the menu below to manage posts."
                )
                
                await update.message.reply_text(
                    welcome_message,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            else:
                # Not authenticated, ask for password directly (NO MENU)
                context.user_data['waiting_manager_password'] = True
                context.user_data['password_retry_count'] = 0
                
                await update.message.reply_text(
                    f"👋 <b>Welcome {user.first_name}!</b>\n\n"
                    "🔐 <b>Manager Authentication</b>\n\n"
                    "Please enter your password:\n\n"
                    "Type /cancel to cancel.",
                    parse_mode='HTML'
                )
        else:
            # Unauthorized user - no menu, just access denied
            pass
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        user = update.effective_user
        
        if user.id == config.ADMIN_ID:
            help_text = (
                "<b>📖 Admin Help & Commands</b>\n\n"
                "<b>Admin Commands:</b>\n"
                "/start - Start the bot\n"
                "/admin - Access admin panel\n"
                "/broadcast - Send message to all users\n"
                "/stats - View statistics\n"
                "/help - Show this help message\n\n"
                "<b>Manager Commands:</b>\n"
                "/manager - Access manager panel\n"
                "/logout - Logout from manager mode\n\n"
                "You have full access to all features."
            )
        elif user.id in config.MANAGER_IDS:
            help_text = (
                "<b>📖 Manager Help & Commands</b>\n\n"
                "<b>Manager Commands:</b>\n"
                "/start - Start the bot\n"
                "/manager - Login as manager\n"
                "/logout - Logout from manager mode\n"
                "/help - Show this help message\n\n"
                "Use the manager panel to manage the system."
            )
        else:
            help_text = (
                "<b>📖 Help & Commands</b>\n\n"
                "<b>User Commands:</b>\n"
                "/start - Start the bot\n"
                "/settings - Manage your settings\n"
                "/help - Show this help message\n\n"
                "Need more help? Contact the administrator."
            )
        
        await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        user = update.effective_user
        
        settings_text = (
            "⚙️ <b>Settings</b>\n\n"
            "No settings available at the moment."
        )
        
        await update.message.reply_text(
            settings_text,
            parse_mode='HTML'
        )
    
    async def manager_login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manager login"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if user.id not in config.MANAGER_IDS and user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ You don't have manager access.")
            return ConversationHandler.END
        
        # Check if already authenticated
        if db.is_manager_authenticated(user.id):
            await update.message.reply_text(
                "✅ You're already logged in as a manager!",
                reply_markup=get_manager_menu_keyboard()
            )
            return ConversationHandler.END
        
        # Ask for password directly
        context.user_data['waiting_manager_password'] = True
        context.user_data['password_retry_count'] = 0
        
        await update.message.reply_text(
            "🔐 <b>Manager Login</b>\n\n"
            "Please enter your password:\n\n"
            "Type /cancel to cancel.",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    async def receive_manager_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receive and verify manager password"""
        user = update.effective_user
        password = update.message.text
        
        # Delete the password message for security
        await update.message.delete()
        
        if db.authenticate_manager(user.id, password):
            await context.bot.send_message(
                chat_id=user.id,
                text="✅ <b>Login Successful!</b>\n\nWelcome to the Manager Panel.",
                parse_mode='HTML',
                reply_markup=get_manager_menu_keyboard()
            )
            return ConversationHandler.END
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text="❌ <b>Invalid Password</b>\n\nPlease try again or type /cancel.",
                parse_mode='HTML'
            )
            return WAITING_MANAGER_PASSWORD
    
    async def logout_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle manager logout"""
        user = update.effective_user
        db.logout_manager(user.id)
        
        await update.message.reply_text(
            "👋 <b>Logged Out</b>\n\nYou've been logged out from manager mode.",
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
    
    async def pending_posts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending posts for manager"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if not db.is_manager_authenticated(user.id) and user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ Please login as a manager first. Use /manager")
            return
        
        # Get all pending posts for this manager
        all_pending = []
        for server_id in [1, 2, 3]:
            pending = db.get_pending_posts_by_server(server_id)
            # Filter by user if not admin
            if user.id != config.ADMIN_ID:
                pending = [p for p in pending if p['user_id'] == user.id]
            all_pending.extend(pending)
        
        if not all_pending:
            await update.message.reply_text(
                "📋 <b>Pending Posts</b>\n\n"
                "You have no pending posts scheduled.\n\n"
                "All your posts have been published!",
                parse_mode='HTML'
            )
            return
        
        # Sort by scheduled time
        all_pending.sort(key=lambda x: x['scheduled_time'])
        
        # Create message with buttons
        import pytz
        from datetime import datetime
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.utcnow()
        
        message_text = f"📋 <b>Pending Posts ({len(all_pending)})</b>\n\n"
        buttons = []
        
        for idx, post in enumerate(all_pending, 1):
            server_id = post['server_id']
            scheduled_time = post['scheduled_time']
            scheduled_ist = scheduled_time.replace(tzinfo=pytz.utc).astimezone(ist)
            scheduled_str = scheduled_ist.strftime('%H:%M IST')
            
            # Calculate time until post
            time_diff = scheduled_time - current_time
            minutes_until = max(0, int(time_diff.total_seconds() / 60))
            hours_until = minutes_until // 60
            mins_remaining = minutes_until % 60
            
            if hours_until > 0:
                time_until_str = f"{hours_until}h {mins_remaining}m"
            else:
                time_until_str = f"{minutes_until}m"
            
            # Get content preview
            content = post.get('message_text', '')
            has_photo = post.get('photo_id') is not None
            content_type = "📸 Photo" if has_photo else "📝 Text"
            content_preview = content[:30] if content else "[No text]"
            
            message_text += (
                f"<b>{idx}. Server {server_id}</b> - {content_type}\n"
                f"⏰ {scheduled_str} (in {time_until_str})\n"
                f"💬 {content_preview}{'...' if len(content) > 30 else ''}\n\n"
            )
            
            # Add delete button
            buttons.append([
                InlineKeyboardButton(
                    f"🗑️ Delete Post #{idx}",
                    callback_data=f"delete_pending_{post['_id']}"
                )
            ])
        
        message_text += "Click a button below to delete a scheduled post:"
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        await update.message.reply_text(
            message_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    
    async def send_announcement_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Prompt for announcement (Manager)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if not db.is_manager_authenticated(user.id) and user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ Please login as a manager first. Use /manager")
            return
        
        # Check if this is the announcement message or the prompt
        if context.user_data.get('waiting_announcement'):
            # This is the message to send
            message = update.message.text
            
            # Send "sending..." message
            status_msg = await update.message.reply_text("📤 Sending announcement...")
            
            users = db.get_all_active_users()
            
            success_count = 0
            failed_count = 0
            
            for user_data in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_data['user_id'],
                        text=f"📢 <b>Announcement</b>\n\n{message}",
                        parse_mode='HTML'
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send to user {user_data['user_id']}: {e}")
                    failed_count += 1
            
            # Save announcement
            db.save_announcement(message, user.id)
            
            # Clear flag
            context.user_data['waiting_announcement'] = False
            
            # Delete status message
            await status_msg.delete()
            
            # Send completion alert
            await update.message.reply_text(
                f"✅ <b>Announcement Sent!</b>\n\n"
                f"📊 <b>Results:</b>\n"
                f"✅ Successfully sent: {success_count}\n"
                f"❌ Failed: {failed_count}\n\n"
                f"💬 <b>Message:</b>\n{message[:100]}{'...' if len(message) > 100 else ''}",
                parse_mode='HTML'
            )
        else:
            # This is the prompt
            await update.message.reply_text(
                "📢 <b>Send Announcement</b>\n\n"
                "Type your announcement message below.\n"
                "It will be sent to all active users.\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            context.user_data['waiting_announcement'] = True
    
    async def manager_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show statistics (Manager)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if not db.is_manager_authenticated(user.id) and user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ Please login as a manager first. Use /manager")
            return
        
        # Get post statistics
        total_posts = db.posts.count_documents({})
        pending_posts = db.pending_posts.count_documents({'status': 'pending'})
        
        # Get posts by server
        server_stats = []
        for server_id in [1, 2, 3]:
            server_posts = db.posts.count_documents({'server_id': server_id})
            server_pending = db.pending_posts.count_documents({'server_id': server_id, 'status': 'pending'})
            server_stats.append(f"Server {server_id}: {server_posts} posted, {server_pending} pending")
        
        stats_text = (
            "📊 <b>Statistics</b>\n\n"
            f"<b>📤 Post Statistics:</b>\n"
            f"✅ Total Posts: {total_posts}\n"
            f"⏳ Pending Posts: {pending_posts}\n\n"
            f"<b>By Server:</b>\n"
            + "\n".join(server_stats)
        )
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin command"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ You don't have admin access.")
            return
        
        await update.message.reply_text(
            "👑 <b>Admin Panel</b>\n\n"
            "Welcome to the admin panel!",
            parse_mode='HTML',
            reply_markup=get_admin_menu_keyboard()
        )
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users (Admin)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ You don't have admin access.")
            return
        
        # Check if this is the broadcast message or the command
        if context.user_data.get('waiting_broadcast'):
            # This is the message to broadcast
            message = update.message.text
            
            # Send "sending..." message
            status_msg = await update.message.reply_text("📤 Sending broadcast message...")
            
            users = db.get_all_active_users()
            
            success_count = 0
            failed_count = 0
            
            for user_data in users:
                try:
                    await context.bot.send_message(
                        chat_id=user_data['user_id'],
                        text=f"📢 <b>Announcement</b>\n\n{message}",
                        parse_mode='HTML'
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send to user {user_data['user_id']}: {e}")
                    failed_count += 1
            
            # Save announcement
            db.save_announcement(message, user.id)
            
            # Clear flag
            context.user_data['waiting_broadcast'] = False
            
            # Delete status message
            await status_msg.delete()
            
            # Send completion alert
            await update.message.reply_text(
                f"✅ <b>Broadcast Complete!</b>\n\n"
                f"📊 <b>Results:</b>\n"
                f"✅ Successfully sent: {success_count}\n"
                f"❌ Failed: {failed_count}\n\n"
                f"💬 <b>Message:</b>\n{message[:100]}{'...' if len(message) > 100 else ''}",
                parse_mode='HTML'
            )
        else:
            # This is the command, prompt for message
            await update.message.reply_text(
                "📢 <b>Broadcast Message</b>\n\n"
                "Type your message below to send it to all users.\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            context.user_data['waiting_broadcast'] = True
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show full statistics (Admin)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ You don't have admin access.")
            return
        
        # Get overall statistics
        total_posts = db.posts.count_documents({})
        total_pending = db.pending_posts.count_documents({'status': 'pending'})
        
        stats_text = (
            "📊 <b>Full Statistics</b>\n\n"
            f"📤 <b>Total Posts:</b> {total_posts}\n"
            f"⏳ <b>Total Pending:</b> {total_pending}\n"
            f"👔 <b>Managers:</b> {len(config.MANAGER_IDS)}\n\n"
        )
        
        # Get statistics per manager
        stats_text += "<b>📊 Posts by Manager:</b>\n\n"
        
        for idx, manager_id in enumerate(config.MANAGER_IDS, 1):
            # Get total posts by this manager
            manager_total_posts = db.posts.count_documents({'user_id': manager_id})
            manager_total_pending = db.pending_posts.count_documents({'user_id': manager_id, 'status': 'pending'})
            
            stats_text += f"<b>👤 Manager {idx}:</b>\n"
            stats_text += f"   Total: {manager_total_posts} posted, {manager_total_pending} pending\n"
            
            # Get posts per server for this manager
            for server_id in [1, 2, 3]:
                server_posts = db.posts.count_documents({'user_id': manager_id, 'server_id': server_id})
                server_pending = db.pending_posts.count_documents({'user_id': manager_id, 'server_id': server_id, 'status': 'pending'})
                stats_text += f"   Server {server_id}: {server_posts} posted, {server_pending} pending\n"
            
            stats_text += "\n"
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
    
    async def server_config_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show server configuration menu (Admin only)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ Only the admin can configure servers.")
            return
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        keyboard = [
            [InlineKeyboardButton("🖥️ Server Configuration", callback_data="admin_server_config")],
            [InlineKeyboardButton("👔 Manager Management", callback_data="admin_manager_management")],
            [InlineKeyboardButton("🗑️ Withdraw Posts", callback_data="admin_withdraw_posts")]
        ]
        
        await update.message.reply_text(
            "⚙️ <b>Admin Settings</b>\n\n"
            "Select an option:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def post_to_server_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show post to server menu (Manager)"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        if not db.is_manager_authenticated(user.id) and user.id != config.ADMIN_ID:
            await update.message.reply_text("❌ Please login as a manager first. Use /manager")
            return
        
        # Show all server configurations
        configs = db.get_all_server_configs()
        
        config_text = "📤 <b>Post to Server</b>\n\n"
        config_text += "<b>Current Server Configurations:</b>\n\n"
        
        for cfg in configs:
            server_id = cfg['server_id']
            server_name = cfg.get('server_name', f'Server {server_id}')
            footer = cfg.get('footer_text', 'Not set')
            btn1 = cfg.get('button1_text', 'Not set')
            btn2 = cfg.get('button2_text', 'Not set')
            time_gap = cfg.get('min_time_gap', 30)
            
            # Check posting permission
            posting_enabled = db.is_server_posting_enabled(server_id)
            permission_status = "✅ Enabled" if posting_enabled else "❌ Disabled"
            
            # Check if can post now
            can_post, remaining = db.can_post_now(server_id)
            status = "✅ Ready" if can_post else f"⏳ Wait {remaining} min"
            
            # Get pending post count
            pending_count = db.get_pending_post_count(server_id)
            pending_text = f" | 📋 {pending_count} pending" if pending_count > 0 else ""
            
            config_text += (
                f"<b>🖥️ {server_name}</b>\n"
                f"Post Permission: {permission_status}\n"
                f"Status: {status}{pending_text}\n"
                f"Footer: {footer[:30]}{'...' if len(footer) > 30 else ''}\n"
                f"Button 1: {btn1}\n"
                f"Button 2: {btn2}\n"
                f"Time Gap: {time_gap} minutes\n\n"
            )
        
        config_text += "Select a server to post:"
        
        await update.message.reply_text(
            config_text,
            parse_mode='HTML',
            reply_markup=get_post_server_keyboard()
        )
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads for posting"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        # Check if waiting for post content
        if context.user_data.get('waiting_post_content'):
            try:
                server_id = context.user_data.get('post_server_id')
                scheduled_time = context.user_data.get('scheduled_post_time')
                scheduled_time_str = context.user_data.get('scheduled_post_time_str', 'now')
                
                logger.info(f"Processing photo upload for server {server_id} from user {user.id}")
                
                # Get the largest photo
                photo = update.message.photo[-1]
                photo_id = photo.file_id
                
                # Get caption if provided
                caption = update.message.caption or ""
                
                # Store photo data for confirmation
                context.user_data['post_photo_id'] = photo_id
                context.user_data['post_caption'] = caption
                context.user_data['waiting_post_content'] = False
                context.user_data['waiting_post_confirmation'] = True
                
                # Get server config
                config_data = db.get_server_config(server_id)
                footer = config_data.get('footer_text', '')
                
                # Add footer to caption if exists
                if footer:
                    full_caption = f"{caption}\n\n{footer}" if caption else footer
                else:
                    full_caption = caption
                
                # Create buttons if configured
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                buttons = []
                
                btn1_text = config_data.get('button1_text', '').strip() if config_data.get('button1_text') else ''
                btn1_url = config_data.get('button1_url', '').strip() if config_data.get('button1_url') else ''
                if btn1_text and btn1_url:
                    try:
                        buttons.append([InlineKeyboardButton(btn1_text, url=btn1_url)])
                    except Exception as e:
                        logger.warning(f"Preview: Failed to create button1: {e}")
                
                btn2_text = config_data.get('button2_text', '').strip() if config_data.get('button2_text') else ''
                btn2_url = config_data.get('button2_url', '').strip() if config_data.get('button2_url') else ''
                if btn2_text and btn2_url:
                    try:
                        buttons.append([InlineKeyboardButton(btn2_text, url=btn2_url)])
                    except Exception as e:
                        logger.warning(f"Preview: Failed to create button2: {e}")
                
                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                
                # Show preview
                try:
                    await update.message.reply_photo(
                        photo=photo_id,
                        caption=f"📸 <b>PREVIEW - Server {server_id}</b>\n\n{full_caption}",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    if 'invalid' in str(e).lower() and 'url' in str(e).lower():
                        logger.warning(f"Invalid URL in buttons, retrying without buttons: {e}")
                        await update.message.reply_photo(
                            photo=photo_id,
                            caption=f"📸 <b>PREVIEW - Server {server_id}</b>\n\n{full_caption}",
                            parse_mode='HTML'
                        )
                    else:
                        raise
                
                # Ask for confirmation
                from datetime import datetime
                import pytz
                
                if scheduled_time_str == "now" or scheduled_time <= datetime.utcnow():
                    time_info = "Will post <b>immediately</b>"
                else:
                    time_diff = scheduled_time - datetime.utcnow()
                    minutes_until = max(1, int(time_diff.total_seconds() / 60))
                    hours_until = minutes_until // 60
                    mins_remaining = minutes_until % 60
                    
                    if hours_until > 0:
                        time_until_str = f"{hours_until}h {mins_remaining}m"
                    else:
                        time_until_str = f"{minutes_until}m"
                    
                    time_info = f"Will post at <b>{scheduled_time_str}</b> (in {time_until_str})"
                
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm & Post", callback_data=f"confirm_post_{server_id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_post_confirm")
                    ]
                ])
                
                await update.message.reply_text(
                    f"👆 <b>Preview Above</b>\n\n"
                    f"📤 <b>Server:</b> {server_id}\n"
                    f"📸 <b>Type:</b> Photo with caption\n"
                    f"⏰ <b>Schedule:</b> {time_info}\n\n"
                    f"<b>Confirm to proceed:</b>",
                    parse_mode='HTML',
                    reply_markup=confirm_keyboard
                )
                
                logger.info(f"Photo preview shown, waiting for confirmation")
                    
            except Exception as e:
                logger.error(f"Error handling photo upload: {e}", exc_info=True)
                await update.message.reply_text(
                    "❌ <b>Error Processing Photo</b>\n\n"
                    "There was an error processing your photo. Please try again.\n\n"
                    f"Error: {str(e)}",
                    parse_mode='HTML'
                )
                context.user_data['waiting_post_content'] = False
                context.user_data.pop('scheduled_post_time', None)
                context.user_data.pop('scheduled_post_time_str', None)
        else:
            await update.message.reply_text(
                "📸 To post a photo, first click '📤 Post to Server' and select a server.",
                parse_mode='HTML'
            )
    
    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for various waiting states"""
        user = update.effective_user
        
        # Check authorization
        if not await self._check_authorization(update, context):
            return
        
        # Check if waiting for posting time
        if context.user_data.get('waiting_post_time'):
            try:
                server_id = context.user_data.get('post_server_id')
                time_input = update.message.text.strip().lower()
                
                import pytz
                from datetime import datetime, timedelta
                import re
                
                ist = pytz.timezone('Asia/Kolkata')
                current_time_ist = datetime.now(ist)
                
                # Handle "now" keyword
                if time_input == "now":
                    proposed_time = datetime.utcnow()
                    time_str = "now"
                else:
                    # Try to parse date + time format: DD/MM HH:MM or DD/MM/YYYY HH:MM
                    datetime_pattern = re.compile(r'^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\s+([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
                    datetime_match = datetime_pattern.match(time_input)
                    
                    if datetime_match:
                        # Date + time format
                        day = int(datetime_match.group(1))
                        month = int(datetime_match.group(2))
                        year = int(datetime_match.group(3)) if datetime_match.group(3) else current_time_ist.year
                        hour = int(datetime_match.group(4))
                        minute = int(datetime_match.group(5))
                        
                        try:
                            # Create datetime in IST
                            proposed_time_ist = ist.localize(datetime(year, month, day, hour, minute, 0, 0))
                            
                            # Check if date is in the past
                            if proposed_time_ist < current_time_ist:
                                await update.message.reply_text(
                                    "❌ <b>Date/Time in the Past!</b>\n\n"
                                    "Please choose a future date and time.\n\n"
                                    "Try again or type /cancel:",
                                    parse_mode='HTML'
                                )
                                return
                            
                            # Convert to UTC for database
                            proposed_time = proposed_time_ist.astimezone(pytz.utc).replace(tzinfo=None)
                            time_str = proposed_time_ist.strftime('%d/%m/%Y %H:%M IST')
                            
                        except ValueError as e:
                            await update.message.reply_text(
                                "❌ <b>Invalid Date!</b>\n\n"
                                f"Error: {str(e)}\n\n"
                                "Please check the date and try again.\n\n"
                                "<b>Format:</b> DD/MM HH:MM or DD/MM/YYYY HH:MM",
                                parse_mode='HTML'
                            )
                            return
                    else:
                        # Try time-only format (HH:MM)
                        time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
                        match = time_pattern.match(time_input)
                        
                        if not match:
                            await update.message.reply_text(
                                "❌ <b>Invalid format!</b>\n\n"
                                "Please use one of these formats:\n\n"
                                "<b>Time only (today/tomorrow):</b>\n"
                                "• <code>14:30</code> - 2:30 PM\n"
                                "• <code>09:00</code> - 9:00 AM\n\n"
                                "<b>Date + Time:</b>\n"
                                "• <code>25/01 14:30</code> - Jan 25 at 2:30 PM\n"
                                "• <code>25/01/2026 14:30</code> - Jan 25, 2026 at 2:30 PM\n\n"
                                "<b>Immediate:</b>\n"
                                "• <code>now</code> - Post immediately\n\n"
                                "Try again or type /cancel:",
                                parse_mode='HTML'
                            )
                            return
                        
                        # Parse the time
                        hour = int(match.group(1))
                        minute = int(match.group(2))
                        
                        # Create datetime for today at specified time (IST)
                        proposed_time_ist = current_time_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        
                        # If time is in the past today, schedule for tomorrow
                        if proposed_time_ist <= current_time_ist:
                            proposed_time_ist += timedelta(days=1)
                        
                        # Convert to UTC for database
                        proposed_time = proposed_time_ist.astimezone(pytz.utc).replace(tzinfo=None)
                        
                        # Show date if tomorrow
                        if proposed_time_ist.date() > current_time_ist.date():
                            time_str = proposed_time_ist.strftime('%d/%m %H:%M IST')
                        else:
                            time_str = proposed_time_ist.strftime('%H:%M IST')
                
                # Check for time conflicts
                config_data = db.get_server_config(server_id)
                min_gap = config_data.get('min_time_gap', 30)
                
                # Check against last post
                last_post = db.get_last_post(server_id)
                if last_post and time_input != "now":
                    last_time = last_post['posted_at']
                    time_diff_minutes = abs((proposed_time - last_time).total_seconds() / 60)
                    
                    if time_diff_minutes < min_gap:
                        # Calculate next available time
                        next_available = last_time + timedelta(minutes=min_gap)
                        next_available_ist = next_available.replace(tzinfo=pytz.utc).astimezone(ist)
                        next_available_str = next_available_ist.strftime('%d/%m %H:%M IST')
                        
                        await update.message.reply_text(
                            f"⚠️ <b>Time Slot Busy!</b>\n\n"
                            f"Your requested time conflicts with the minimum time gap.\n\n"
                            f"⏱️ <b>Minimum gap:</b> {min_gap} minutes\n"
                            f"⏰ <b>Last post:</b> {last_post['posted_at'].replace(tzinfo=pytz.utc).astimezone(ist).strftime('%d/%m %H:%M IST')}\n"
                            f"✅ <b>Next available:</b> {next_available_str}\n\n"
                            f"Please choose a time after <b>{next_available_str}</b> or type <code>now</code> to post immediately:",
                            parse_mode='HTML'
                        )
                        return
                
                # Check against pending posts
                conflict, suggested_time = db.check_time_conflict(server_id, proposed_time)
                if not conflict and time_input != "now":
                    suggested_time_ist = suggested_time.replace(tzinfo=pytz.utc).astimezone(ist)
                    suggested_time_str = suggested_time_ist.strftime('%d/%m %H:%M IST')
                    
                    await update.message.reply_text(
                        f"⚠️ <b>Time Slot Busy!</b>\n\n"
                        f"Your requested time conflicts with another scheduled post.\n\n"
                        f"⏱️ <b>Minimum gap:</b> {min_gap} minutes\n"
                        f"✅ <b>Next available:</b> {suggested_time_str}\n\n"
                        f"Please choose a time after <b>{suggested_time_str}</b> or type <code>now</code>:",
                        parse_mode='HTML'
                    )
                    return
                
                # Time is valid, save it and ask for content
                context.user_data['scheduled_post_time'] = proposed_time
                context.user_data['scheduled_post_time_str'] = time_str
                context.user_data['waiting_post_time'] = False
                context.user_data['waiting_post_content'] = True
                
                await update.message.reply_text(
                    f"✅ <b>Time Confirmed!</b>\n\n"
                    f"📅 <b>Scheduled for:</b> {time_str}\n\n"
                    f"Now send your content:\n"
                    f"📝 Type a text message OR\n"
                    f"📸 Upload a photo (with optional caption)\n\n"
                    f"The footer and buttons will be added automatically.\n\n"
                    f"Type /cancel to cancel.",
                    parse_mode='HTML'
                )
                
                logger.info(f"Time confirmed for server {server_id}: {time_str}")
                
            except Exception as e:
                logger.error(f"Error processing posting time: {e}", exc_info=True)
                await update.message.reply_text(
                    f"❌ <b>Error Processing Time</b>\n\n"
                    f"There was an error processing your time.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again or type /cancel.",
                    parse_mode='HTML'
                )
            return
        
        # Check if waiting for manager password (from /start or manager selection)
        if context.user_data.get('waiting_manager_password'):
            password = update.message.text
            
            # Delete the password message for security
            await update.message.delete()
            
            # Get or initialize retry count
            retry_count = context.user_data.get('password_retry_count', 0)
            
            # Check if password matches any manager password
            password_valid = False
            manager_index = -1
            
            for idx, correct_password in enumerate(config.MANAGER_PASSWORDS):
                if password == correct_password:
                    password_valid = True
                    manager_index = idx
                    break
            
            if password_valid:
                # Success - authenticate the manager
                context.user_data['waiting_manager_password'] = False
                context.user_data['password_retry_count'] = 0
                
                # Mark as authenticated in database
                db.authenticate_manager(user.id, password)
                
                await context.bot.send_message(
                    chat_id=user.id,
                    text=(
                        "✅ <b>Authentication Successful!</b>\n\n"
                        f"Welcome {user.first_name}!\n\n"
                        "Use the menu below to manage posts."
                    ),
                    parse_mode='HTML',
                    reply_markup=get_manager_menu_keyboard()
                )
                return
            else:
                # Wrong password - increment retry count
                retry_count += 1
                context.user_data['password_retry_count'] = retry_count
                
                if retry_count >= 3:
                    # Max attempts reached
                    context.user_data['waiting_manager_password'] = False
                    context.user_data['password_retry_count'] = 0
                    
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=(
                            "❌ <b>Authentication Failed</b>\n\n"
                            "Maximum password attempts (3) exceeded.\n"
                            "Please try again later with /start or /manager."
                        ),
                        parse_mode='HTML'
                    )
                    return
                else:
                    # Show error and remaining attempts
                    remaining_attempts = 3 - retry_count
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=(
                            f"❌ <b>Invalid Password</b>\n\n"
                            f"Remaining attempts: {remaining_attempts}\n\n"
                            "Please try again or type /cancel."
                        ),
                        parse_mode='HTML'
                    )
                    return
        
        # Check if waiting for server footer
        elif context.user_data.get('waiting_footer'):
            server_id = context.user_data.get('config_server_id')
            footer_text = update.message.text.strip()
            
            db.update_server_footer(server_id, footer_text)
            context.user_data['waiting_footer'] = False
            
            await update.message.reply_text(
                f"✅ <b>Footer Updated!</b>\n\n"
                f"Server {server_id} footer text:\n"
                f"<code>{footer_text}</code>",
                parse_mode='HTML'
            )
        
        # Check if waiting for button text
        elif context.user_data.get('waiting_button_text'):
            button_num = context.user_data.get('button_num')
            server_id = context.user_data.get('config_server_id')
            button_text = update.message.text.strip()
            
            context.user_data['button_text'] = button_text
            context.user_data['waiting_button_text'] = False
            context.user_data['waiting_button_url'] = True
            
            await update.message.reply_text(
                f"✅ Button text saved: <b>{button_text}</b>\n\n"
                f"Now send the URL for Button {button_num}:",
                parse_mode='HTML'
            )
        
        # Check if waiting for button URL
        elif context.user_data.get('waiting_button_url'):
            button_num = context.user_data.get('button_num')
            server_id = context.user_data.get('config_server_id')
            button_text = context.user_data.get('button_text')
            button_url = update.message.text.strip()
            
            # Validate URL
            if not button_url.startswith(('http://', 'https://')):
                await update.message.reply_text(
                    "❌ Invalid URL! Must start with http:// or https://\n"
                    "Please send a valid URL:"
                )
                return
            
            db.update_server_button(server_id, button_num, button_text, button_url)
            context.user_data['waiting_button_url'] = False
            
            await update.message.reply_text(
                f"✅ <b>Button {button_num} Updated!</b>\n\n"
                f"Text: {button_text}\n"
                f"URL: {button_url}",
                parse_mode='HTML'
            )
        
        # Check if waiting for time gap
        elif context.user_data.get('waiting_timegap'):
            server_id = context.user_data.get('config_server_id')
            
            try:
                minutes = int(update.message.text.strip())
                if minutes < 0:
                    raise ValueError("Negative value")
                
                db.update_server_time_gap(server_id, minutes)
                context.user_data['waiting_timegap'] = False
                
                await update.message.reply_text(
                    f"✅ <b>Time Gap Updated!</b>\n\n"
                    f"Server {server_id} minimum time gap: {minutes} minutes",
                    parse_mode='HTML'
                )
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid number! Please enter a positive number (minutes):"
                )
        
        # Check admin manager management actions
        if context.user_data.get('admin_action'):
            action = context.user_data.get('admin_action')
            step = context.user_data.get('admin_step')
            
            if action == 'add_manager':
                if step == 'user_id':
                    try:
                        user_id = int(update.message.text.strip())
                        context.user_data['admin_manager_user_id'] = user_id
                        context.user_data['admin_step'] = 'password'
                        
                        await update.message.reply_text(
                            f"✅ User ID: {user_id}\n\n"
                            f"Now send the password for this manager:\n\n"
                            f"Type /cancel to cancel.",
                            parse_mode='HTML'
                        )
                    except ValueError:
                        await update.message.reply_text(
                            "❌ Invalid user ID. Please send a valid Telegram User ID (number):"
                        )
                
                elif step == 'password':
                    password = update.message.text.strip()
                    user_id = context.user_data.get('admin_manager_user_id')
                    
                    db.add_manager(user_id, password=password)
                    
                    context.user_data.pop('admin_action', None)
                    context.user_data.pop('admin_step', None)
                    context.user_data.pop('admin_manager_user_id', None)
                    
                    await update.message.reply_text(
                        f"✅ <b>Manager Added!</b>\n\n"
                        f"User ID: {user_id}\n"
                        f"Password: {password}\n\n"
                        f"Manager can now login with /manager",
                        parse_mode='HTML'
                    )
            
            elif action == 'edit_manager_password':
                if step == 'user_id':
                    try:
                        user_id = int(update.message.text.strip())
                        manager = db.get_manager(user_id)
                        
                        if not manager:
                            await update.message.reply_text(
                                f"❌ Manager with User ID {user_id} not found.\n\n"
                                f"Please send a valid manager User ID or /cancel:"
                            )
                            return
                        
                        context.user_data['admin_manager_user_id'] = user_id
                        context.user_data['admin_step'] = 'password'
                        
                        await update.message.reply_text(
                            f"✅ Manager found: {user_id}\n\n"
                            f"Now send the new password:\n\n"
                            f"Type /cancel to cancel.",
                            parse_mode='HTML'
                        )
                    except ValueError:
                        await update.message.reply_text(
                            "❌ Invalid user ID. Please send a valid Telegram User ID (number):"
                        )
                
                elif step == 'password':
                    password = update.message.text.strip()
                    user_id = context.user_data.get('admin_manager_user_id')
                    
                    db.update_manager_password(user_id, password)
                    
                    context.user_data.pop('admin_action', None)
                    context.user_data.pop('admin_step', None)
                    context.user_data.pop('admin_manager_user_id', None)
                    
                    await update.message.reply_text(
                        f"✅ <b>Password Updated!</b>\n\n"
                        f"Manager {user_id} password has been updated.\n\n"
                        f"New password: {password}",
                        parse_mode='HTML'
                    )
            
            elif action == 'remove_manager':
                try:
                    user_id = int(update.message.text.strip())
                    manager = db.get_manager(user_id)
                    
                    if not manager:
                        await update.message.reply_text(
                            f"❌ Manager with User ID {user_id} not found.\n\n"
                            f"Please send a valid manager User ID or /cancel:"
                        )
                        return
                    
                    db.remove_manager(user_id)
                    
                    context.user_data.pop('admin_action', None)
                    context.user_data.pop('admin_step', None)
                    
                    await update.message.reply_text(
                        f"✅ <b>Manager Removed!</b>\n\n"
                        f"Manager {user_id} has been removed from the system.",
                        parse_mode='HTML'
                    )
                    
                    # Try to logout the manager
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="⚠️ <b>Access Revoked</b>\n\nYour manager access has been revoked by admin.",
                            parse_mode='HTML'
                        )
                    except:
                        pass
                        
                except ValueError:
                    await update.message.reply_text(
                        "❌ Invalid user ID. Please send a valid Telegram User ID (number):"
                    )
            
            return
        
        # Check if waiting for post content
        elif context.user_data.get('waiting_post_content'):
            try:
                server_id = context.user_data.get('post_server_id')
                post_content = update.message.text.strip()
                scheduled_time = context.user_data.get('scheduled_post_time')
                scheduled_time_str = context.user_data.get('scheduled_post_time_str', 'now')
                
                logger.info(f"Processing text post for server {server_id} from user {user.id}")
                
                # Store text content for confirmation
                context.user_data['post_text_content'] = post_content
                context.user_data['waiting_post_content'] = False
                context.user_data['waiting_post_confirmation'] = True
                
                # Get server config
                config_data = db.get_server_config(server_id)
                footer = config_data.get('footer_text', '')
                
                # Add footer if exists
                if footer:
                    full_content = f"{post_content}\n\n{footer}"
                else:
                    full_content = post_content
                
                # Create buttons if configured (same logic as _send_post_to_channel)
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                buttons = []
                
                btn1_text = config_data.get('button1_text', '').strip() if config_data.get('button1_text') else ''
                btn1_url = config_data.get('button1_url', '').strip() if config_data.get('button1_url') else ''
                if btn1_text and btn1_url:
                    try:
                        buttons.append([InlineKeyboardButton(btn1_text, url=btn1_url)])
                    except Exception as e:
                        logger.warning(f"Preview: Failed to create button1: {e}")
                
                btn2_text = config_data.get('button2_text', '').strip() if config_data.get('button2_text') else ''
                btn2_url = config_data.get('button2_url', '').strip() if config_data.get('button2_url') else ''
                if btn2_text and btn2_url:
                    try:
                        buttons.append([InlineKeyboardButton(btn2_text, url=btn2_url)])
                    except Exception as e:
                        logger.warning(f"Preview: Failed to create button2: {e}")
                
                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                
                # Show preview
                preview_text = f"📝 <b>PREVIEW - Server {server_id}</b>\n\n{full_content}"
                
                try:
                    await update.message.reply_text(
                        preview_text,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    if 'invalid' in str(e).lower() and 'url' in str(e).lower():
                        logger.warning(f"Invalid URL in buttons, retrying without buttons: {e}")
                        await update.message.reply_text(
                            preview_text,
                            parse_mode='HTML'
                        )
                    else:
                        raise
                
                # Ask for confirmation
                from datetime import datetime
                import pytz
                
                if scheduled_time_str == "now" or scheduled_time <= datetime.utcnow():
                    time_info = "Will post <b>immediately</b>"
                else:
                    time_diff = scheduled_time - datetime.utcnow()
                    minutes_until = max(1, int(time_diff.total_seconds() / 60))
                    hours_until = minutes_until // 60
                    mins_remaining = minutes_until % 60
                    
                    if hours_until > 0:
                        time_until_str = f"{hours_until}h {mins_remaining}m"
                    else:
                        time_until_str = f"{minutes_until}m"
                    
                    time_info = f"Will post at <b>{scheduled_time_str}</b> (in {time_until_str})"
                
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Confirm & Post", callback_data=f"confirm_post_{server_id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_post_confirm")
                    ]
                ])
                
                await update.message.reply_text(
                    f"👆 <b>Preview Above</b>\n\n"
                    f"📤 <b>Server:</b> {server_id}\n"
                    f"📝 <b>Type:</b> Text post\n"
                    f"⏰ <b>Schedule:</b> {time_info}\n\n"
                    f"<b>Confirm to proceed:</b>",
                    parse_mode='HTML',
                    reply_markup=confirm_keyboard
                )
                
                logger.info(f"Text preview shown, waiting for confirmation")
                    
            except Exception as e:
                error_msg = str(e).lower()
                if 'invalid' in error_msg and 'url' in error_msg:
                    logger.warning(f"Invalid URL in post, continuing without buttons: {e}")
                    preview_text = f"📝 <b>PREVIEW - Server {server_id}</b>\n\n{full_content}"
                    await update.message.reply_text(
                        preview_text,
                        parse_mode='HTML'
                    )
                    
                    from datetime import datetime
                    import pytz
                    
                    if scheduled_time_str == "now" or scheduled_time <= datetime.utcnow():
                        time_info = "Will post <b>immediately</b>"
                    else:
                        time_diff = scheduled_time - datetime.utcnow()
                        minutes_until = max(1, int(time_diff.total_seconds() / 60))
                        hours_until = minutes_until // 60
                        mins_remaining = minutes_until % 60
                        
                        if hours_until > 0:
                            time_until_str = f"{hours_until}h {mins_remaining}m"
                        else:
                            time_until_str = f"{minutes_until}m"
                        
                        time_info = f"Will post at <b>{scheduled_time_str}</b> (in {time_until_str})"
                    
                    confirm_keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Confirm & Post", callback_data=f"confirm_post_{server_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data="cancel_post_confirm")
                        ]
                    ])
                    
                    await update.message.reply_text(
                        f"👆 <b>Preview Above</b>\n\n"
                        f"📤 <b>Server:</b> {server_id}\n"
                        f"📝 <b>Type:</b> Text post\n"
                        f"⏰ <b>Schedule:</b> {time_info}\n\n"
                        f"<b>Confirm to proceed:</b>",
                        parse_mode='HTML',
                        reply_markup=confirm_keyboard
                    )
                    logger.info(f"Text preview shown (without buttons), waiting for confirmation")
                else:
                    logger.error(f"Error handling text post: {e}", exc_info=True)
                    await update.message.reply_text(
                        "❌ <b>Error Processing Post</b>\n\n"
                        "There was an error processing your post. Please try again.\n\n"
                        f"Error: {str(e)}",
                        parse_mode='HTML'
                    )
                    context.user_data['waiting_post_content'] = False
                    context.user_data.pop('scheduled_post_time', None)
                    context.user_data.pop('scheduled_post_time_str', None)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Manager selection callbacks
        if data.startswith("select_manager_"):
            manager_num = int(data.split('_')[-1])
            manager_index = manager_num - 1  # Convert to 0-based index
            
            context.user_data['selected_manager_index'] = manager_index
            context.user_data['waiting_manager_password'] = True
            context.user_data['password_retry_count'] = 0
            
            await query.edit_message_text(
                f"🔐 <b>Manager {manager_num} Login</b>\n\n"
                "Please enter your password:\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
        
        elif data == "cancel_login":
            await query.edit_message_text(
                "❌ Login cancelled.",
                parse_mode='HTML'
            )
        
        # Settings callbacks
        elif data == "back_to_menu":
            await query.message.delete()
        
        # Schedule callbacks
        # Server configuration callbacks
        elif data.startswith("config_server_"):
            server_id = int(data.split('_')[-1])
            config_data = db.get_server_config(server_id)
            
            posting_enabled = db.is_server_posting_enabled(server_id)
            permission_status = "✅ Enabled" if posting_enabled else "❌ Disabled"
            
            config_text = (
                f"⚙️ <b>Server {server_id} Configuration</b>\n\n"
                f"<b>Current Settings:</b>\n"
                f"Post Permission: {permission_status}\n"
                f"Footer: {config_data.get('footer_text', 'Not set')[:50]}\n"
                f"Button 1: {config_data.get('button1_text', 'Not set')}\n"
                f"Button 2: {config_data.get('button2_text', 'Not set')}\n"
                f"Time Gap: {config_data.get('min_time_gap', 30)} minutes\n\n"
                "Select what to configure:"
            )
            
            await query.edit_message_text(
                config_text,
                parse_mode='HTML',
                reply_markup=get_server_config_keyboard(server_id)
            )
        
        elif data.startswith("edit_footer_"):
            server_id = int(data.split('_')[-1])
            context.user_data['config_server_id'] = server_id
            context.user_data['waiting_footer'] = True
            
            await query.message.reply_text(
                f"📝 <b>Edit Footer for Server {server_id}</b>\n\n"
                "Send the footer text that will be automatically appended to every post.\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data.startswith("edit_button"):
            # Parse: edit_button1_1 or edit_button2_1
            parts = data.split('_')
            # parts = ['edit', 'button1', '1'] or ['edit', 'button2', '1']
            button_str = parts[1]  # 'button1' or 'button2'
            button_num = int(button_str[-1])  # Get last character: 1 or 2
            server_id = int(parts[2])  # Server ID
            
            context.user_data['config_server_id'] = server_id
            context.user_data['button_num'] = button_num
            context.user_data['waiting_button_text'] = True
            
            await query.message.reply_text(
                f"🔘 <b>Edit Button {button_num} for Server {server_id}</b>\n\n"
                f"Send the button text (label):\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data.startswith("edit_timegap_"):
            server_id = int(data.split('_')[-1])
            context.user_data['config_server_id'] = server_id
            context.user_data['waiting_timegap'] = True
            
            await query.message.reply_text(
                f"⏱️ <b>Edit Time Gap for Server {server_id}</b>\n\n"
                "Send the minimum time gap in minutes between posts.\n\n"
                "Example: 30 (for 30 minutes)\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data.startswith("toggle_posting_"):
            server_id = int(data.split('_')[-1])
            user = query.from_user
            
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can toggle posting permission", show_alert=True)
                return
            
            posting_enabled = db.is_server_posting_enabled(server_id)
            
            if posting_enabled:
                db.disable_server_posting(server_id)
                await query.answer("❌ Posting disabled for this server", show_alert=True)
            else:
                db.enable_server_posting(server_id)
                await query.answer("✅ Posting enabled for this server", show_alert=True)
            
            # Refresh the config display
            config_data = db.get_server_config(server_id)
            posting_status = "✅ Enabled" if not posting_enabled else "❌ Disabled"
            
            config_text = (
                f"⚙️ <b>Server {server_id} Configuration</b>\n\n"
                f"<b>Current Settings:</b>\n"
                f"Post Permission: {posting_status}\n"
                f"Footer: {config_data.get('footer_text', 'Not set')[:50]}\n"
                f"Button 1: {config_data.get('button1_text', 'Not set')}\n"
                f"Button 2: {config_data.get('button2_text', 'Not set')}\n"
                f"Time Gap: {config_data.get('min_time_gap', 30)} minutes\n\n"
                "Select what to configure:"
            )
            
            await query.edit_message_text(
                config_text,
                parse_mode='HTML',
                reply_markup=get_server_config_keyboard(server_id)
            )
        
        elif data.startswith("view_config_"):
            server_id = int(data.split('_')[-1])
            config_data = db.get_server_config(server_id)
            
            can_post, remaining = db.can_post_now(server_id)
            status = "✅ Ready to post" if can_post else f"⏳ Wait {remaining} minutes"
            posting_enabled = db.is_server_posting_enabled(server_id)
            permission_status = "✅ Enabled" if posting_enabled else "❌ Disabled"
            
            config_text = (
                f"👁️ <b>Server {server_id} - Full Configuration</b>\n\n"
                f"<b>Post Permission:</b> {permission_status}\n"
                f"<b>Status:</b> {status}\n\n"
                f"<b>Footer Text:</b>\n{config_data.get('footer_text', 'Not set')}\n\n"
                f"<b>Button 1:</b>\n"
                f"Text: {config_data.get('button1_text', 'Not set')}\n"
                f"URL: {config_data.get('button1_url', 'Not set')}\n\n"
                f"<b>Button 2:</b>\n"
                f"Text: {config_data.get('button2_text', 'Not set')}\n"
                f"URL: {config_data.get('button2_url', 'Not set')}\n\n"
                f"<b>Minimum Time Gap:</b> {config_data.get('min_time_gap', 30)} minutes"
            )
            
            await query.answer()
            await query.message.reply_text(config_text, parse_mode='HTML')
        
        elif data == "back_to_servers":
            await query.edit_message_text(
                "⚙️ <b>Server Configuration</b>\n\n"
                "Select a server to configure:",
                parse_mode='HTML',
                reply_markup=get_server_selection_keyboard()
            )
        
        elif data == "admin_server_config":
            await query.edit_message_text(
                "⚙️ <b>Server Configuration</b>\n\n"
                "Select a server to configure:",
                parse_mode='HTML',
                reply_markup=get_server_selection_keyboard()
            )
        
        elif data == "admin_manager_management":
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can manage managers", show_alert=True)
                return
            
            managers = db.get_all_managers()
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            managers_text = "👔 <b>Manager Management</b>\n\n"
            
            if managers:
                for idx, mgr in enumerate(managers, 1):
                    user_id = mgr.get('user_id')
                    username = mgr.get('username', 'N/A')
                    from datetime import datetime as dt_module
                    added_at = mgr.get('added_at', dt_module.utcnow())
                    if isinstance(added_at, dt_module):
                        added_str = added_at.strftime('%Y-%m-%d')
                    else:
                        added_str = str(added_at)[:10]
                    
                    managers_text += (
                        f"<b>{idx}. Manager {user_id}</b>\n"
                        f"Username: @{username if username else 'N/A'}\n"
                        f"Added: {added_str}\n\n"
                    )
            else:
                managers_text += "No managers found.\n\n"
            
            managers_text += "Use buttons below to manage:"
            
            keyboard = [
                [InlineKeyboardButton("➕ Add Manager", callback_data="admin_add_manager")],
                [InlineKeyboardButton("✏️ Edit Manager Password", callback_data="admin_edit_manager_password")],
                [InlineKeyboardButton("🗑️ Remove Manager", callback_data="admin_remove_manager")],
                [InlineKeyboardButton("« Back", callback_data="back_to_admin_settings")]
            ]
            
            await query.edit_message_text(
                managers_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "admin_add_manager":
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can add managers", show_alert=True)
                return
            
            context.user_data['admin_action'] = 'add_manager'
            context.user_data['admin_step'] = 'user_id'
            
            await query.message.reply_text(
                "➕ <b>Add Manager</b>\n\n"
                "Send the Telegram User ID of the manager:\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data == "admin_edit_manager_password":
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can edit manager passwords", show_alert=True)
                return
            
            context.user_data['admin_action'] = 'edit_manager_password'
            context.user_data['admin_step'] = 'user_id'
            
            await query.message.reply_text(
                "✏️ <b>Edit Manager Password</b>\n\n"
                "Send the Telegram User ID of the manager:\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data == "admin_remove_manager":
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can remove managers", show_alert=True)
                return
            
            context.user_data['admin_action'] = 'remove_manager'
            context.user_data['admin_step'] = 'user_id'
            
            await query.message.reply_text(
                "🗑️ <b>Remove Manager</b>\n\n"
                "Send the Telegram User ID of the manager to remove:\n\n"
                "Type /cancel to cancel.",
                parse_mode='HTML'
            )
            await query.answer()
        
        elif data == "admin_withdraw_posts":
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can withdraw posts", show_alert=True)
                return
            
            # Get all pending posts
            from bson import ObjectId
            all_pending = []
            for server_id in [1, 2, 3]:
                pending = db.get_pending_posts_by_server(server_id)
                all_pending.extend(pending)
            
            if not all_pending:
                await query.answer("✅ No pending posts to withdraw", show_alert=True)
                return
            
            # Sort by scheduled time
            all_pending.sort(key=lambda x: x['scheduled_time'])
            
            import pytz
            from datetime import datetime as dt_module
            ist = pytz.timezone('Asia/Kolkata')
            current_time = dt_module.utcnow()
            
            posts_text = f"🗑️ <b>Withdraw Posts ({len(all_pending)})</b>\n\n"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            buttons = []
            
            for idx, post in enumerate(all_pending[:20], 1):
                server_id = post['server_id']
                user_id = post['user_id']
                scheduled_time = post['scheduled_time']
                scheduled_ist = scheduled_time.replace(tzinfo=pytz.utc).astimezone(ist)
                scheduled_str = scheduled_ist.strftime('%d/%m %H:%M IST')
                
                content = post.get('message_text', '')
                has_photo = post.get('photo_id') is not None
                content_type = "Photo" if has_photo else "Text"
                content_preview = content[:30] if content else "[No text]"
                
                posts_text += (
                    f"<b>{idx}. Server {server_id}</b> - {content_type}\n"
                    f"Manager: {user_id} | {scheduled_str}\n"
                    f"{content_preview}{'...' if len(content) > 30 else ''}\n\n"
                )
                
                buttons.append([
                    InlineKeyboardButton(
                        f"🗑️ Withdraw Post #{idx}",
                        callback_data=f"withdraw_post_{str(post['_id'])}"
                    )
                ])
            
            if len(all_pending) > 20:
                posts_text += f"... and {len(all_pending) - 20} more posts\n\n"
            
            posts_text += "Click a button below to withdraw a post:"
            
            keyboard = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(
                posts_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            await query.answer()
        
        elif data.startswith("withdraw_post_"):
            user = query.from_user
            if user.id != config.ADMIN_ID:
                await query.answer("❌ Only admin can withdraw posts", show_alert=True)
                return
            
            from bson import ObjectId
            post_id_str = data.replace("withdraw_post_", "")
            
            try:
                if not post_id_str or len(post_id_str) != 24:
                    raise ValueError("Invalid post ID")
                post_id = ObjectId(post_id_str)
                
                pending_post = db.pending_posts.find_one({'_id': post_id})
                
                if not pending_post:
                    await query.answer("❌ Post not found or already deleted", show_alert=True)
                    return
                
                db.delete_pending_post(post_id)
                
                server_id = pending_post['server_id']
                manager_id = pending_post['user_id']
                
                await query.answer("✅ Post withdrawn successfully!", show_alert=True)
                
                await query.edit_message_text(
                    f"✅ <b>Post Withdrawn</b>\n\n"
                    f"Post from Manager {manager_id} to Server {server_id} has been withdrawn.\n\n"
                    f"Use /setting to withdraw more posts.",
                    parse_mode='HTML'
                )
                
                # Notify the manager
                try:
                    await context.bot.send_message(
                        chat_id=manager_id,
                        text=(
                            f"⚠️ <b>Post Withdrawn</b>\n\n"
                            f"Your scheduled post to Server {server_id} has been withdrawn by admin."
                        ),
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Could not notify manager {manager_id}: {e}")
                
                logger.info(f"Post {post_id} withdrawn by admin {user.id}")
                
            except Exception as e:
                logger.error(f"Error withdrawing post: {e}", exc_info=True)
                await query.answer(f"❌ Error: {str(e)}", show_alert=True)
        
        elif data == "back_to_admin_settings":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            keyboard = [
                [InlineKeyboardButton("🖥️ Server Configuration", callback_data="admin_server_config")],
                [InlineKeyboardButton("👔 Manager Management", callback_data="admin_manager_management")],
                [InlineKeyboardButton("🗑️ Withdraw Posts", callback_data="admin_withdraw_posts")]
            ]
            
            await query.edit_message_text(
                "⚙️ <b>Admin Settings</b>\n\n"
                "Select an option:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("post_server_"):
            server_id = int(data.split('_')[-1])
            
            # Check if posting is enabled for this server
            posting_enabled = db.is_server_posting_enabled(server_id)
            if not posting_enabled:
                await query.answer("❌ Posting is disabled for this server. Contact admin.", show_alert=True)
                await query.message.reply_text(
                    f"❌ <b>Posting Disabled</b>\n\n"
                    f"Posting is currently disabled for Server {server_id}.\n\n"
                    f"Please contact the admin to enable posting for this server.",
                    parse_mode='HTML'
                )
                return
            
            context.user_data['post_server_id'] = server_id
            context.user_data['waiting_post_time'] = True
            
            # Show server config
            config_data = db.get_server_config(server_id)
            
            # Get pending count
            pending_count = db.get_pending_post_count(server_id)
            pending_info = f"\n📋 <b>Pending posts:</b> {pending_count}" if pending_count > 0 else ""
            
            # Get current time in IST
            import pytz
            from datetime import datetime
            ist = pytz.timezone('Asia/Kolkata')
            current_time_ist = datetime.now(ist)
            current_time_str = current_time_ist.strftime('%H:%M')
            
            # Check last post time
            last_post = db.get_last_post(server_id)
            min_gap = config_data.get('min_time_gap', 30)
            
            if last_post:
                last_time = last_post['posted_at']
                last_time_ist = last_time.replace(tzinfo=pytz.utc).astimezone(ist)
                last_time_str = last_time_ist.strftime('%H:%M IST')
                
                # Calculate next available time
                from datetime import timedelta
                next_available = last_time + timedelta(minutes=min_gap)
                next_available_ist = next_available.replace(tzinfo=pytz.utc).astimezone(ist)
                next_available_str = next_available_ist.strftime('%H:%M IST')
                
                time_info = (
                    f"⏰ <b>Last post:</b> {last_time_str}\n"
                    f"⏱️ <b>Minimum gap:</b> {min_gap} minutes\n"
                    f"✅ <b>Next available:</b> {next_available_str}\n\n"
                )
            else:
                time_info = f"✅ <b>No previous posts</b> - You can post anytime!\n\n"
            
            config_preview = (
                f"📤 <b>Posting to Server {server_id}</b>\n\n"
                f"{time_info}"
                f"🕐 <b>Current time (IST):</b> {current_time_str}\n"
                f"{pending_info}\n\n"
                f"<b>Server Configuration:</b>\n"
                f"Footer: {config_data.get('footer_text', 'None')[:30]}...\n"
                f"Button 1: {config_data.get('button1_text', 'None')}\n"
                f"Button 2: {config_data.get('button2_text', 'None')}\n\n"
                "⏰ <b>Please enter posting time (IST):</b>\n\n"
                "<b>Time only (today/tomorrow):</b>\n"
                "• <code>14:30</code> - Post at 2:30 PM\n"
                "• <code>09:00</code> - Post at 9:00 AM\n\n"
                "<b>Date + Time:</b>\n"
                "• <code>25/01 14:30</code> - Jan 25 at 2:30 PM\n"
                "• <code>25/01/2026 14:30</code> - Jan 25, 2026 at 2:30 PM\n\n"
                "<b>Immediate:</b>\n"
                "• <code>now</code> - Post immediately\n\n"
                "Type /cancel to cancel."
            )
            
            await query.message.reply_text(config_preview, parse_mode='HTML')
            await query.answer()
        
        elif data == "cancel_post":
            await query.message.delete()
            await query.answer("Post cancelled")
        
        # Delete pending post callbacks
        elif data.startswith("delete_pending_"):
            from bson import ObjectId
            pending_id_str = data.split('_')[-1]
            
            try:
                pending_id = ObjectId(pending_id_str)
                
                # Get the pending post to show details
                pending_post = db.pending_posts.find_one({'_id': pending_id})
                
                if not pending_post:
                    await query.answer("❌ Post not found or already deleted", show_alert=True)
                    return
                
                # Check if user owns this post (or is admin)
                if pending_post['user_id'] != query.from_user.id and query.from_user.id != config.ADMIN_ID:
                    await query.answer("❌ You can only delete your own posts", show_alert=True)
                    return
                
                # Delete the post
                db.delete_pending_post(pending_id)
                
                # Get post details for confirmation
                server_id = pending_post['server_id']
                content = pending_post.get('message_text', '')
                has_photo = pending_post.get('photo_id') is not None
                content_type = "photo post" if has_photo else "text post"
                
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                scheduled_time = pending_post['scheduled_time']
                scheduled_ist = scheduled_time.replace(tzinfo=pytz.utc).astimezone(ist)
                scheduled_str = scheduled_ist.strftime('%H:%M IST')
                
                await query.answer("✅ Post deleted successfully!", show_alert=True)
                
                # Update the message
                await query.edit_message_text(
                    f"🗑️ <b>Post Deleted</b>\n\n"
                    f"Your {content_type} to Server {server_id} has been cancelled.\n\n"
                    f"⏰ <b>Was scheduled for:</b> {scheduled_str}\n"
                    f"💬 <b>Content:</b> {content[:50] if content else '[Photo only]'}{'...' if len(content) > 50 else ''}\n\n"
                    f"Use /pending to view remaining scheduled posts.",
                    parse_mode='HTML'
                )
                
                logger.info(f"Deleted pending post {pending_id} by user {query.from_user.id}")
                
            except Exception as e:
                logger.error(f"Error deleting pending post: {e}", exc_info=True)
                await query.answer(f"❌ Error deleting post: {str(e)}", show_alert=True)
        
        # Confirm post callbacks
        elif data.startswith("confirm_post"):
            user = query.from_user
            
            try:
                # Try to get server_id from callback data first (backup)
                if data.startswith("confirm_post_"):
                    try:
                        server_id_from_callback = int(data.split('_')[-1])
                        # Use callback data server_id as backup, but prefer context if available
                        server_id = context.user_data.get('post_server_id') or server_id_from_callback
                        # Update context with server_id from callback if it was missing
                        if context.user_data.get('post_server_id') is None:
                            context.user_data['post_server_id'] = server_id
                            logger.info(f"Recovered server_id {server_id} from callback data")
                    except (ValueError, IndexError):
                        server_id = context.user_data.get('post_server_id')
                else:
                    server_id = context.user_data.get('post_server_id')
                
                scheduled_time = context.user_data.get('scheduled_post_time')
                scheduled_time_str = context.user_data.get('scheduled_post_time_str', 'now')
                photo_id = context.user_data.get('post_photo_id')
                caption = context.user_data.get('post_caption', '')
                text_content = context.user_data.get('post_text_content', '')
                
                # Debug logging
                logger.info(f"confirm_post called - server_id: {server_id}, user_data keys: {list(context.user_data.keys())}")
                
                # Validate server_id
                if server_id is None:
                    logger.error(f"server_id is None in confirm_post callback. user_data: {context.user_data}, callback_data: {data}")
                    await query.edit_message_text(
                        "❌ <b>Error: Missing Server Information</b>\n\n"
                        "Server ID was not found. This might happen if the session expired.\n\n"
                        "Please try again:\n"
                        "1. Go to '📤 Post to Server'\n"
                        "2. Select a server\n"
                        "3. Enter time and content\n"
                        "4. Click Confirm",
                        parse_mode='HTML'
                    )
                    await query.answer("❌ Error: Missing server ID", show_alert=True)
                    return
                
                # Check if posting is enabled for this server
                if not db.is_server_posting_enabled(server_id):
                    await query.edit_message_text(
                        f"❌ <b>Posting Disabled</b>\n\n"
                        f"Posting is disabled for Server {server_id}.\n\n"
                        f"Contact admin to enable posting for this server.",
                        parse_mode='HTML'
                    )
                    await query.answer("❌ Posting disabled for this server", show_alert=True)
                    return
                
                from datetime import datetime
                
                if photo_id:
                    # Photo post
                    if scheduled_time_str == "now" or scheduled_time <= datetime.utcnow():
                        # Post immediately
                        try:
                            channel_message_id = await self._send_post_to_channel(
                                server_id, caption, photo_id=photo_id, context=context
                            )
                            db.save_post(server_id, user.id, caption, channel_message_id=channel_message_id, photo_id=photo_id)
                            
                            await query.edit_message_text(
                                "✅ <b>Photo Posted Successfully!</b>\n\n"
                                f"Your photo has been posted to Server {server_id}.\n\n"
                                f"📸 Caption: {caption[:50] if caption else '[No caption]'}{'...' if len(caption) > 50 else ''}",
                                parse_mode='HTML'
                            )
                            
                            logger.info(f"Photo posted immediately to server {server_id}")
                        except Exception as channel_error:
                            logger.error(f"Failed to post to channel for server {server_id}: {channel_error}")
                            await query.edit_message_text(
                                f"❌ <b>Error Posting to Channel</b>\n\n"
                                f"Failed to post to channel for Server {server_id}.\n\n"
                                f"<b>Error:</b> {str(channel_error)}\n\n"
                                f"Please check:\n"
                                f"• Channel ID is correct in .env file\n"
                                f"• Bot is added to the channel as admin\n"
                                f"• Channel ID format is correct\n\n"
                                f"The post was not saved.",
                                parse_mode='HTML'
                            )
                            await query.answer("❌ Posting failed", show_alert=True)
                            return
                    else:
                        # Schedule for later
                        pending_id = db.save_pending_post(server_id, user.id, caption, scheduled_time, photo_id=photo_id)
                        
                        time_diff = scheduled_time - datetime.utcnow()
                        minutes_until = max(1, int(time_diff.total_seconds() / 60))
                        hours_until = minutes_until // 60
                        mins_remaining = minutes_until % 60
                        
                        if hours_until > 0:
                            time_until_str = f"{hours_until}h {mins_remaining}m"
                        else:
                            time_until_str = f"{minutes_until}m"
                        
                        await query.edit_message_text(
                            f"⏰ <b>Photo Post Scheduled!</b>\n\n"
                            f"Your photo post to Server {server_id} has been scheduled.\n\n"
                            f"📸 Caption: {caption[:50] if caption else '[No caption]'}{'...' if len(caption) > 50 else ''}\n\n"
                            f"📅 <b>Will post at:</b> {scheduled_time_str}\n"
                            f"⏱️ <b>In approximately:</b> {time_until_str}\n\n"
                            f"✅ You'll be notified when it's published!\n\n"
                            f"Use /pending to view or cancel scheduled posts.",
                            parse_mode='HTML'
                        )
                        
                        logger.info(f"Photo scheduled as pending post {pending_id}")
                else:
                    # Text post
                    if scheduled_time_str == "now" or scheduled_time <= datetime.utcnow():
                        # Post immediately
                        try:
                            channel_message_id = await self._send_post_to_channel(
                                server_id, text_content, context=context
                            )
                            db.save_post(server_id, user.id, text_content, channel_message_id=channel_message_id)
                            
                            await query.edit_message_text(
                                "✅ <b>Post Sent Successfully!</b>\n\n"
                                f"Your post has been sent to Server {server_id}.\n\n"
                                f"📝 Content: {text_content[:50]}{'...' if len(text_content) > 50 else ''}",
                                parse_mode='HTML'
                            )
                            
                            logger.info(f"Text posted immediately to server {server_id}")
                        except Exception as channel_error:
                            logger.error(f"Failed to post to channel for server {server_id}: {channel_error}")
                            await query.edit_message_text(
                                f"❌ <b>Error Posting to Channel</b>\n\n"
                                f"Failed to post to channel for Server {server_id}.\n\n"
                                f"<b>Error:</b> {str(channel_error)}\n\n"
                                f"Please check:\n"
                                f"• Channel ID is correct in .env file\n"
                                f"• Bot is added to the channel as admin\n"
                                f"• Channel ID format is correct\n\n"
                                f"The post was not saved.",
                                parse_mode='HTML'
                            )
                            await query.answer("❌ Posting failed", show_alert=True)
                            return
                    else:
                        # Schedule for later
                        pending_id = db.save_pending_post(server_id, user.id, text_content, scheduled_time)
                        
                        time_diff = scheduled_time - datetime.utcnow()
                        minutes_until = max(1, int(time_diff.total_seconds() / 60))
                        hours_until = minutes_until // 60
                        mins_remaining = minutes_until % 60
                        
                        if hours_until > 0:
                            time_until_str = f"{hours_until}h {mins_remaining}m"
                        else:
                            time_until_str = f"{minutes_until}m"
                        
                        await query.edit_message_text(
                            f"⏰ <b>Post Scheduled!</b>\n\n"
                            f"Your post to Server {server_id} has been scheduled.\n\n"
                            f"📝 Content: {text_content[:50]}{'...' if len(text_content) > 50 else ''}\n\n"
                            f"📅 <b>Will post at:</b> {scheduled_time_str}\n"
                            f"⏱️ <b>In approximately:</b> {time_until_str}\n\n"
                            f"✅ You'll be notified when it's published!\n\n"
                            f"Use /pending to view or cancel scheduled posts.",
                            parse_mode='HTML'
                        )
                        
                        logger.info(f"Text scheduled as pending post {pending_id}")
                
                # Clear context data
                context.user_data['waiting_post_confirmation'] = False
                context.user_data.pop('scheduled_post_time', None)
                context.user_data.pop('scheduled_post_time_str', None)
                context.user_data.pop('post_photo_id', None)
                context.user_data.pop('post_caption', None)
                context.user_data.pop('post_text_content', None)
                
                await query.answer("✅ Confirmed!")
                
            except Exception as e:
                logger.error(f"Error confirming post: {e}", exc_info=True)
                await query.answer(f"❌ Error: {str(e)}", show_alert=True)
        
        elif data == "cancel_post_confirm":
            # Cancel the post
            context.user_data['waiting_post_confirmation'] = False
            context.user_data.pop('scheduled_post_time', None)
            context.user_data.pop('scheduled_post_time_str', None)
            context.user_data.pop('post_photo_id', None)
            context.user_data.pop('post_caption', None)
            context.user_data.pop('post_text_content', None)
            
            await query.edit_message_text(
                "❌ <b>Post Cancelled</b>\n\n"
                "Your post has been cancelled and will not be published.",
                parse_mode='HTML'
            )
            await query.answer("Cancelled")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current operation"""
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    def run(self):
        """Run the bot"""
        # Initialize managers in database
        for idx, manager_id in enumerate(config.MANAGER_IDS):
            password = config.MANAGER_PASSWORDS[idx] if idx < len(config.MANAGER_PASSWORDS) else "password"
            db.add_manager(manager_id, password=password)
        
        # Scheduler removed - no feedback functionality
        
        # Start bot
        logger.info("Bot started")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()
