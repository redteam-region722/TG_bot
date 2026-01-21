import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
MANAGER_IDS = [int(id.strip()) for id in os.getenv('MANAGER_IDS', '').split(',') if id.strip()]
MANAGER_PASSWORDS = [pwd.strip() for pwd in os.getenv('MANAGER_PASSWORDS', '').split(',') if pwd.strip()]
CHANNEL_IDS = [ch.strip() for ch in os.getenv('CHANNEL_IDS', '').split(',') if ch.strip()]

# Server Names
SERVER_NAMES = ['Server 1', 'Server 2', 'Server 3']

# MongoDB Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'management')

# Secret Key
SECRET_KEY = os.getenv('SECRET_KEY', 'secret')

# Feedback Schedule Times (24-hour format)
FEEDBACK_TIMES = ['09:00', '12:00', '15:00', '18:00', '21:00']

# Timezone - IST (India Standard Time)
TIMEZONE = 'Asia/Kolkata'
