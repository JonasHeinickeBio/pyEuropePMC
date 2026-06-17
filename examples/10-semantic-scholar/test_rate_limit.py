#!/usr/bin/env python3
import os
import time
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded .env from: {env_path}")

api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
if api_key:
    print(f"API key: set (length={len(api_key)})")
else:
    print("API key: NOT SET")

from pyeuropepmc import SemanticScholarClient
client = SemanticScholarClient()
doi = "10.1038/nature12373"

def test_rate(num_requests=20, delay=0.1):
    print(f"\nTesting {num_requests} requests...")
    print("-" * 60)
    start = time.time()
    success = 0
    for i in range(1, num_requests + 1):
        t0 = time.time()
        try:
            result = client.enrich(identifier=doi)
            elapsed = time.time() - t0
            if result:
                success += 1
                print(f"{i:2d}: {elapsed:.3f}s - OK")
            else:
                print(f"{i:2d}: {elapsed:.3f}s - FAILED")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"{i:2d}: {elapsed:.3f}s - ERROR: {type(e).__name__}")
    end = time.time()
    total_time = end - start
    print("-" * 60)
    print(f"Total: {total_time:.2f}s, Rate: {num_requests/total_time:.2f} req/s")
    return success

print("=" * 60)
print("RATE LIMIT TEST")
print("=" * 60)
print("\n[1] 20 rapid requests")
s1 = test_rate(20, 0)
print("\n[2] 20 requests with 0.1s delay")
s2 = test_rate(20, 0.1)
print("\n[3] 10 requests with 0.5s delay")
s3 = test_rate(10, 0.5)
print("\n" + "=" * 60)
print(f"Results: {s1}/20 | {s2}/20 | {s3}/10")
print("=" * 60)
