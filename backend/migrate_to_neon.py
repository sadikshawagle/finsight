"""
Copies all signals from local SQLite → Neon PostgreSQL.
Run with: python migrate_to_neon.py
"""
import os, sys

print("=== FinSight: Copy local signals to Neon ===\n")
neon_url = input("Paste your Neon connection string and press Enter:\n> ").strip()

if not neon_url.startswith("postgresql"):
    print("That doesn't look right. It should start with 'postgresql://'")
    sys.exit(1)

os.environ["DATABASE_URL"] = neon_url

# Local SQLite
import sqlite3
conn = sqlite3.connect("finsight.db")
rows = conn.execute("SELECT * FROM signals WHERE is_active=1").fetchall()
cols = [d[0] for d in conn.execute("PRAGMA table_info(signals)").fetchall()]
conn.close()
print(f"\nFound {len(rows)} active signals in local DB. Copying to Neon...")

# Neon PostgreSQL
from sqlalchemy import create_engine, text
if neon_url.startswith("postgres://"):
    neon_url = neon_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(neon_url)

# Create tables
from database import Base, init_db
init_db()

from database import SessionLocal, Signal
from datetime import datetime
import json

db = SessionLocal()
copied = 0
for row in rows:
    data = dict(zip(cols, row))
    try:
        exists = db.query(Signal).filter(Signal.news_hash == data["news_hash"]).first()
        if exists:
            continue
        s = Signal(
            news_hash      = data["news_hash"],
            title          = data["title"],
            source         = data["source"],
            source_domain  = data["source_domain"],
            credibility    = data["credibility"],
            published_at   = datetime.fromisoformat(data["published_at"]) if isinstance(data["published_at"], str) else data["published_at"],
            signal         = data["signal"],
            confidence     = data["confidence"],
            impact         = data["impact"],
            tickers        = data["tickers"],
            market         = data["market"],
            summary        = data["summary"],
            reasoning      = data["reasoning"],
            signal_logic   = data.get("signal_logic"),
            pump_dump_risk = data.get("pump_dump_risk", "LOW"),
            is_twitter     = bool(data.get("is_twitter", 0)),
            twitter_handle = data.get("twitter_handle"),
            is_active      = bool(data.get("is_active", 1)),
        )
        db.add(s)
        db.commit()
        copied += 1
    except Exception as e:
        db.rollback()
        print(f"  Skipped: {data.get('title','?')[:50]} — {e}")

db.close()
print(f"\nDone! Copied {copied} signals to Neon.")
print("Visit https://finsight-blush.vercel.app — signals should appear now.")
