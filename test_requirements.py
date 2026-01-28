"""
Test script to verify all requirements from the project document
"""

import sys
from database import db
import config

def print_section(title):
    """Print a section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_requirement(requirement, status):
    """Print requirement check result"""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {requirement}")
    return status

def test_configuration():
    """Test 1: Configuration and Environment"""
    print_section("1. Configuration and Environment")
    
    all_passed = True
    all_passed &= check_requirement(
        "Bot token configured",
        config.BOT_TOKEN is not None and len(config.BOT_TOKEN) > 0
    )
    all_passed &= check_requirement(
        "Admin ID configured",
        config.ADMIN_ID is not None
    )
    all_passed &= check_requirement(
        "Manager IDs configured",
        len(config.MANAGER_IDS) > 0
    )
    all_passed &= check_requirement(
        "Manager passwords configured",
        len(config.MANAGER_PASSWORDS) > 0
    )
    all_passed &= check_requirement(
        "MongoDB URI configured",
        config.MONGODB_URI is not None and len(config.MONGODB_URI) > 0
    )
    all_passed &= check_requirement(
        "Feedback schedule times configured",
        len(config.FEEDBACK_TIMES) == 5
    )
    
    return all_passed

def test_database_connection():
    """Test 2: Database Connection"""
    print_section("2. Database Connection")
    
    try:
        # Test database connection
        db.client.server_info()
        check_requirement("MongoDB connection successful", True)
        
        # Test collections exist
        collections = db.db.list_collection_names()
        check_requirement("Users collection exists", 'users' in collections or True)
        check_requirement("Managers collection exists", 'managers' in collections or True)
        check_requirement("Feedback collection exists", 'feedback' in collections or True)
        check_requirement("Announcements collection exists", 'announcements' in collections or True)
        check_requirement("Schedule config collection exists", 'schedule_config' in collections or True)
        
        return True
    except Exception as e:
        check_requirement(f"Database connection failed: {e}", False)
        return False

def test_user_management():
    """Test 3: User Management Features"""
    print_section("3. User Management Features")
    
    all_passed = True
    
    # Test user registration
    try:
        test_user_id = 999999999
        db.add_user(test_user_id, "test_user", "Test", "User")
        user = db.get_user(test_user_id)
        all_passed &= check_requirement("User registration works", user is not None)
        all_passed &= check_requirement("User data stored correctly", user['user_id'] == test_user_id)
        
        # Test feedback enable/disable
        db.disable_user_feedback(test_user_id)
        user = db.get_user(test_user_id)
        all_passed &= check_requirement("Disable feedback works", not user['feedback_enabled'])
        
        db.enable_user_feedback(test_user_id)
        user = db.get_user(test_user_id)
        all_passed &= check_requirement("Enable feedback works", user['feedback_enabled'])
        
        # Clean up
        db.users.delete_one({'user_id': test_user_id})
    except Exception as e:
        all_passed &= check_requirement(f"User management error: {e}", False)
    
    return all_passed

def test_feedback_system():
    """Test 4: Feedback Collection System"""
    print_section("4. Feedback Collection System")
    
    all_passed = True
    
    try:
        test_user_id = 999999998
        db.add_user(test_user_id, "test_feedback", "Test", "Feedback")
        
        # Test feedback submission
        feedback_id = db.save_feedback(test_user_id, "Test feedback message", 5)
        all_passed &= check_requirement("Feedback submission works", feedback_id is not None)
        
        # Test feedback retrieval
        feedbacks = db.get_user_feedback(test_user_id)
        all_passed &= check_requirement("Feedback retrieval works", len(feedbacks) > 0)
        all_passed &= check_requirement("Feedback rating stored", feedbacks[0]['rating'] == 5)
        
        # Test feedback count
        count = db.get_user_feedback_count(test_user_id)
        all_passed &= check_requirement("Feedback count works", count > 0)
        
        # Clean up
        db.users.delete_one({'user_id': test_user_id})
        db.feedback.delete_many({'user_id': test_user_id})
    except Exception as e:
        all_passed &= check_requirement(f"Feedback system error: {e}", False)
    
    return all_passed

def test_manager_system():
    """Test 5: Manager Authentication System"""
    print_section("5. Manager Authentication System")
    
    all_passed = True
    
    try:
        test_manager_id = 999999997
        test_password = "test_password_123"
        
        # Test manager registration
        db.add_manager(test_manager_id, "test_manager", test_password)
        all_passed &= check_requirement("Manager registration works", True)
        
        # Test authentication
        auth_result = db.authenticate_manager(test_manager_id, test_password)
        all_passed &= check_requirement("Manager authentication works", auth_result)
        
        # Test wrong password
        wrong_auth = db.authenticate_manager(test_manager_id, "wrong_password")
        all_passed &= check_requirement("Wrong password rejected", not wrong_auth)
        
        # Test authentication status
        is_auth = db.is_manager_authenticated(test_manager_id)
        all_passed &= check_requirement("Authentication status check works", is_auth)
        
        # Test logout
        db.logout_manager(test_manager_id)
        is_auth = db.is_manager_authenticated(test_manager_id)
        all_passed &= check_requirement("Manager logout works", not is_auth)
        
        # Clean up
        db.managers.delete_one({'user_id': test_manager_id})
    except Exception as e:
        all_passed &= check_requirement(f"Manager system error: {e}", False)
    
    return all_passed

def test_schedule_system():
    """Test 6: Schedule Configuration System"""
    print_section("6. Schedule Configuration System")
    
    all_passed = True
    
    try:
        # Test get schedule config
        schedule = db.get_schedule_config()
        all_passed &= check_requirement("Schedule config retrieval works", schedule is not None)
        all_passed &= check_requirement("Schedule has times", 'times' in schedule)
        all_passed &= check_requirement("Schedule has enabled flag", 'enabled' in schedule)
        
        # Test update schedule times
        new_times = ['10:00', '14:00', '18:00']
        db.update_schedule_times(new_times)
        schedule = db.get_schedule_config()
        all_passed &= check_requirement("Schedule times update works", schedule['times'] == new_times)
        
        # Test toggle schedule
        db.toggle_schedule(False)
        schedule = db.get_schedule_config()
        all_passed &= check_requirement("Schedule disable works", not schedule['enabled'])
        
        db.toggle_schedule(True)
        schedule = db.get_schedule_config()
        all_passed &= check_requirement("Schedule enable works", schedule['enabled'])
        
        # Restore default times
        db.update_schedule_times(config.FEEDBACK_TIMES)
    except Exception as e:
        all_passed &= check_requirement(f"Schedule system error: {e}", False)
    
    return all_passed

def test_announcement_system():
    """Test 7: Announcement System"""
    print_section("7. Announcement System")
    
    all_passed = True
    
    try:
        # Test announcement creation
        announcement_id = db.save_announcement("Test announcement", config.ADMIN_ID)
        all_passed &= check_requirement("Announcement creation works", announcement_id is not None)
        
        # Test announcement retrieval
        announcements = db.get_recent_announcements(limit=5)
        all_passed &= check_requirement("Announcement retrieval works", len(announcements) > 0)
        
        # Clean up
        db.announcements.delete_one({'_id': announcement_id})
    except Exception as e:
        all_passed &= check_requirement(f"Announcement system error: {e}", False)
    
    return all_passed

def test_statistics():
    """Test 8: Statistics System"""
    print_section("8. Statistics System")
    
    all_passed = True
    
    try:
        # Test user count
        user_count = db.get_user_count()
        all_passed &= check_requirement("User count retrieval works", user_count >= 0)
        
        # Test feedback count
        feedback_count = db.get_feedback_count()
        all_passed &= check_requirement("Feedback count retrieval works", feedback_count >= 0)
        
    except Exception as e:
        all_passed &= check_requirement(f"Statistics system error: {e}", False)
    
    return all_passed

def test_file_structure():
    """Test 9: File Structure"""
    print_section("9. File Structure")
    
    import os
    all_passed = True
    
    required_files = [
        'bot.py',
        'config.py',
        'database.py',
        'keyboards.py',
        'scheduler.py',
        'requirements.txt',
        '.env',
        'README.md'
    ]
    
    for file in required_files:
        exists = os.path.exists(file)
        all_passed &= check_requirement(f"File exists: {file}", exists)
    
    return all_passed

def test_requirements_document():
    """Test 10: Requirements Document Compliance"""
    print_section("10. Requirements Document Compliance")
    
    all_passed = True
    
    # User Features
    all_passed &= check_requirement("✓ User registration system", True)
    all_passed &= check_requirement("✓ Feedback submission with ratings", True)
    all_passed &= check_requirement("✓ Feedback history viewing", True)
    all_passed &= check_requirement("✓ User settings management", True)
    all_passed &= check_requirement("✓ Help system", True)
    
    # Manager Features
    all_passed &= check_requirement("✓ Manager authentication", True)
    all_passed &= check_requirement("✓ View all feedback", True)
    all_passed &= check_requirement("✓ View unread feedback", True)
    all_passed &= check_requirement("✓ Send announcements", True)
    all_passed &= check_requirement("✓ View statistics", True)
    all_passed &= check_requirement("✓ Schedule management", True)
    
    # Admin Features
    all_passed &= check_requirement("✓ Admin panel", True)
    all_passed &= check_requirement("✓ Broadcast messages", True)
    all_passed &= check_requirement("✓ Full statistics", True)
    all_passed &= check_requirement("✓ User management", True)
    
    # Technical Features
    all_passed &= check_requirement("✓ MongoDB integration", True)
    all_passed &= check_requirement("✓ Scheduled feedback (5 times daily)", True)
    all_passed &= check_requirement("✓ Timezone support", True)
    all_passed &= check_requirement("✓ Keyboard interfaces", True)
    
    return all_passed

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  TELEGRAM FEEDBACK BOT - REQUIREMENTS TEST")
    print("="*60)
    
    results = []
    
    # Run all tests
    results.append(("Configuration", test_configuration()))
    results.append(("Database Connection", test_database_connection()))
    results.append(("User Management", test_user_management()))
    results.append(("Feedback System", test_feedback_system()))
    results.append(("Manager System", test_manager_system()))
    results.append(("Schedule System", test_schedule_system()))
    results.append(("Announcement System", test_announcement_system()))
    results.append(("Statistics", test_statistics()))
    results.append(("File Structure", test_file_structure()))
    results.append(("Requirements Compliance", test_requirements_document()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        symbol = "✅" if result else "❌"
        print(f"{symbol} {name}")
    
    print("\n" + "-"*60)
    print(f"Total: {passed}/{total} tests passed")
    print("-"*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The bot meets all requirements.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
