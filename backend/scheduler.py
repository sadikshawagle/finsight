"""
Background scheduler — runs recurring jobs while the server is up.
  - News + Claude analysis: every 5 minutes
  - Price cache update:     every 60 seconds
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

log       = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="Australia/Sydney")


def _news_job():
    from services.signal_generator import process_new_articles
    try:
        count = process_new_articles()
        log.info(f"[Scheduler] News job done — {count} new signals")
    except Exception as e:
        log.error(f"[Scheduler] News job failed: {e}")


def _price_job():
    from services.price_fetcher import update_price_cache
    try:
        update_price_cache()
    except Exception as e:
        log.error(f"[Scheduler] Price job failed: {e}")


def start_scheduler():
    scheduler.add_job(_news_job,  "interval", minutes=5,  id="news_analysis", replace_existing=True)
    scheduler.add_job(_price_job, "interval", seconds=60, id="price_update",  replace_existing=True)
    scheduler.start()
    log.info("Scheduler started: news every 5 min | prices every 60 sec")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        log.info("Scheduler stopped")
