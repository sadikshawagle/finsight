"""
Orchestrates the full pipeline:
  1. Fetch news from all sources
  2. Skip already-processed articles (dedup by hash)
  3. Analyze with Groq AI
  4. Cross-check: if new signal contradicts an existing signal for same ticker → resolve conflict
  5. Write valid signals to the database
  6. Update hourly chart snapshot
"""
import json
import logging
from datetime import datetime, timedelta
import pytz

from database import SessionLocal, Signal, ChartSnapshot
from services.news_aggregator import fetch_all_news
from services.claude_analyzer import analyze_article

log  = logging.getLogger(__name__)
AEST = pytz.timezone("Australia/Sydney")

VALID_SIGNALS = {"BUY", "SELL", "AVOID", "WATCH"}
VALID_MARKETS = {"ASX", "US", "CRYPTO", "COMMODITY"}

# Signals that directly contradict each other
CONFLICTS = {
    "BUY":  {"SELL"},
    "SELL": {"BUY"},
}

# How far back to look for conflicting signals (hours)
CONFLICT_WINDOW_HOURS = 24


def _find_conflict(db, tickers: list, new_signal: str) -> Signal | None:
    """
    Return the most recent active conflicting signal for any of these tickers,
    within the conflict window. Returns None if no conflict.
    """
    conflicting_types = CONFLICTS.get(new_signal, set())
    if not conflicting_types:
        return None

    cutoff = datetime.utcnow() - timedelta(hours=CONFLICT_WINDOW_HOURS)

    for existing in (
        db.query(Signal)
        .filter(Signal.is_active == True, Signal.ingested_at >= cutoff)
        .order_by(Signal.ingested_at.desc())
        .all()
    ):
        try:
            existing_tickers = set(json.loads(existing.tickers or "[]"))
        except Exception:
            continue
        if existing_tickers & set(tickers) and existing.signal in conflicting_types:
            return existing
    return None


def _resolve_conflict(db, existing: Signal, new_result: dict,
                      new_article: dict, new_signal: str, new_conf: float):
    """
    Two sources disagree on the same ticker. Resolution rules:
    - If new confidence is clearly higher (>15% gap) → retire old, save new with conflict note
    - If confidence is similar → retire both, save a WATCH with 'sources conflict' note
    - If new confidence is clearly lower → skip new signal entirely, return None
    Returns the resolved signal dict to save, or None to skip.
    """
    old_conf = existing.confidence
    gap      = new_conf - old_conf

    tickers_str = ", ".join(json.loads(existing.tickers or "[]"))
    conflict_note = (
        f"⚠ Conflicting sources: one article says {existing.signal}, "
        f"another says {new_signal} for {tickers_str}. "
        f"Confidence gap: {abs(gap):.0%}. "
    )

    if gap > 0.15:
        # New signal is much more confident — retire old, keep new with note
        existing.is_active = False
        db.commit()
        log.info(f"Conflict resolved: retired [{existing.signal}] in favour of [{new_signal}] "
                 f"(conf {old_conf:.0%} → {new_conf:.0%}) for {tickers_str}")
        new_result["reasoning"]    = conflict_note + "The newer source has higher credibility. " + new_result.get("reasoning", "")
        new_result["signal_logic"] = f"Overrides earlier {existing.signal} signal — stronger evidence"
        return new_result

    elif gap < -0.15:
        # Old signal is much more confident — skip new signal
        log.info(f"Conflict: kept [{existing.signal}] over [{new_signal}] — old conf {old_conf:.0%} > new {new_conf:.0%} for {tickers_str}")
        return None

    else:
        # Both roughly equal confidence — retire old, save WATCH with explanation
        existing.is_active = False
        db.commit()
        log.info(f"Conflict: {existing.signal} vs {new_signal} for {tickers_str} — downgrading both to WATCH")
        new_result["signal"]       = "WATCH"
        new_result["confidence"]   = round((old_conf + new_conf) / 2, 2)
        new_result["signal_logic"] = f"Sources split: {existing.signal} vs {new_signal} — wait for clarity"
        new_result["reasoning"]    = (
            conflict_note +
            "Because credible sources disagree, this signal is marked WATCH. "
            "Wait until one side of the story is confirmed before acting. " +
            new_result.get("reasoning", "")
        )
        new_result["summary"] = (
            f"Mixed signals for {tickers_str} — one source says {existing.signal}, "
            f"another says {new_signal}. Do not act until the picture is clearer."
        )
        return new_result


def process_new_articles(max_articles: int = 0) -> int:
    """Main pipeline. Returns count of new signals generated.
    max_articles=0 means no limit (local/dev). Set to 1 for Vercel serverless."""
    db        = SessionLocal()
    articles  = fetch_all_news()
    new_count = 0
    processed = 0

    for article in articles:
        if max_articles and processed >= max_articles:
            break
        try:
            # Skip if already in DB
            existing_hash = db.query(Signal).filter(
                Signal.news_hash == article["news_hash"]
            ).first()
            if existing_hash:
                continue

            # Analyze with Groq
            result = analyze_article(article)
            if not result:
                continue
            if not result.get("relevant", True):
                log.debug(f"Skipped (irrelevant): {article['title'][:60]}")
                continue

            signal_type = result.get("signal", "").upper()
            market      = result.get("market", "").upper()
            tickers     = result.get("tickers", [])
            confidence  = min(max(float(result.get("confidence", 0.5)), 0.0), 1.0)

            if signal_type not in VALID_SIGNALS:
                log.warning(f"Invalid signal '{signal_type}' — skipping")
                continue
            if market not in VALID_MARKETS:
                log.warning(f"Invalid market '{market}' — skipping")
                continue
            if not tickers:
                log.debug(f"No tickers extracted — skipping: {article['title'][:60]}")
                continue

            # ── Cross-source conflict check ──────────────────────────────────
            conflict = _find_conflict(db, tickers, signal_type)
            if conflict:
                result = _resolve_conflict(db, conflict, result, article, signal_type, confidence)
                if result is None:
                    continue  # weaker signal, skip entirely
                # Resolution may have changed signal/confidence
                signal_type = result.get("signal", signal_type).upper()
                confidence  = min(max(float(result.get("confidence", confidence)), 0.0), 1.0)

            row = Signal(
                news_hash      = article["news_hash"],
                title          = article["title"],
                source         = article["source"],
                source_domain  = article["source_domain"],
                credibility    = article["credibility"],
                published_at   = article["published_at"],
                signal         = signal_type,
                confidence     = confidence,
                impact         = min(max(float(result.get("impact", 0.0)), -1.0), 1.0),
                tickers        = json.dumps(tickers),
                market         = market,
                summary        = result.get("summary", ""),
                reasoning      = result.get("reasoning", ""),
                signal_logic   = result.get("signal_logic", ""),
                pump_dump_risk = result.get("pump_dump_risk", "LOW").upper(),
                is_twitter     = article.get("is_twitter", False),
                twitter_handle = article.get("twitter_handle"),
            )
            db.add(row)
            db.commit()
            new_count += 1
            processed += 1
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
