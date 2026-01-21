from pymongo import MongoClient
from datetime import datetime
import config

class Database:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client[config.DATABASE_NAME]
        
        # Collections
        self.users = self.db['users']
        self.managers = self.db['managers']
        self.announcements = self.db['announcements']
        self.server_config = self.db['server_config']
        self.posts = self.db['posts']
        self.pending_posts = self.db['pending_posts']
        
        # Create indexes
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for better performance"""
        self.users.create_index('user_id', unique=True)
        self.managers.create_index('user_id', unique=True)
        self.announcements.create_index([('created_at', -1)])
        self.server_config.create_index('server_id', unique=True)
        self.posts.create_index([('server_id', 1), ('posted_at', -1)])
        self.pending_posts.create_index([('server_id', 1), ('scheduled_time', 1)])
    
    # User Management
    def add_user(self, user_id, username=None, first_name=None, last_name=None):
        """Add or update a user"""
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True
        }
        self.users.update_one(
            {'user_id': user_id},
            {
                '$set': user_data,
                '$setOnInsert': {'joined_at': datetime.utcnow()}
            },
            upsert=True
        )
    
    def get_user(self, user_id):
        """Get user by ID"""
        return self.users.find_one({'user_id': user_id})
    
    def get_all_active_users(self):
        """Get all active users"""
        return list(self.users.find({'is_active': True}))
    
    # Manager Management
    def add_manager(self, user_id, username=None, password=None):
        """Add a manager"""
        manager_data = {
            'user_id': user_id,
            'username': username,
            'password': password,
            'is_authenticated': False,
            'added_at': datetime.utcnow()
        }
        self.managers.update_one(
            {'user_id': user_id},
            {'$set': manager_data},
            upsert=True
        )
    
    def authenticate_manager(self, user_id, password):
        """Authenticate a manager"""
        manager = self.managers.find_one({'user_id': user_id})
        if manager and manager.get('password') == password:
            self.managers.update_one(
                {'user_id': user_id},
                {'$set': {'is_authenticated': True}}
            )
            return True
        return False
    
    def is_manager_authenticated(self, user_id):
        """Check if manager is authenticated"""
        manager = self.managers.find_one({'user_id': user_id})
        return manager and manager.get('is_authenticated', False)
    
    def logout_manager(self, user_id):
        """Logout a manager"""
        self.managers.update_one(
            {'user_id': user_id},
            {'$set': {'is_authenticated': False}}
        )
    
    def get_all_managers(self):
        """Get all managers"""
        return list(self.managers.find().sort('added_at', -1))
    
    def remove_manager(self, user_id):
        """Remove a manager"""
        self.managers.delete_one({'user_id': user_id})
    
    def update_manager_password(self, user_id, password):
        """Update manager password"""
        self.managers.update_one(
            {'user_id': user_id},
            {'$set': {'password': password}}
        )
    
    def get_manager(self, user_id):
        """Get manager by ID"""
        return self.managers.find_one({'user_id': user_id})
    
    # Announcement Management
    def save_announcement(self, text, created_by):
        """Save an announcement"""
        announcement_data = {
            'text': text,
            'created_by': created_by,
            'created_at': datetime.utcnow(),
            'sent_to_users': []
        }
        return self.announcements.insert_one(announcement_data).inserted_id
    
    def get_recent_announcements(self, limit=10):
        """Get recent announcements"""
        return list(self.announcements.find().sort('created_at', -1).limit(limit))
    
    # Statistics
    def get_user_count(self):
        """Get total user count"""
        return self.users.count_documents({'is_active': True})
    
    # Server Configuration Management
    def get_server_config(self, server_id):
        """Get configuration for a specific server"""
        config = self.server_config.find_one({'server_id': server_id})
        if not config:
            # Create default config
            config = {
                'server_id': server_id,
                'server_name': f'Server {server_id}',
                'footer_text': '',
                'button1_text': '',
                'button1_url': '',
                'button2_text': '',
                'button2_url': '',
                'min_time_gap': 30,  # minutes
                'enabled': True,
                'posting_enabled': True
            }
            self.server_config.insert_one(config)
        return config
    
    def get_all_server_configs(self):
        """Get all server configurations"""
        configs = []
        for i in range(1, 4):  # 3 servers
            configs.append(self.get_server_config(i))
        return configs
    
    def update_server_config(self, server_id, config_data):
        """Update server configuration"""
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': config_data},
            upsert=True
        )
    
    def update_server_footer(self, server_id, footer_text):
        """Update server footer text"""
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': {'footer_text': footer_text}},
            upsert=True
        )
    
    def update_server_button(self, server_id, button_num, text, url):
        """Update server button"""
        field_text = f'button{button_num}_text'
        field_url = f'button{button_num}_url'
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': {field_text: text, field_url: url}},
            upsert=True
        )
    
    def update_server_time_gap(self, server_id, minutes):
        """Update minimum time gap for server"""
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': {'min_time_gap': minutes}},
            upsert=True
        )
    
    def enable_server_posting(self, server_id):
        """Enable posting permission for a server"""
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': {'posting_enabled': True}},
            upsert=True
        )
    
    def disable_server_posting(self, server_id):
        """Disable posting permission for a server"""
        self.server_config.update_one(
            {'server_id': server_id},
            {'$set': {'posting_enabled': False}},
            upsert=True
        )
    
    def is_server_posting_enabled(self, server_id):
        """Check if posting is enabled for a server"""
        config = self.get_server_config(server_id)
        return config.get('posting_enabled', True)
    
    # Post Management
    def save_post(self, server_id, user_id, message_text, channel_message_id=None, photo_id=None):
        """Save a post record"""
        post_data = {
            'server_id': server_id,
            'user_id': user_id,
            'message_text': message_text,
            'photo_id': photo_id,
            'channel_message_id': channel_message_id,
            'posted_at': datetime.utcnow()
        }
        return self.posts.insert_one(post_data).inserted_id
    
    def get_last_post(self, server_id):
        """Get the last post for a server"""
        return self.posts.find_one(
            {'server_id': server_id},
            sort=[('posted_at', -1)]
        )
    
    def can_post_now(self, server_id):
        """Check if enough time has passed since last post"""
        config = self.get_server_config(server_id)
        min_gap = config.get('min_time_gap', 30)
        
        last_post = self.get_last_post(server_id)
        if not last_post:
            return True, 0
        
        time_since_last = datetime.utcnow() - last_post['posted_at']
        minutes_passed = time_since_last.total_seconds() / 60
        
        if minutes_passed >= min_gap:
            return True, 0
        else:
            remaining = min_gap - minutes_passed
            return False, int(remaining)
    
    def get_scheduled_post_time(self, server_id):
        """Calculate when the next post can be made"""
        config = self.get_server_config(server_id)
        min_gap = config.get('min_time_gap', 30)
        
        last_post = self.get_last_post(server_id)
        if not last_post:
            return datetime.utcnow()
        
        from datetime import timedelta
        scheduled_time = last_post['posted_at'] + timedelta(minutes=min_gap)
        
        # If scheduled time is in the past, return now
        if scheduled_time < datetime.utcnow():
            return datetime.utcnow()
        
        return scheduled_time
    
    # Pending Posts Management
    def save_pending_post(self, server_id, user_id, message_text, scheduled_time, photo_id=None, caption=None):
        """Save a pending post to be sent later"""
        pending_data = {
            'server_id': server_id,
            'user_id': user_id,
            'message_text': message_text,
            'photo_id': photo_id,
            'caption': caption,
            'scheduled_time': scheduled_time,
            'created_at': datetime.utcnow(),
            'status': 'pending'
        }
        return self.pending_posts.insert_one(pending_data).inserted_id
    
    def check_time_conflict(self, server_id, proposed_time):
        """Check if proposed time conflicts with existing scheduled posts"""
        config = self.get_server_config(server_id)
        min_gap = config.get('min_time_gap', 30)
        
        from datetime import timedelta
        
        # Check pending posts
        pending_posts = self.get_pending_posts_by_server(server_id)
        
        for post in pending_posts:
            existing_time = post['scheduled_time']
            time_diff = abs((proposed_time - existing_time).total_seconds() / 60)
            
            if time_diff < min_gap:
                # Conflict found - suggest next available time
                next_available = existing_time + timedelta(minutes=min_gap)
                return False, next_available
        
        # Check last posted time
        last_post = self.get_last_post(server_id)
        if last_post:
            last_time = last_post['posted_at']
            time_diff = abs((proposed_time - last_time).total_seconds() / 60)
            
            if time_diff < min_gap:
                next_available = last_time + timedelta(minutes=min_gap)
                return False, next_available
        
        return True, None
    
    def get_pending_posts_ready(self):
        """Get all pending posts that are ready to be sent"""
        return list(self.pending_posts.find({
            'status': 'pending',
            'scheduled_time': {'$lte': datetime.utcnow()}
        }).sort('scheduled_time', 1))
    
    def get_pending_posts_by_server(self, server_id):
        """Get all pending posts for a specific server"""
        return list(self.pending_posts.find({
            'server_id': server_id,
            'status': 'pending'
        }).sort('scheduled_time', 1))
    
    def get_pending_post_count(self, server_id):
        """Get count of pending posts for a server"""
        return self.pending_posts.count_documents({
            'server_id': server_id,
            'status': 'pending'
        })
    
    def mark_pending_post_sent(self, pending_post_id):
        """Mark a pending post as sent"""
        self.pending_posts.update_one(
            {'_id': pending_post_id},
            {'$set': {'status': 'sent', 'sent_at': datetime.utcnow()}}
        )
    
    def delete_pending_post(self, pending_post_id):
        """Delete a pending post"""
        self.pending_posts.delete_one({'_id': pending_post_id})

# Global database instance
db = Database()
