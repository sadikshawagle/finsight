#!/usr/bin/env python3
"""Test the /api/signals endpoint locally."""
import subprocess
import json

# Start the backend server in background
print("Starting FastAPI server...")
proc = subprocess.Popen(
    ["python", "-m", "uvicorn", "main:app", "--port", "8000"],
    cwd="/Users/sadikshyawagle/finsight/backend",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

import time
time.sleep(3)  # Wait for server to start

# Test signals endpoint
print("Testing /api/signals...")
result = subprocess.run(
    ["curl", "-s", "http://localhost:8000/api/signals?plan=FREE&limit=50"],
    capture_output=True,
    text=True,
)

signals = json.loads(result.stdout)
print(f"✓ Got {len(signals)} signals from local API")
if signals:
    for s in signals[:3]:
        print(f"  - [{s.get('signal', 'N/A')}] {s.get('title', 'N/A')[:70]}")

# Test refresh endpoint
print("\nTesting /api/refresh...")
result = subprocess.run(
    ["curl", "-s", "-X", "POST", "http://localhost:8000/api/refresh"],
    capture_output=True,
    text=True,
)
print(f"Response: {result.stdout}")

# Cleanup
proc.terminate()
proc.wait()
