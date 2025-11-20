"""
Report generation utilities for enrichment results.

This module provides classes for generating human-readable reports
from enrichment results and analysis.
"""

from typing import Any


class EnrichmentReporter:
    """
    Generates human-readable reports from enrichment results.

    This class provides methods to create formatted reports summarizing
    enrichment data, statistics, and key metadata.
    """

    def __init__(self) -> None:
        """Initialize the enrichment reporter."""
        pass

    def generate_report(self, enrichment_result: dict[str, Any]) -> str:
        """
        Generate a human-readable report from enrichment results.

        Parameters
        ----------
        enrichment_result : dict
            Result from enrich_paper or enrich_papers_batch

        Returns
        -------
        str
            Formatted report string
        """
        if not enrichment_result:
            return "No enrichment data available."

        lines = []
        lines.append("=== Paper Enrichment Report ===")
        lines.append(f"Identifier: {enrichment_result.get('identifier', 'N/A')}")
        lines.append(f"DOI: {enrichment_result.get('doi', 'N/A')}")

        # Sources summary
        sources = enrichment_result.get("sources", [])
        lines.append(f"Data Sources: {len(sources)} ({', '.join(sources) if sources else 'None'})")

        # Merged data summary
        merged = enrichment_result.get("merged", {})
        if merged:
            lines.append("\n--- Key Metadata ---")
            if merged.get("title"):
                title = merged["title"]
                truncated_title = f"{title[:100]}{'...' if len(title) > 100 else ''}"
                lines.append(f"Title: {truncated_title}")
            if merged.get("authors"):
                author_count = len(merged["authors"])
                lines.append(f"Authors: {author_count}")
            if merged.get("journal"):
                journal = merged["journal"]
                journal_name = journal.get("title") or journal.get("name", "Unknown")
                lines.append(f"Journal: {journal_name}")
            if merged.get("publication_date") or merged.get("publication_year"):
                pub_date = merged.get("publication_date") or merged.get("publication_year")
                lines.append(f"Publication: {pub_date}")
            if merged.get("citation_count"):
                lines.append(f"Citations: {merged['citation_count']}")
            if merged.get("is_oa") is not None:
                oa_status = "Open Access" if merged["is_oa"] else "Closed Access"
                lines.append(f"Access: {oa_status}")
        else:
            lines.append("No merged metadata available.")

        return "\n".join(lines)

    def generate_batch_summary(self, batch_results: dict[str, dict[str, Any]]) -> str:
        """
        Generate a summary report for batch enrichment results.

        Parameters
        ----------
        batch_results : dict
            Results from enrich_papers_batch

        Returns
        -------
        str
            Formatted batch summary report
        """
        if not batch_results:
            return "No batch results available."

        total_papers = len(batch_results)
        successful_enrichments = sum(
            1
            for result in batch_results.values()
            if isinstance(result, dict) and result.get("sources")
        )
        failed_enrichments = total_papers - successful_enrichments

        lines = []
        lines.append("=== Batch Enrichment Summary ===")
        lines.append(f"Total Papers: {total_papers}")
        lines.append(f"Successful Enrichments: {successful_enrichments}")
        lines.append(f"Failed Enrichments: {failed_enrichments}")
        lines.append(f"Success Rate: {(successful_enrichments / total_papers * 100):.1f}%")

        if successful_enrichments > 0:
            # Calculate average sources per paper
            total_sources = sum(
                len(result.get("sources", []))
                for result in batch_results.values()
                if isinstance(result, dict)
            )
            avg_sources = total_sources / successful_enrichments
            lines.append(f"Average Sources per Paper: {avg_sources:.1f}")

            # Most common sources
            source_counts: dict[str, int] = {}
            for result in batch_results.values():
                if isinstance(result, dict):
                    for source in result.get("sources", []):
                        source_counts[source] = source_counts.get(source, 0) + 1

            if source_counts:
                most_common = max(source_counts.items(), key=lambda x: x[1])
                lines.append(f"Most Used Source: {most_common[0]} ({most_common[1]} papers)")

        return "\n".join(lines)
