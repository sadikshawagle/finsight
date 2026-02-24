"""
Monitors a curated list of market-moving Twitter/X accounts.
Only includes tweets with significant engagement (100+ likes/RTs).
All Twitter signals are clearly labelled with source handle.
Requires TWITTER_BEARER_TOKEN in .env (Phase 4 — optional for now).
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from config import settings

log = logging.getLogger(__name__)

# Load curated influencer list
_config_path = Path(__file__).parent.parent / "config" / "influencers.json"
try:
    with open(_config_path) as f:
        INFLUENCERS = json.load(f)
except FileNotFoundError:
    INFLUENCERS = []
    log.warning("influencers.json not found — Twitter monitoring disabled")


def fetch_influencer_tweets() -> list[dict]:
    """Fetch recent high-engagement tweets from curated market influencers."""
    if not settings.TWITTER_BEARER_TOKEN:
        log.info("No TWITTER_BEARER_TOKEN set — skipping Twitter fetch")
        return []

    try:
        import tweepy
        client = tweepy.Client(bearer_token=settings.TWITTER_BEARER_TOKEN)
    except ImportError:
        log.warning("tweepy not installed")
        return []

    articles = []

    for influencer in INFLUENCERS:
        handle     = influencer.get("handle", "")
        twitter_id = influencer.get("twitter_id", "")
        cred       = influencer.get("credibility", 0.70)

        if not twitter_id:
            continue

        try:
            tweets = client.get_users_tweets(
                id           = twitter_id,
                max_results  = 5,
                tweet_fields = ["created_at", "text", "public_metrics"],
                exclude      = ["retweets", "replies"],
            )
            if not tweets.data:
                continue

            for tweet in tweets.data:
                metrics = tweet.public_metrics or {}
                engagement = metrics.get("like_count", 0) + metrics.get("retweet_count", 0)

                # Only process high-engagement tweets (>100 combined)
                if engagement < 100:
                    continue

                pub_time = tweet.created_at.replace(tzinfo=None) \
                           if tweet.created_at else datetime.utcnow()

                articles.append({
                    "news_hash":     f"tw_{tweet.id}",
                    "title":         f"@{handle}: {tweet.text[:150]}",
                    "source":        f"Twitter (@{handle})",
                    "source_domain": "twitter.com",
                    "credibility":   cred,
                    "published_at":  pub_time,
                    "content":       tweet.text,
                    "url":           f"https://x.com/{handle}/status/{tweet.id}",
                    "is_twitter":    True,
                    "twitter_handle": handle,
                })

        except Exception as e:
            log.warning(f"Twitter fetch failed for @{handle}: {e}")

    log.info(f"Twitter: {len(articles)} qualifying tweets fetched")
    return articles
