#!/usr/bin/env python3
"""
Demo: Semantic Scholar Enrichment with pyEuropePMC

Usage:
    python3 demo_semantic_scholar.py

With API key (recommended):
    export SEMANTIC_SCHOLAR_API_KEY=your_key
    python3 demo_semantic_scholar.py
"""

import os

api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

from pyeuropepmc import SemanticScholarClient

print("=" * 60)
print("Semantic Scholar Enrichment Demo")
print("=" * 60)

if api_key:
    print(f"\n✓ Using API key from environment (higher rate limits)")
else:
    print(f"\n⚠ No API key (lower rate limits: 25k/month)")

client = SemanticScholarClient()

# Test 1: Basic enrichment
print("\n[1] Basic Enrichment")
try:
    result = client.enrich(identifier="10.1038/nature12373")
    if result:
        print(f"✓ Title: {result.get('title', 'N/A')[:50]}...")
        print(f"  Citations: {result.get('citation_count')}")
        print(f"  Year: {result.get('year')}")
    else:
        print("✗ No result")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}")

# Test 2: Author enrichment
print("\n[2] Author Enrichment")
try:
    author = client.enrich_author(author_id="2226359")
    if author:
        print(f"✓ Name: {author.get('name')}")
        print(f"  Papers: {author.get('paper_count')}")
        print(f"  H-Index: {author.get('h_index')}")
    else:
        print("✗ No author data")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}")

# Test 3: Recommendations
print("\n[3] Paper Recommendations")
try:
    recs = client.get_recommendations_for_paper(
        "649def34f8be52c8b66281af98ae884c09aef38b",
        limit=2
    )
    print(f"✓ Found {len(recs)} recommendations")
    if recs:
        print(f"  First: {recs[0].get('title', 'N/A')[:40]}...")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}")

print("\n" + "=" * 60)
print("Demo complete!")
print("=" * 60)
