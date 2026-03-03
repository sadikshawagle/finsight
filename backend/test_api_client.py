#!/usr/bin/env python3
"""Test the API routes using FastAPI test client."""
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Test health endpoint
print("Testing /health...")
response = client.get("/health")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

print("\n" + "="*60)
print("Testing /api/signals...")
response = client.get("/api/signals?plan=FREE&limit=50")
print(f"Status: {response.status_code}")
signals = response.json()
print(f"Got {len(signals)} signals")
if signals:
    for s in signals[:3]:
        print(f"  - [{s.get('signal', 'N/A')}] {s.get('title', 'N/A')[:70]}")

print("\n" + "="*60)
print("Testing /api/markets/overview...")
response = client.get("/api/markets/overview")
print(f"Status: {response.status_code}")
markets = response.json()
print(f"Indices: {list(markets.get('indices', {}).keys())}")
print(f"Commodities: {list(markets.get('commodities', {}).keys())}")
print(f"Crypto: {list(markets.get('crypto', {}).keys())}")
