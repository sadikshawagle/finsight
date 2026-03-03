"""
One-time bootstrap script for Vercel — this creates the database schema
and generates the first batch of signals to seed the database.

Uses: DATABASE_URL from Vercel environment variables.

'''Run this ONCE after deploying to Vercel, then remove it.'''
"""
import os
import sys
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")

# Must be running with Vercel PostgreSQL database
if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
    print("ERROR: DATABASE_URL is not pointing to PostgreSQL")
    print("Check your Vercel environment variables.")
    sys.exit(1)

print("\n" + "="*60)
print("Initializing database schema...")
print("="*60)
from database import init_db
init_db()
print("✓ Database schema created")

print("\n" + "="*60)
print("Generating first batch of signals...")
print("="*60)
from services.signal_generator import process_new_articles
count = process_new_articles(max_articles=10)
print(f"✓ Generated {count} signals")

print("\n" + "="*60)
print("Updating price cache...")
print("="*60)
from services.price_fetcher import update_price_cache
update_price_cache()
print("✓ Price cache updated")

print("\n" + "="*60)
print("✓ Bootstrap complete!")
print("="*60)
print("\nNow make sure GitHub Actions is enabled to run the refresh_signals.yml workflow.")
print("The workflow will run every 5 minutes and keep the signals updated.\n")
