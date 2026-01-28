"""
Simple setup verification script
"""

import os
import sys

def check_file(filename):
    """Check if a file exists"""
    exists = os.path.exists(filename)
    symbol = "✅" if exists else "❌"
    print(f"{symbol} {filename}")
    return exists

def check_env_var(var_name):
    """Check if environment variable is set in .env"""
    try:
        with open('.env', 'r') as f:
            content = f.read()
            exists = var_name in content and f"{var_name}=" in content
            symbol = "✅" if exists else "❌"
            print(f"{symbol} {var_name} configured")
            return exists
    except:
        return False

print("="*60)
print("  TELEGRAM FEEDBACK BOT - SETUP VERIFICATION")
print("="*60)

print("\n📁 Checking Core Files...")
files_ok = all([
    check_file('bot.py'),
    check_file('config.py'),
    check_file('database.py'),
    check_file('keyboards.py'),
    check_file('scheduler.py'),
    check_file('requirements.txt'),
    check_file('.env')
])

print("\n⚙️  Checking Configuration...")
config_ok = all([
    check_env_var('BOT_TOKEN'),
    check_env_var('ADMIN_ID'),
    check_env_var('MANAGER_IDS'),
    check_env_var('MANAGER_PASSWORDS'),
    check_env_var('MONGODB_URI'),
    check_env_var('DATABASE_NAME')
])

print("\n📚 Checking Documentation...")
docs_ok = all([
    check_file('README.md'),
    check_file('QUICKSTART.md'),
    check_file('PROJECT_STRUCTURE.md')
])

print("\n🔧 Checking Utilities...")
utils_ok = all([
    check_file('run.bat'),
    check_file('run.sh'),
    check_file('test_requirements.py')
])

print("\n" + "="*60)
if files_ok and config_ok and docs_ok and utils_ok:
    print("✅ ALL CHECKS PASSED!")
    print("\n📋 Next Steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run full tests: python test_requirements.py")
    print("3. Start the bot: python bot.py")
    print("\n📖 Read QUICKSTART.md for detailed instructions")
else:
    print("❌ SOME CHECKS FAILED!")
    print("\nPlease ensure all files are present and .env is configured.")

print("="*60)
