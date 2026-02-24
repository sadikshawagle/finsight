from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db, WatchlistItem
from services.price_fetcher import fetch_single_price

router = APIRouter()


class AddTickerRequest(BaseModel):
    ticker: str
    name:   Optional[str] = None


@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    items  = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    result = []
    for item in items:
        price_data = fetch_single_price(item.ticker) or {}
        result.append({
            "ticker":     item.ticker,
            "name":       item.name or item.ticker,
            "price":      price_data.get("price"),
            "change_pct": price_data.get("change_pct"),
            "currency":   price_data.get("currency", "USD"),
        })
    return result


@router.post("/watchlist")
def add_to_watchlist(body: AddTickerRequest, db: Session = Depends(get_db)):
    ticker   = body.ticker.upper()
    existing = db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist")
    item = WatchlistItem(ticker=ticker, name=body.name or ticker)
    db.add(item)
    db.commit()
    return {"ticker": ticker, "added": True}


@router.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(
        WatchlistItem.ticker == ticker.upper()
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    db.delete(item)
    db.commit()
    return {"ticker": ticker.upper(), "removed": True}
