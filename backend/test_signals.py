#!/usr/bin/env python3
"""Test signal generation."""
import logging

logging.basicConfig(level=logging.INFO, format="%(name)s — %(message)s")
log = logging.getLogger(__name__)

print("Starting signal generation test...\n")

# Test 1: Fetch signals from DB
print("=" * 60)
print("Checking current signals in DB...")
print("=" * 60)
try:
    from database import SessionLocal, Signal
    db = SessionLocal()
    count = db.query(Signal).count()
    print(f"✓ Total signals in DB: {count}")
    
    # Show 3 most recent
    recent = db.query(Signal).order_by(Signal.ingested_at.desc()).limit(3).all()
    for s in recent:
        print(f"  - [{s.signal}] {s.title[:70]}")
    db.close()
except Exception as e:
    print(f"✗ DB query failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: Run signal generation
print("=" * 60)
print("Running signal generation process...")
print("=" * 60)
try:
    from services.signal_generator import process_new_articles
    count = process_new_articles(max_articles=2)  # Just test with 2 articles
    print(f"✓ process_new_articles() returned: {count} new signals")
except Exception as e:
    print(f"✗ Signal generation failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Check signals again
print("=" * 60)
print("Checking signals after generation...")
print("=" * 60)
try:
    from database import SessionLocal, Signal
    db = SessionLocal()
    count = db.query(Signal).count()
    print(f"✓ Total signals in DB now: {count}")
    db.close()
except Exception as e:
    print(f"✗ DB query failed: {e}")
