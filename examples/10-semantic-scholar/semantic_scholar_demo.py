#!/usr/bin/env python3
"""Demo: Semantic Scholar Enrichment with pyEuropePMC"""
import os
from pyeuropepmc import SemanticScholarClient

api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

print("=" * 60)
print("Semantic Scholar Enrichment Demo")
print("=" * 60)

if api_key:
    print("\nOK Using API key")
else:
    print("\nWARNING No API key (25k/month)")

client = SemanticScholarClient()

print("\n[1] Enrichment")
result = client.enrich(identifier="10.1038/nature12373")
if result:
    print(f"OK Title: {result.get('title', 'N/A')[:50]}...")
    print(f"  Citations: {result.get('citation_count')}")

print("\n[2] Author Enrichment")
author = client.enrich_author(author_id="2226359")
if author:
    print(f"OK Name: {author.get('name')}")
    print(f"  Papers: {author.get('paper_count')}")

print("\n[3] Recommendations")
recs = client.get_recommendations_for_paper(
    "649def34f8be52c8b66281af98ae884c09aef38b", limit=2)
print(f"OK Found {len(recs)} recommendations")

print("\n[4] Batch Enrichment")
results = client.enrich_batch(identifiers=["10.1038/nature12373", "10.1038/nature15758"])
print(f"OK Enriched {len(results)} papers")

print("\n" + "=" * 60)
print("Demo complete!")
print("=" * 60)
