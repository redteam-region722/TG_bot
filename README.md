# Telegram Bot

Telegram bot for managing posts and channels.

## Features

- Post management to multiple channels
- Manager authentication system
- Admin controls
- Scheduled posts
- Server configuration with buttons and footers

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file with:
```
BOT_TOKEN=your_bot_token
ADMIN_ID=your_admin_id
MANAGER_IDS=manager_id1,manager_id2
CHANNEL_IDS=channel1,channel2,channel3
MONGODB_URI=your_mongodb_uri
DATABASE_NAME=management
```

3. Run the bot:
```bash
# Windows
run.bat

# Linux/Mac
./run.sh
```

## Project Structure

- `bot.py` - Main bot application
- `config.py` - Configuration management
- `database.py` - MongoDB database operations
- `keyboards.py` - Telegram keyboard layouts
- `pending_post_processor.py` - Scheduled post processor
- `scheduler.py` - Background task scheduler
