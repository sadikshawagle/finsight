"""
FinSight — FastAPI backend entry point.
Run with:
  source venv/bin/activate
  uvicorn main:app --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import signals, markets, prices, watchlist, chart, beta

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

# Accept origins from env var (comma-separated) or default to localhost
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title       = "FinSight API",
    version     = "0.1.0",
    description = "Real-time finance news signals powered by Groq AI",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ALLOWED_ORIGINS,
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

app.include_router(signals.router,   prefix="/api", tags=["Signals"])
app.include_router(markets.router,   prefix="/api", tags=["Markets"])
app.include_router(prices.router,    prefix="/api", tags=["Prices"])
app.include_router(watchlist.router, prefix="/api", tags=["Watchlist"])
app.include_router(chart.router,     prefix="/api", tags=["Chart"])
app.include_router(beta.router,      prefix="/api", tags=["Beta"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "0.1.0", "app": "FinSight"}


@app.post("/health/init", tags=["Health"])
def health_init():
    """One-time bootstrap endpoint to initialize Vercel PostgreSQL database with initial signals."""
    import logging
    log = logging.getLogger(__name__)
    try:
        log.info("Bootstrap: Initializing database and generating first batch of signals...")
        from services.signal_generator import process_new_articles
        from services.price_fetcher import update_price_cache
        
        # init_db() is already called in lifespan startup, but can be called again safely
        init_db()
        log.info("Bootstrap: Database schema initialized")
        
        count = process_new_articles(max_articles=10)
        log.info(f"Bootstrap: Generated {count} signals")
        
        update_price_cache()
        log.info("Bootstrap: Price cache updated")
        
        return {
            "status": "ok",
            "message": "Database initialized successfully",
            "signals_generated": count
        }
    except Exception as e:
        log.error(f"Bootstrap failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@app.post("/api/refresh", tags=["Health"])
def refresh():
    """Called by GitHub Actions every 5 minutes. Processes 1 article per call to stay within Vercel's timeout."""
    import logging
    log = logging.getLogger(__name__)
    try:
        log.info("Refresh triggered")
        from services.signal_generator import process_new_articles
        from services.price_fetcher import update_price_cache
        from services.news_aggregator import fetch_all_news
        
        # Check if we can fetch news
        news_count = len(fetch_all_news())
        log.info(f"Fetched {news_count} articles")
        
        count = process_new_articles(max_articles=1)
        log.info(f"Generated {count} new signals")
        
        update_price_cache()
        log.info("Price cache updated")
        
        return {"status": "ok", "new_signals": count, "articles_fetched": news_count}
    except Exception as e:
        log.error(f"Refresh failed: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


@app.get("/api/debug/news", tags=["Debug"])
def debug_news():
    """Debug endpoint to see what articles are being fetched."""
    try:
        from services.news_aggregator import fetch_all_news
        articles = fetch_all_news()
        return {
            "total_articles": len(articles),
            "articles": [
                {
                    "title": a.get("title", "")[:80],
                    "source": a.get("source", ""),
                    "credibility": a.get("credibility", 0),
                    "published_at": str(a.get("published_at", "")),
                }
                for a in articles[:10]
            ]
        }
    except Exception as e:
        return {"status": "error", "detail": str(e), "type": type(e).__name__}
