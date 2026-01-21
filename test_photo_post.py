"""
Test script to check photo posting functionality
"""
from database import db
from datetime import datetime

print("=" * 60)
print("  PHOTO POST DEBUGGING")
print("=" * 60)

# Check server configurations
print("\n1. Server Configurations:")
for i in range(1, 4):
    config = db.get_server_config(i)
    print(f"\nServer {i}:")
    print(f"  - Footer: {config.get('footer_text', 'Not set')[:50]}")
    print(f"  - Button 1: {config.get('button1_text', 'Not set')}")
    print(f"  - Button 2: {config.get('button2_text', 'Not set')}")
    print(f"  - Time Gap: {config.get('min_time_gap', 30)} minutes")
    
    # Check if can post now
    can_post, remaining = db.can_post_now(i)
    if can_post:
        print(f"  - Status: ✅ Ready to post")
    else:
        print(f"  - Status: ⏳ Wait {remaining} minutes")
    
    # Check last post
    last_post = db.get_last_post(i)
    if last_post:
        print(f"  - Last post: {last_post['posted_at']}")
        print(f"  - Has photo: {'Yes' if last_post.get('photo_id') else 'No'}")
    else:
        print(f"  - Last post: None")

# Check pending posts
print("\n2. Pending Posts:")
for i in range(1, 4):
    pending = db.get_pending_posts_by_server(i)
    print(f"\nServer {i}: {len(pending)} pending posts")
    for idx, post in enumerate(pending, 1):
        print(f"  {idx}. Scheduled: {post['scheduled_time']}")
        print(f"     Has photo: {'Yes' if post.get('photo_id') else 'No'}")
        print(f"     Caption: {post.get('message_text', '[No text]')[:30]}")

# Check all posts
print("\n3. All Posts:")
total_posts = db.posts.count_documents({})
print(f"Total posts in database: {total_posts}")

for i in range(1, 4):
    server_posts = db.posts.count_documents({'server_id': i})
    photo_posts = db.posts.count_documents({'server_id': i, 'photo_id': {'$exists': True, '$ne': None}})
    text_posts = server_posts - photo_posts
    print(f"Server {i}: {server_posts} total ({photo_posts} photos, {text_posts} text)")

# Check ready to send
print("\n4. Posts Ready to Send:")
ready_posts = db.get_pending_posts_ready()
print(f"Posts ready to send now: {len(ready_posts)}")
for post in ready_posts:
    print(f"  - Server {post['server_id']}, scheduled: {post['scheduled_time']}")

print("\n" + "=" * 60)
print("  DEBUGGING TIPS")
print("=" * 60)
print("\nIf you're not seeing alerts after uploading photos:")
print("1. Check if bot is running (should see 'Bot started' in console)")
print("2. Check if you clicked 'Post to Server' first")
print("3. Check if you selected a server")
print("4. Look for error messages in bot console")
print("5. Try restarting the bot")
print("\nIf posts are being saved but no notification:")
print("1. Check bot console for errors")
print("2. Verify Telegram bot token is correct")
print("3. Check if bot has permission to send messages")
print("\n" + "=" * 60)
