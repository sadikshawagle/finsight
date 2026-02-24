from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db, Signal
from datetime import datetime, timedelta
import json

router = APIRouter()


@router.get("/signals")
def get_signals(
    market:      Optional[str] = Query(None, description="Filter: ASX US CRYPTO COMMODITY"),
    signal_type: Optional[str] = Query(None, alias="signal", description="Filter: BUY SELL AVOID WATCH"),
    plan:        str            = Query("FREE"),
    limit:       int            = Query(50),
    db:          Session        = Depends(get_db),
):
    # Freemium limits
    if plan == "FREE":
        limit = min(limit, 3)
    elif plan == "PRO":
        limit = min(limit, 50)

    cutoff = datetime.utcnow() - timedelta(hours=24)
    query  = db.query(Signal).filter(
        Signal.is_active   == True,
        Signal.ingested_at >= cutoff,
    )

    if market:
        query = query.filter(Signal.market == market.upper())
    if signal_type:
        query = query.filter(Signal.signal == signal_type.upper())

    signals = query.order_by(Signal.ingested_at.desc()).limit(limit).all()

    result = []
    for s in signals:
        tickers = []
        try:
            tickers = json.loads(s.tickers)
        except Exception:
            pass

        result.append({
            "id":             s.id,
            "title":          s.title,
            "source":         s.source,
            "credibility":    s.credibility,
            "published_at":   s.published_at.isoformat() if s.published_at else None,
            "ingested_at":    s.ingested_at.isoformat()  if s.ingested_at  else None,
            "signal":         s.signal,
            "confidence":     s.confidence,
            "impact":         s.impact,
            "tickers":        tickers,
            "market":         s.market,
            "summary":        s.summary,
            "reasoning":      s.reasoning,
            "signal_logic":   s.signal_logic or "",
            "is_twitter":     s.is_twitter,
            "twitter_handle": s.twitter_handle,
        })

    return result


@router.get("/signals/stats")
def get_signal_stats(db: Session = Depends(get_db)):
    cutoff  = datetime.utcnow() - timedelta(hours=24)
    signals = db.query(Signal).filter(
        Signal.is_active   == True,
        Signal.ingested_at >= cutoff,
    ).all()

    counts     = {"BUY": 0, "SELL": 0, "AVOID": 0, "WATCH": 0}
    total_conf = 0.0
    for s in signals:
        if s.signal in counts:
            counts[s.signal] += 1
        total_conf += s.confidence

    avg_conf = round(total_conf / len(signals), 2) if signals else 0.0

    return {
        "total":          len(signals),
        "counts":         counts,
        "avg_confidence": avg_conf,
    }
