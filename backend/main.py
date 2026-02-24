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
from scheduler import start_scheduler, stop_scheduler
from routers import signals, markets, prices, watchlist, chart

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
    # Startup
    init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


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


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "0.1.0", "app": "FinSight"}
