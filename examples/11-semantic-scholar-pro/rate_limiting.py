"""
Rate Limiting Example with the Semantic Scholar Library Wrapper

This example shows how rate_limit_delay spaces out the requests of
ProfessionalSemanticScholarClient, and how a bulk search keeps the number of
API calls down. The wrapper does not cache responses: repeating a request
makes another API call.
"""

import time

from pyeuropepmc.features.enrich.sources.semanticscholar_pro import (
    ProfessionalSemanticScholarClient,
)


def timed_get_paper(client, paper_id):
    """Fetch one paper and return the elapsed seconds."""
    start_time = time.time()
    client.get_paper(paper_id)
    return time.time() - start_time


def main():
    print("=" * 60)
    print("Rate Limiting Example")
    print("=" * 60)

    paper_id = "DOI:10.1038/nature12373"

    # Example 1: Low volume (hobby projects)
    print("\n\n1. Low Volume Configuration (2.0s delay)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key=None,  # or "your-api-key-here"
        rate_limit_delay=2.0,  # at least 2 seconds between requests
    )
    timed_get_paper(client, paper_id)
    elapsed = timed_get_paper(client, paper_id)  # waits for the delay first
    print(f"Second request took: {elapsed:.2f}s (includes the 2.0s spacing)")
    print("Estimated papers/hour: ~1800")

    # Example 2: Medium volume (research projects)
    print("\n\n2. Medium Volume Configuration (1.0s delay)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key=None,
        rate_limit_delay=1.0,  # at least 1 second between requests
    )
    timed_get_paper(client, paper_id)
    elapsed = timed_get_paper(client, paper_id)
    print(f"Second request took: {elapsed:.2f}s (includes the 1.0s spacing)")
    print("Estimated papers/hour: ~3600")

    # Example 3: High volume (needs an API key for the higher rate limit)
    print("\n\n3. High Volume Configuration (0.5s delay, API key)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(
        api_key=None,  # a key is required to stay under the limit at this pace
        rate_limit_delay=0.5,
    )
    timed_get_paper(client, paper_id)
    elapsed = timed_get_paper(client, paper_id)
    print(f"Second request took: {elapsed:.2f}s (not cached: a second API call)")
    print("Estimated papers/hour: ~7200")

    # Example 4: Bulk search (minimize API calls)
    print("\n\n4. Bulk Search (Minimal API Calls)")
    print("-" * 40)

    client = ProfessionalSemanticScholarClient(api_key=None, rate_limit_delay=1.0)

    # A bulk search returns up to 1000 papers per API call
    start_time = time.time()
    papers = client.search_paper("cancer", bulk=True, limit=100)
    elapsed_bulk = time.time() - start_time

    print(f"Bulk search took: {elapsed_bulk:.2f}s")
    print(f"Papers retrieved: {len(papers)}")

    print("\n\nComparison: Bulk vs one request per paper")
    print("-" * 40)
    print(f"Bulk search (1 API call, ~{elapsed_bulk:.2f}s): recommended for large datasets")
    print("get_paper() for each of 100 papers (100 API calls, ~100s+): for small sets")


if __name__ == "__main__":
    main()
