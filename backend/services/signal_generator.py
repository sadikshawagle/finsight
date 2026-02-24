"""
Orchestrates the full pipeline:
  1. Fetch news from all sources
  2. Skip already-processed articles (dedup by hash)
  3. Analyze with Claude
  4. Write valid signals to the database
  5. Update hourly chart snapshot
"""
import json
import logging
from datetime import datetime
import pytz

from database import SessionLocal, Signal, ChartSnapshot
from services.news_aggregator import fetch_all_news
from services.claude_analyzer import analyze_article

log  = logging.getLogger(__name__)
AEST = pytz.timezone("Australia/Sydney")

VALID_SIGNALS = {"BUY", "SELL", "AVOID", "WATCH"}
VALID_MARKETS = {"ASX", "US", "CRYPTO", "COMMODITY"}


def process_new_articles() -> int:
    """Main scheduled job. Returns count of new signals generated."""
    db       = SessionLocal()
    articles = fetch_all_news()
    new_count = 0

    for article in articles:
        try:
            # Skip if already in DB
            existing = db.query(Signal).filter(
                Signal.news_hash == article["news_hash"]
            ).first()
            if existing:
                continue

            # Analyze with Claude
            result = analyze_article(article)
            if not result:
                continue
            if not result.get("relevant", True):
                log.debug(f"Skipped (irrelevant): {article['title'][:60]}")
                continue

            signal_type = result.get("signal", "").upper()
            market      = result.get("market", "").upper()
            tickers     = result.get("tickers", [])

            if signal_type not in VALID_SIGNALS:
                log.warning(f"Invalid signal '{signal_type}' — skipping")
                continue
            if market not in VALID_MARKETS:
                log.warning(f"Invalid market '{market}' — skipping")
                continue
            if not tickers:
                log.debug(f"No tickers extracted — skipping: {article['title'][:60]}")
                continue

            row = Signal(
                news_hash      = article["news_hash"],
                title          = article["title"],
                source         = article["source"],
                source_domain  = article["source_domain"],
                credibility    = article["credibility"],
                published_at   = article["published_at"],
                signal         = signal_type,
                confidence     = min(max(float(result.get("confidence", 0.5)), 0.0), 1.0),
                impact         = min(max(float(result.get("impact", 0.0)), -1.0), 1.0),
                tickers        = json.dumps(tickers),
                market         = market,
                summary        = result.get("summary", ""),
                reasoning      = result.get("reasoning", ""),
                signal_logic   = result.get("signal_logic", ""),
                is_twitter     = article.get("is_twitter", False),
                twitter_handle = article.get("twitter_handle"),
            )
            db.add(row)
            db.commit()
            new_count += 1
            log.info(f"[{signal_type}] {article['title'][:70]}")

        except Exception as e:
            log.error(f"Error processing article: {e}")
            db.rollback()

    _update_chart_snapshot(db)
    db.close()
    log.info(f"Pipeline complete: {len(articles)} articles → {new_count} new signals")
    return new_count


def _update_chart_snapshot(db):
    """Record signal counts for the current hour (for the chart tab)."""
    try:
        now        = datetime.now(AEST)
        hour_label = now.strftime("%-I%p")   # e.g. "9AM", "2PM"

        counts = {"BUY": 0, "SELL": 0, "AVOID": 0, "WATCH": 0}
        rows   = db.query(Signal).filter(Signal.is_active == True).all()
        for r in rows:
            if r.signal in counts:
                counts[r.signal] += 1

        snap = ChartSnapshot(
            snapshot_hour = hour_label,
            buy_count     = counts["BUY"],
            sell_count    = counts["SELL"],
            avoid_count   = counts["AVOID"],
            watch_count   = counts["WATCH"],
        )
        db.add(snap)
        db.commit()
    except Exception as e:
        log.warning(f"Chart snapshot failed: {e}")
        db.rollback()
