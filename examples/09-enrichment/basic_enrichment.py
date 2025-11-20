"""
Basic example demonstrating paper metadata enrichment.

This example shows how to enrich paper metadata using external APIs
like CrossRef, Semantic Scholar, and OpenAlex.
"""

from pyeuropepmc import PaperEnricher, EnrichmentConfig

# Example DOI
DOI = "10.1371/journal.pone.0308090"


def main():
    """Demonstrate basic enrichment functionality."""
    print("=" * 80)
    print("Paper Metadata Enrichment Example")
    print("=" * 80)

    # Configure enrichment with default settings
    # This enables CrossRef, Semantic Scholar, and OpenAlex
    # Unpaywall is disabled by default (requires email)
    config = EnrichmentConfig(
        enable_crossref=True,
        enable_semantic_scholar=True,
        enable_openalex=True,
        enable_unpaywall=False,
    )

    # Create enricher
    with PaperEnricher(config) as enricher:
        print(f"\nEnriching metadata for DOI: {DOI}")
        print("-" * 80)

        # Enrich the paper
        result = enricher.enrich_paper(doi=DOI)

        # Display results
        print(f"\nData sources used: {', '.join(result['sources'])}")
        print("\n" + "=" * 80)
        print("MERGED METADATA")
        print("=" * 80)

        merged = result.get("merged", {})

        # Title
        if "title" in merged:
            print(f"\nTitle: {merged['title']}")

        # Authors
        if "authors" in merged:
            print(f"\nAuthors ({len(merged['authors'])} total):")
            # Show first 5 authors
            authors = merged["authors"][:5]
            for author in authors:
                if isinstance(author, dict):
                    print(f"  - {author.get('name', author.get('display_name', 'Unknown'))}")
                else:
                    print(f"  - {author}")
            if len(merged["authors"]) > 5:
                print(f"  ... and {len(merged['authors']) - 5} more")

        # Abstract
        if "abstract" in merged and merged["abstract"]:
            abstract = merged["abstract"]
            print(f"\nAbstract: {abstract[:200]}...")

        # Journal
        if "journal" in merged:
            journal = merged["journal"]
            if isinstance(journal, dict):
                print(f"\nJournal: {journal.get('display_name', journal)}")
            else:
                print(f"\nJournal: {journal}")

        # Publication date
        if "publication_date" in merged:
            print(f"Publication Date: {merged['publication_date']}")
        elif "publication_year" in merged:
            print(f"Publication Year: {merged['publication_year']}")

        # Citation metrics
        if "citation_count" in merged:
            print(f"\nCitation Count: {merged['citation_count']}")
            if "citation_counts" in merged:
                print("  Citation counts by source:")
                for cite_info in merged["citation_counts"]:
                    print(f"    - {cite_info['source']}: {cite_info['count']}")

        if "influential_citation_count" in merged:
            print(f"Influential Citations: {merged['influential_citation_count']}")

        # Open access status
        if "is_oa" in merged:
            oa_status = "Yes" if merged["is_oa"] else "No"
            print(f"\nOpen Access: {oa_status}")
            if merged.get("oa_status"):
                print(f"  Status: {merged['oa_status']}")
            if merged.get("oa_url"):
                print(f"  URL: {merged['oa_url']}")

        # Topics/Fields of study
        if "topics" in merged and merged["topics"]:
            print("\nTopics:")
            for topic in merged["topics"][:5]:
                if isinstance(topic, dict):
                    name = topic.get("display_name", topic)
                    score = topic.get("score", "")
                    if score:
                        print(f"  - {name} (score: {score:.3f})")
                    else:
                        print(f"  - {name}")
                else:
                    print(f"  - {topic}")

        if "fields_of_study" in merged and merged["fields_of_study"]:
            print("\nFields of Study:")
            for field in merged["fields_of_study"][:5]:
                print(f"  - {field}")

        # License information
        if "license" in merged and merged["license"]:
            license_info = merged["license"]
            if isinstance(license_info, dict) and license_info.get("url"):
                print(f"\nLicense: {license_info['url']}")

        # Funding information
        if "funders" in merged and merged["funders"]:
            print("\nFunders:")
            for funder in merged["funders"][:3]:
                if isinstance(funder, dict):
                    print(f"  - {funder.get('name', 'Unknown')}")
                    if funder.get("award"):
                        print(f"    Awards: {', '.join(funder['award'])}")

        # Show individual source data
        print("\n" + "=" * 80)
        print("INDIVIDUAL SOURCE DATA")
        print("=" * 80)

        for source in result["sources"]:
            print(f"\n{source.upper()}:")
            print("-" * 40)
            source_data = result.get(source, {})
            if source_data:
                # Show a few key fields from each source
                if "title" in source_data:
                    print(f"  Title: {source_data['title'][:60]}...")
                if "citation_count" in source_data:
                    print(f"  Citations: {source_data['citation_count']}")
                if "is_oa" in source_data:
                    print(f"  Open Access: {source_data['is_oa']}")

    print("\n" + "=" * 80)
    print("Enrichment complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
