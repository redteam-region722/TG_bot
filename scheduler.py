from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pytz
import config
from pending_post_processor import PendingPostProcessor

class PostScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(config.TIMEZONE))
        self.pending_processor = PendingPostProcessor(bot)
    
    def start(self):
        """Start the scheduler"""
        # Add pending post processor (runs every minute)
        self.scheduler.add_job(
            self.pending_processor.process_pending_posts,
            trigger=IntervalTrigger(minutes=1),
            id='pending_post_processor',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("Scheduler started")
        print("Pending post processor started (runs every minute)")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        print("Scheduler stopped")
