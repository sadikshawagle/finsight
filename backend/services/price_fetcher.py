"""
Fetches stock, index, commodity, and crypto prices.
- Stocks/indices/commodities: yfinance (free, unofficial Yahoo Finance)
- Crypto: CoinGecko (free, no API key needed)
Compatible with Python 3.9+
"""
from __future__ import annotations
from typing import Optional, Dict
import yfinance as yf
from pycoingecko import CoinGeckoAPI
from database import SessionLocal, Price
from datetime import datetime
import logging

log = logging.getLogger(__name__)
cg = CoinGeckoAPI()

# ── Ticker definitions ─────────────────────────────────────────────────────────

INDICES = {
    "ASX 200":   "^AXJO",
    "S&P 500":   "^GSPC",
    "NASDAQ":    "^IXIC",
    "Dow Jones": "^DJI",
}

COMMODITIES = {
    "Gold":       "GC=F",
    "Silver":     "SI=F",
    "Oil (WTI)":  "CL=F",
}

CRYPTO_IDS = {
    "Bitcoin":  "bitcoin",
    "Ethereum": "ethereum",
    "Solana":   "solana",
    "XRP":      "ripple",
}

CURRENCY_MAP = {
    "^AXJO": "AUD",
    "GC=F":  "USD",
    "SI=F":  "USD",
    "CL=F":  "USD",
}


def _fetch_yf(ticker: str) -> Optional[Dict]:
    """Fetch a single ticker price via yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="2d")
        if hist.empty:
            return None
        current = float(hist["Close"].iloc[-1])
        prev    = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current
        change  = ((current - prev) / prev) * 100 if prev else 0
        return {
            "ticker":     ticker,
            "price":      round(current, 2),
            "change_pct": round(change, 2),
            "currency":   CURRENCY_MAP.get(ticker, "USD"),
        }
    except Exception as e:
        log.warning(f"yfinance failed for {ticker}: {e}")
        return None


def fetch_market_overview() -> Dict:
    """Return prices for all indices and commodities."""
    result = {}
    for name, ticker in {**INDICES, **COMMODITIES}.items():
        data = _fetch_yf(ticker)
        if data:
            result[name] = data
    return result


def fetch_crypto_prices() -> Dict:
    """Return crypto prices via CoinGecko (no key required)."""
    try:
        ids    = list(CRYPTO_IDS.values())
        prices = cg.get_price(ids=ids, vs_currencies="usd", include_24hr_change=True)
        result = {}
        for name, cg_id in CRYPTO_IDS.items():
            if cg_id in prices:
                result[name] = {
                    "ticker":     cg_id.upper(),
                    "price":      prices[cg_id].get("usd", 0),
                    "change_pct": round(prices[cg_id].get("usd_24h_change", 0), 2),
                    "currency":   "USD",
                }
        return result
    except Exception as e:
        log.warning(f"CoinGecko failed: {e}")
        return {}


def fetch_single_price(ticker: str) -> Optional[Dict]:
    """Fetch price for any single ticker (stock, index, commodity)."""
    return _fetch_yf(ticker)


def update_price_cache():
    """Scheduled job: fetch all prices and write to DB."""
    db = SessionLocal()
    try:
        all_prices = {}
        all_prices.update(fetch_market_overview())
        all_prices.update(fetch_crypto_prices())

        now = datetime.utcnow()
        for name, data in all_prices.items():
            row = Price(
                ticker     = data["ticker"],
                name       = name,
                price      = data["price"],
                change_pct = data["change_pct"],
                currency   = data["currency"],
                fetched_at = now,
            )
            db.add(row)
        db.commit()
        log.info(f"Price cache updated: {len(all_prices)} items")
    except Exception as e:
        log.error(f"Price cache update failed: {e}")
        db.rollback()
    finally:
        db.close()
