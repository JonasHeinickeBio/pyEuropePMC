"""
Data merging utilities for enrichment results.

This module provides classes and functions for merging metadata from
multiple enrichment sources with intelligent conflict resolution.
"""

from typing import Any


class DataMerger:
    """
    Handles merging of enrichment data from multiple sources.

    This class provides intelligent merging of metadata from different
    enrichment APIs, with configurable priority rules and conflict resolution.
    """

    def __init__(self) -> None:
        """Initialize the data merger."""
        pass

    def merge_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        Merge results from multiple sources into a single metadata dict.

        Parameters
        ----------
        results : dict
            Results from all sources

        Returns
        -------
        dict
            Merged metadata
        """
        merged: dict[str, Any] = {}

        merged.update(self._merge_title(results))
        merged.update(self._merge_authors_field(results))
        merged.update(self._merge_abstract(results))
        merged.update(self._merge_journal(results))
        merged.update(self._merge_publication_date(results))
        merged.update(self._merge_citations(results))
        merged.update(self._merge_oa_info(results))
        merged.update(self._merge_additional_metrics(results))
        merged.update(self._merge_topics(results))
        merged.update(self._merge_license(results))
        merged.update(self._merge_funders(results))

        return merged

    def _merge_title(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge title from multiple sources."""
        for source in ["crossref", "openalex", "semantic_scholar"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict) and source_data.get("title"):
                return {"title": source_data["title"]}
        return {}

    def _merge_authors_field(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge authors field."""
        merged_authors = self._merge_authors(results)
        return {"authors": merged_authors} if merged_authors else {}

    def _merge_abstract(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge abstract from multiple sources."""
        for source in ["crossref", "semantic_scholar"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict) and source_data.get("abstract"):
                return {"abstract": source_data["abstract"]}
        return {}

    def _merge_journal(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge journal/venue information."""
        for source in ["crossref", "openalex"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict):
                journal = source_data.get("journal") or source_data.get("venue", {})
                if journal:
                    return {"journal": journal}
        return {}

    def _merge_publication_date(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge publication date/year."""
        crossref_data = results.get("crossref")
        openalex_data = results.get("openalex")
        if (
            crossref_data
            and isinstance(crossref_data, dict)
            and crossref_data.get("publication_date")
        ):
            return {"publication_date": crossref_data["publication_date"]}
        elif openalex_data and isinstance(openalex_data, dict):
            if openalex_data.get("publication_date"):
                return {"publication_date": openalex_data["publication_date"]}
            elif openalex_data.get("publication_year"):
                return {"publication_year": openalex_data["publication_year"]}
        return {}

    def _merge_citations(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge citation counts from multiple sources."""
        citation_counts = []
        for source in ["crossref", "semantic_scholar", "openalex"]:
            source_data = results.get(source)
            if source_data and isinstance(source_data, dict):
                count = source_data.get("citation_count")
                if count is not None:
                    citation_counts.append({"source": source, "count": count})

        if citation_counts:
            return {
                "citation_counts": citation_counts,
                "citation_count": max(c["count"] for c in citation_counts),
            }
        return {}

    def _merge_oa_info(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge open access information."""
        unpaywall_data = results.get("unpaywall")
        openalex_data = results.get("openalex")
        if unpaywall_data and isinstance(unpaywall_data, dict):
            result = {
                "is_oa": unpaywall_data.get("is_oa", False),
                "oa_status": unpaywall_data.get("oa_status"),
            }
            best_oa = unpaywall_data.get("best_oa_location")
            if best_oa and isinstance(best_oa, dict):
                result["oa_url"] = best_oa.get("url")
            return result
        elif openalex_data and isinstance(openalex_data, dict):
            return {
                "is_oa": openalex_data.get("is_oa", False),
                "oa_status": openalex_data.get("oa_status"),
                "oa_url": openalex_data.get("oa_url"),
            }
        return {}

    def _merge_additional_metrics(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge additional metrics from Semantic Scholar."""
        semantic_data = results.get("semantic_scholar")
        if semantic_data and isinstance(semantic_data, dict):
            return {
                "influential_citation_count": semantic_data.get("influential_citation_count"),
                "fields_of_study": semantic_data.get("fields_of_study"),
            }
        return {}

    def _merge_topics(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge topics from OpenAlex."""
        openalex_data = results.get("openalex")
        if openalex_data and isinstance(openalex_data, dict):
            return {"topics": openalex_data.get("topics")}
        return {}

    def _merge_license(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge license information from CrossRef."""
        crossref_data = results.get("crossref")
        if crossref_data and isinstance(crossref_data, dict) and crossref_data.get("license"):
            return {"license": crossref_data["license"]}
        return {}

    def _merge_funders(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge funders from CrossRef."""
        crossref_data = results.get("crossref")
        if crossref_data and isinstance(crossref_data, dict) and crossref_data.get("funders"):
            return {"funders": crossref_data["funders"]}
        return {}

    def _merge_authors(self, results: dict[str, Any]) -> list[dict[str, Any]] | None:
        """
        Merge author information from multiple sources with comprehensive details.

        Parameters
        ----------
        results : dict
            Results from all sources

        Returns
        -------
        list[dict[str, Any]] | None
            Merged author list with detailed information
        """
        all_authors: dict[str, dict[str, Any]] = {}

        self._process_crossref_authors(results, all_authors)
        self._process_openalex_authors(results, all_authors)
        self._process_datacite_authors(results, all_authors)

        if not all_authors:
            return None

        merged_list = list(all_authors.values())
        merged_list.sort(key=lambda x: len(x.get("sources", [])), reverse=True)
        return merged_list

    def _process_crossref_authors(
        self, results: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process authors from CrossRef."""
        crossref_data = results.get("crossref")
        if not crossref_data or not isinstance(crossref_data, dict):
            return

        cr_authors = crossref_data.get("authors", [])
        for author in cr_authors:
            if not isinstance(author, dict):
                continue
            name = author.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in all_authors:
                all_authors[key] = {
                    "name": name,
                    "given_name": author.get("given", ""),
                    "family_name": author.get("family", ""),
                    "orcid": author.get("ORCID"),
                    "affiliations": author.get("affiliation", []),
                    "sequence": author.get("sequence"),
                    "sources": ["crossref"],
                }
            else:
                existing = all_authors[key]
                if not existing.get("orcid") and author.get("ORCID"):
                    existing["orcid"] = author.get("ORCID")
                existing["sources"].append("crossref")

    def _process_openalex_authors(  # noqa: C901
        self, results: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process authors from OpenAlex."""
        openalex_data = results.get("openalex")
        if not openalex_data or not isinstance(openalex_data, dict):
            return

        oa_authors = openalex_data.get("authors", [])
        for author in oa_authors:
            if not isinstance(author, dict):
                continue
            name = author.get("display_name", "").strip()
            if not name:
                continue
            key = name.lower()
            institutions = []
            for inst in author.get("institutions", []):
                if isinstance(inst, dict):
                    institutions.append(
                        {
                            "id": inst.get("id"),
                            "display_name": inst.get("display_name"),
                            "country": inst.get("country"),
                            "type": inst.get("type"),
                            "ror_id": inst.get("ror_id"),
                        }
                    )

            if key not in all_authors:
                all_authors[key] = {
                    "name": name,
                    "orcid": author.get("orcid"),
                    "openalex_id": author.get("id"),
                    "institutions": institutions,
                    "position": author.get("position"),
                    "sources": ["openalex"],
                }
            else:
                existing = all_authors[key]
                if not existing.get("orcid") and author.get("orcid"):
                    existing["orcid"] = author.get("orcid")
                if not existing.get("openalex_id"):
                    existing["openalex_id"] = author.get("id")
                if not existing.get("institutions") and institutions:
                    existing["institutions"] = institutions
                if not existing.get("position"):
                    existing["position"] = author.get("position")
                existing["sources"].append("openalex")

    def _process_datacite_authors(
        self, results: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process authors from DataCite."""
        datacite_data = results.get("datacite")
        if not datacite_data or not isinstance(datacite_data, dict):
            return

        dc_creators = datacite_data.get("creators", [])
        for creator in dc_creators:
            if not isinstance(creator, dict):
                continue
            name = creator.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            affiliations = creator.get("affiliation", [])
            orcid = creator.get("orcid")

            if key not in all_authors:
                all_authors[key] = {
                    "name": name,
                    "given_name": creator.get("given_name", ""),
                    "family_name": creator.get("family_name", ""),
                    "orcid": orcid,
                    "affiliations": affiliations,
                    "sources": ["datacite"],
                }
            else:
                existing = all_authors[key]
                if not existing.get("orcid") and orcid:
                    existing["orcid"] = orcid
                if not existing.get("affiliations") and affiliations:
                    existing["affiliations"] = affiliations
                existing["sources"].append("datacite")
