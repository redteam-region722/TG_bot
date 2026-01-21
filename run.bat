@echo off
echo Starting Telegram Bot...
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/update requirements
echo Installing requirements...
pip install -r requirements.txt

REM Run the bot
echo.
echo Starting bot...
python bot.py

pause
