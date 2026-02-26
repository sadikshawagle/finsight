"""
One-time script to seed the Neon DB with signals from local.
Usage:
  DATABASE_URL="postgresql://..." python seed_neon.py
"""
import os, sys

if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
    print("ERROR: Set DATABASE_URL to your Neon connection string first.")
    print('Usage: DATABASE_URL="postgresql://..." python seed_neon.py')
    sys.exit(1)

print("Connecting to Neon DB and running signal pipeline...")
from services.signal_generator import process_new_articles
from services.price_fetcher import update_price_cache
from database import init_db

init_db()
count = process_new_articles()
update_price_cache()
print(f"Done! Generated {count} new signals.")
