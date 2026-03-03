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
from routers import signals, markets, prices, watchlist, chart, beta, auth, payments

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
app.include_router(auth.router,      prefix="/api", tags=["Auth"])
app.include_router(payments.router,  prefix="/api", tags=["Payments"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "0.1.0", "app": "FinSight"}


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


@app.post("/api/admin/migrate-db", tags=["Admin"])
def migrate_db():
    """One-time: add new auth columns to beta_users if they don't exist yet."""
    from database import engine
    migrations = [
        "ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS password_hash TEXT",
        "ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP",
        "ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS access_expires_at TIMESTAMP",
        "ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
        "ALTER TABLE beta_users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT",
    ]
    results = []
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(engine.text(sql) if hasattr(engine, "text") else __import__("sqlalchemy").text(sql))
                results.append({"sql": sql, "status": "ok"})
            except Exception as e:
                results.append({"sql": sql, "status": "error", "detail": str(e)})
        conn.commit()
    return {"migrated": len([r for r in results if r["status"] == "ok"]), "results": results}


@app.get("/api/debug/db", tags=["Debug"])
def debug_db():
    """Debug endpoint exposing the database URL and total signal count."""
    try:
        from database import DATABASE_URL, SessionLocal, Signal
        db = SessionLocal()
        count = db.query(Signal).count()
        db.close()
        masked = DATABASE_URL[:20] + "***" if DATABASE_URL else "not set"
        return {"DATABASE_URL": masked, "signal_count": count}
    except Exception as e:
        return {"status": "error", "detail": str(e), "type": type(e).__name__}
