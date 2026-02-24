"""
Fetches financial news from Finnhub (primary) and NewsAPI (fallback).
Filters by source credibility and deduplicates by URL hash.
Compatible with Python 3.9+
"""
from __future__ import annotations
import finnhub
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List
from config import settings, get_credibility, MIN_CREDIBILITY

log = logging.getLogger(__name__)

finnhub_client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)

# NewsAPI import (only used if key is set)
try:
    from newsapi import NewsApiClient
    newsapi_client = NewsApiClient(api_key=settings.NEWS_API_KEY) if settings.NEWS_API_KEY else None
except Exception:
    newsapi_client = None

# Finnhub categories to pull — covers stocks, M&A, crypto, macro
FINNHUB_CATEGORIES = ["general", "forex", "crypto", "merger"]

# NewsAPI finance keyword query — broad enough to catch all market-moving news
NEWSAPI_QUERY = (
    "stock OR market OR shares OR earnings OR acquisition OR merger OR "
    "bitcoin OR crypto OR gold OR oil OR Fed OR interest rate OR GDP OR inflation"
)

# Trusted domains added to credibility map (supplement config.py)
EXTRA_DOMAINS: dict[str, float] = {
    "investing.com":       0.78,
    "finance.yahoo.com":   0.75,
    "apnews.com":          0.90,
    "bbc.com":             0.88,
    "theguardian.com":     0.85,
    "nytimes.com":         0.88,
    "forbes.com":          0.78,
    "benzinga.com":        0.72,
    "zacks.com":           0.72,
    "nasdaq.com":          0.80,
    "thestreet.com":       0.74,
    "proactiveinvestors.com": 0.70,
}


def _make_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def _domain_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _get_cred(url: str) -> float:
    """Check config credibility map first, then EXTRA_DOMAINS."""
    score = get_credibility(url)
    if score == 0.60:  # default unknown
        domain = _domain_from_url(url)
        for key, val in EXTRA_DOMAINS.items():
            if domain == key or domain.endswith(key):
                return val
    return score


def _build_article(title: str, source: str, url: str, pub_time: datetime,
                   content: str, credibility: float) -> dict:
    return {
        "news_hash":      _make_hash(url or title),
        "title":          title,
        "source":         source,
        "source_domain":  _domain_from_url(url),
        "credibility":    credibility,
        "published_at":   pub_time,
        "content":        content,
        "url":            url,
        "is_twitter":     False,
        "twitter_handle": None,
    }


def fetch_finnhub_news() -> List[dict]:
    """Fetch news from multiple Finnhub categories."""
    articles  = []
    seen_urls = set()
    cutoff    = datetime.utcnow() - timedelta(hours=6)  # wider window

    for category in FINNHUB_CATEGORIES:
        try:
            raw = finnhub_client.general_news(category, min_id=0)
        except Exception as e:
            log.warning(f"Finnhub category '{category}' failed: {e}")
            continue

        for item in raw:
            try:
                pub_time = datetime.utcfromtimestamp(item.get("datetime", 0))
                if pub_time < cutoff:
                    continue

                url = item.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                credibility = _get_cred(url)
                if credibility < MIN_CREDIBILITY:
                    continue

                content = item.get("summary", "") or item.get("headline", "")
                if not content or len(content) < 30:
                    continue

                articles.append(_build_article(
                    title       = item.get("headline", ""),
                    source      = item.get("source", "Finnhub"),
                    url         = url,
                    pub_time    = pub_time,
                    content     = content,
                    credibility = credibility,
                ))
            except Exception as e:
                log.warning(f"Skipping Finnhub item: {e}")

    log.info(f"Finnhub: {len(articles)} credible articles across {len(FINNHUB_CATEGORIES)} categories")
    return articles


def fetch_newsapi_news() -> List[dict]:
    """Fetch finance news from NewsAPI using keyword search (more results than top_headlines)."""
    if not newsapi_client:
        return []

    articles = []
    cutoff   = datetime.utcnow() - timedelta(hours=6)

    try:
        # Use 'everything' endpoint with finance keywords — much more results than top_headlines
        response = newsapi_client.get_everything(
            q          = NEWSAPI_QUERY,
            language   = "en",
            sort_by    = "publishedAt",
            page_size  = 50,
        )
        raw = response.get("articles", [])
    except Exception as e:
        log.error(f"NewsAPI everything failed: {e}")
        # Fallback to top_headlines
        try:
            response = newsapi_client.get_top_headlines(
                category  = "business",
                language  = "en",
                page_size = 30,
            )
            raw = response.get("articles", [])
        except Exception as e2:
            log.error(f"NewsAPI top_headlines also failed: {e2}")
            return []

    for item in raw:
        try:
            pub_str  = item.get("publishedAt", "")
            pub_time = datetime.fromisoformat(pub_str.replace("Z", "+00:00")).replace(tzinfo=None)
            if pub_time < cutoff:
                continue

            url         = item.get("url", "")
            credibility = _get_cred(url)
            if credibility < MIN_CREDIBILITY:
                continue

            content = item.get("content") or item.get("description") or item.get("title") or ""
            if not content or len(content) < 30:
                continue

            articles.append(_build_article(
                title       = item.get("title", ""),
                source      = item.get("source", {}).get("name", "NewsAPI"),
                url         = url,
                pub_time    = pub_time,
                content     = content,
                credibility = credibility,
            ))
        except Exception as e:
            log.warning(f"Skipping NewsAPI item: {e}")

    log.info(f"NewsAPI: {len(articles)} credible articles fetched")
    return articles


def fetch_all_news() -> List[dict]:
    """Combine and deduplicate news from all sources."""
    seen_hashes = set()
    combined    = []

    for article in fetch_finnhub_news() + fetch_newsapi_news():
        h = article["news_hash"]
        if h not in seen_hashes:
            seen_hashes.add(h)
            combined.append(article)

    log.info(f"Total unique articles after dedup: {len(combined)}")
    return combined
