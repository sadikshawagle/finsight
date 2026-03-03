#!/usr/bin/env python3
"""Quick debug script to test news fetching."""
import sys
import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# Load environment
from config import settings
print(f"GROQ_API_KEY: {'✓' if settings.GROQ_API_KEY else '✗ MISSING'}")
print(f"FINNHUB_API_KEY: {'✓' if settings.FINNHUB_API_KEY else '✗ MISSING'}")
print(f"NEWS_API_KEY: {'✓' if settings.NEWS_API_KEY else '✗ MISSING'}")
print()

# Test Finnhub
print("=" * 60)
print("Testing Finnhub...")
print("=" * 60)
try:
    from services.news_aggregator import fetch_finnhub_news
    articles = fetch_finnhub_news()
    print(f"✓ Got {len(articles)} articles from Finnhub")
    if articles:
        for a in articles[:3]:
            print(f"  - {a['title'][:70]}")
except Exception as e:
    print(f"✗ Finnhub failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test NewsAPI
print("=" * 60)
print("Testing NewsAPI...")
print("=" * 60)
try:
    from services.news_aggregator import fetch_newsapi_news
    articles = fetch_newsapi_news()
    print(f"✓ Got {len(articles)} articles from NewsAPI")
    if articles:
        for a in articles[:3]:
            print(f"  - {a['title'][:70]}")
except Exception as e:
    print(f"✗ NewsAPI failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test combined
print("=" * 60)
print("Testing overall fetch_all_news()...")
print("=" * 60)
try:
    from services.news_aggregator import fetch_all_news
    articles = fetch_all_news()
    print(f"✓ Got {len(articles)} total articles")
except Exception as e:
    print(f"✗ fetch_all_news() failed: {e}")
    import traceback
    traceback.print_exc()
