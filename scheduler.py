import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import get_all_subscribers, save_sunday_cache, clear_sunday_cache
from agent import run_digest_for_user
from mailer import send_weekend_email

logger = logging.getLogger("scheduler")
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")


async def run_saturday_dispatch():
    """Runs every Saturday at 9:00 AM: searches week's news, emails #1, caches #2 for Sunday."""
    subscribers = get_all_subscribers()
    logger.info(f"Starting Saturday dispatch for {len(subscribers)} subscribers...")
    for sub in subscribers:
        email = sub["email"]
        try:
            digest = await run_digest_for_user(email, sub["api_key"])
            send_weekend_email(email, "SATURDAY", "#1 TOP PICK OF THE WEEK", digest["saturday"])
            save_sunday_cache(email, digest["sunday"])
            logger.info(f"Saturday email sent & Sunday pick cached for {email}")
        except Exception as e:
            logger.error(f"Failed Saturday job for {email}: {e}")


async def run_sunday_dispatch():
    """Runs every Sunday at 9:00 AM: sends cached #2 pick using ZERO API calls."""
    subscribers = get_all_subscribers()
    logger.info(f"Starting Sunday dispatch for {len(subscribers)} subscribers...")
    for sub in subscribers:
        email = sub["email"]
        sunday_item = sub.get("cached_sunday")
        try:
            if not sunday_item:
                # Fallback if user signed up late Saturday night
                digest = await run_digest_for_user(email, sub["api_key"])
                sunday_item = digest["sunday"]

            send_weekend_email(email, "SUNDAY", "#2 RUNNER-UP OF THE WEEK", sunday_item)
            clear_sunday_cache(email)
            logger.info(f"Sunday email sent for {email}")
        except Exception as e:
            logger.error(f"Failed Sunday job for {email}: {e}")


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    # Saturday 09:00 AM
    scheduler.add_job(run_saturday_dispatch, CronTrigger(day_of_week="sat", hour=9, minute=0))
    # Sunday 09:00 AM
    scheduler.add_job(run_sunday_dispatch, CronTrigger(day_of_week="sun", hour=9, minute=0))
    scheduler.start()
    return scheduler