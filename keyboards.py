from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# User Keyboards
def get_main_menu_keyboard():
    """Main menu keyboard for users"""
    keyboard = [
        [KeyboardButton("ℹ️ Help"), KeyboardButton("⚙️ Settings")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Manager Keyboards
def get_manager_menu_keyboard():
    """Main menu keyboard for managers"""
    keyboard = [
        [KeyboardButton("/post")],
        [KeyboardButton("/pending"), KeyboardButton("/status")],
        [KeyboardButton("/logout")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# Admin Keyboards
def get_admin_menu_keyboard():
    """Main menu keyboard for admin"""
    keyboard = [
        [KeyboardButton("/post"), KeyboardButton("/pending")],
        [KeyboardButton("/status"), KeyboardButton("/setting")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard():
    """Keyboard for user management"""
    keyboard = [
        [InlineKeyboardButton("📊 View All Users", callback_data="view_all_users")],
        [InlineKeyboardButton("🔍 Search User", callback_data="search_user")],
        [InlineKeyboardButton("« Back", callback_data="back_to_admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(action):
    """Confirmation keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ No", callback_data=f"cancel_{action}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_server_selection_keyboard():
    """Keyboard for selecting a server to configure"""
    keyboard = [
        [InlineKeyboardButton("🖥️ Server 1", callback_data="config_server_1")],
        [InlineKeyboardButton("🖥️ Server 2", callback_data="config_server_2")],
        [InlineKeyboardButton("🖥️ Server 3", callback_data="config_server_3")],
        [InlineKeyboardButton("« Back", callback_data="back_to_admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_server_config_keyboard(server_id):
    """Keyboard for server configuration options"""
    keyboard = [
        [InlineKeyboardButton("📝 Edit Footer Text", callback_data=f"edit_footer_{server_id}")],
        [InlineKeyboardButton("🔘 Edit Button 1", callback_data=f"edit_button1_{server_id}")],
        [InlineKeyboardButton("🔘 Edit Button 2", callback_data=f"edit_button2_{server_id}")],
        [InlineKeyboardButton("⏱️ Edit Time Gap", callback_data=f"edit_timegap_{server_id}")],
        [InlineKeyboardButton("🔒 Toggle Post Permission", callback_data=f"toggle_posting_{server_id}")],
        [InlineKeyboardButton("👁️ View Current Config", callback_data=f"view_config_{server_id}")],
        [InlineKeyboardButton("« Back to Servers", callback_data="back_to_servers")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_post_server_keyboard():
    """Keyboard for selecting server to post"""
    keyboard = [
        [InlineKeyboardButton("🖥️ Post to Server 1", callback_data="post_server_1")],
        [InlineKeyboardButton("🖥️ Post to Server 2", callback_data="post_server_2")],
        [InlineKeyboardButton("🖥️ Post to Server 3", callback_data="post_server_3")],
        [InlineKeyboardButton("« Cancel", callback_data="cancel_post")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_manager_selection_keyboard():
    """Keyboard for selecting which manager to login as"""
    keyboard = [
        [InlineKeyboardButton("👤 Manager 1", callback_data="select_manager_1")],
        [InlineKeyboardButton("👤 Manager 2", callback_data="select_manager_2")],
        [InlineKeyboardButton("« Cancel", callback_data="cancel_login")]
    ]
    return InlineKeyboardMarkup(keyboard)
