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
        merged.update(self._merge_external_ids(results))
        merged.update(self._merge_bibliographic_info(results))
        merged.update(self._merge_references(results))

        # Apply ROR enrichment to institutions in authors
        self._apply_ror_enrichment_to_authors(merged, results)

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
            return {"funding": crossref_data["funders"]}
        return {}

    def _merge_external_ids(self, results: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
        """Merge external identifiers from all sources, flattening and aligning them."""
        external_ids: dict[str, Any] = {}
        conflicts: dict[str, Any] = {}

        # Helper function to normalize identifiers
        def normalize_pmid(value: str) -> str:
            """Normalize PMID to just the numeric ID."""
            if isinstance(value, str):
                # Extract PMID from URL if present
                if "pubmed.ncbi.nlm.nih.gov" in value:
                    import re

                    match = re.search(r"/(\d+)", value)
                    if match:
                        return match.group(1)
                # Return as-is if already just the ID
                return value.strip()
            return str(value).strip()

        def normalize_doi(value: str) -> str:
            """Normalize DOI to just the DOI string."""
            if isinstance(value, str):
                # Extract DOI from URL if present
                if "doi.org" in value:
                    return value.replace("https://doi.org/", "").strip()
                # Return as-is if already just the DOI
                return value.strip()
            return str(value).strip()

        # Semantic Scholar external IDs
        semantic_data = results.get("semantic_scholar")
        if semantic_data and isinstance(semantic_data, dict):
            ss_ids = semantic_data.get("external_ids", {})
            if ss_ids:
                # Map Semantic Scholar IDs to standardized field names
                ss_mappings = {
                    "CorpusId": "semantic_scholar_corpus_id",
                    "PubMed": "pmid",  # Will be normalized
                }
                for ss_key, field_name in ss_mappings.items():
                    value = ss_ids.get(ss_key)
                    if value:
                        # Normalize based on field type
                        if field_name == "pmid":
                            value = normalize_pmid(value)
                        normalized_value = value

                        if (
                            field_name in external_ids
                            and external_ids[field_name] != normalized_value
                        ):
                            # Conflict detected
                            if field_name not in conflicts:
                                conflicts[field_name] = []
                            conflicts[field_name].append(
                                {
                                    "source": "semantic_scholar",
                                    "original_value": ss_ids.get(ss_key),
                                    "normalized_value": normalized_value,
                                    "conflicts_with": external_ids[field_name],
                                }
                            )
                        else:
                            external_ids[field_name] = normalized_value

        # OpenAlex IDs
        openalex_data = results.get("openalex")
        if openalex_data and isinstance(openalex_data, dict):
            oa_ids = openalex_data.get("ids", {})
            if oa_ids:
                # Map OpenAlex IDs to standardized field names
                oa_mappings = {
                    "openalex": "openalex_id",
                    "doi": "doi",  # Will be normalized
                    "pmid": "pmid",  # Will be normalized
                }
                for oa_key, field_name in oa_mappings.items():
                    value = oa_ids.get(oa_key)
                    if value:
                        # Normalize based on field type
                        if field_name == "pmid":
                            value = normalize_pmid(value)
                        elif field_name == "doi":
                            value = normalize_doi(value)
                        normalized_value = value

                        if (
                            field_name in external_ids
                            and external_ids[field_name] != normalized_value
                        ):
                            # Conflict detected
                            if field_name not in conflicts:
                                conflicts[field_name] = []
                            conflicts[field_name].append(
                                {
                                    "source": "openalex",
                                    "original_value": oa_ids.get(
                                        oa_key
                                    ),  # Keep original for conflict reporting
                                    "normalized_value": normalized_value,
                                    "conflicts_with": external_ids[field_name],
                                }
                            )
                        else:
                            external_ids[field_name] = normalized_value

        # CrossRef doesn't typically have external IDs beyond DOI, but check anyway
        crossref_data = results.get("crossref")
        if crossref_data and isinstance(crossref_data, dict):
            doi = crossref_data.get("DOI")
            if doi:
                normalized_doi = normalize_doi(doi)
                if "doi" in external_ids and external_ids["doi"] != normalized_doi:
                    if "doi" not in conflicts:
                        conflicts["doi"] = []
                    conflicts["doi"].append(
                        {
                            "source": "crossref",
                            "original_value": doi,
                            "normalized_value": normalized_doi,
                            "conflicts_with": external_ids["doi"],
                        }
                    )
                else:
                    external_ids["doi"] = normalized_doi

        result = {}
        if external_ids:
            result["external_ids"] = external_ids
        if conflicts:
            result["external_id_conflicts"] = conflicts

        return result

    def _merge_bibliographic_info(self, results: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
        """Merge bibliographic information from multiple sources."""
        biblio = {}

        # CrossRef bibliographic info
        crossref_data = results.get("crossref")
        if crossref_data and isinstance(crossref_data, dict):
            if crossref_data.get("volume"):
                biblio["volume"] = crossref_data["volume"]
            if crossref_data.get("issue"):
                biblio["issue"] = crossref_data["issue"]
            if crossref_data.get("page"):
                biblio["pages"] = crossref_data["page"]
            if crossref_data.get("publisher"):
                biblio["publisher"] = crossref_data["publisher"]
            if crossref_data.get("issn"):
                biblio["issn"] = crossref_data["issn"]
            if crossref_data.get("type"):
                biblio["type"] = crossref_data["type"]

        # OpenAlex bibliographic info
        openalex_data = results.get("openalex")
        if openalex_data and isinstance(openalex_data, dict):
            oa_biblio = openalex_data.get("biblio", {})
            if oa_biblio:
                if not biblio.get("volume") and oa_biblio.get("volume"):
                    biblio["volume"] = oa_biblio["volume"]
                if not biblio.get("issue") and oa_biblio.get("issue"):
                    biblio["issue"] = oa_biblio["issue"]
                if not biblio.get("first_page") and oa_biblio.get("first_page"):
                    biblio["first_page"] = oa_biblio["first_page"]
                if not biblio.get("last_page") and oa_biblio.get("last_page"):
                    biblio["last_page"] = oa_biblio["last_page"]

        # Semantic Scholar bibliographic info
        semantic_data = results.get("semantic_scholar")
        if semantic_data and isinstance(semantic_data, dict):
            ss_journal = semantic_data.get("journal", {})
            if ss_journal:
                if not biblio.get("volume") and ss_journal.get("volume"):
                    biblio["volume"] = ss_journal["volume"]
                if not biblio.get("pages") and ss_journal.get("pages"):
                    biblio["pages"] = ss_journal["pages"]

        return {"biblio": biblio} if biblio else {}

    def _merge_references(self, results: dict[str, Any]) -> dict[str, Any]:
        """Merge reference/citation information from multiple sources."""
        references = {}

        # CrossRef references count
        crossref_data = results.get("crossref")
        if (
            crossref_data
            and isinstance(crossref_data, dict)
            and crossref_data.get("references_count")
        ):
            references["count"] = crossref_data["references_count"]

        # Semantic Scholar reference count
        semantic_data = results.get("semantic_scholar")
        if (
            semantic_data
            and isinstance(semantic_data, dict)
            and semantic_data.get("reference_count")
        ):
            references["count"] = max(references.get("count", 0), semantic_data["reference_count"])

        # OpenAlex reference/citation counts
        openalex_data = results.get("openalex")
        if openalex_data and isinstance(openalex_data, dict):
            if openalex_data.get("referenced_works_count"):
                references["count"] = max(
                    references.get("count", 0), openalex_data["referenced_works_count"]
                )
            if openalex_data.get("cited_by_count"):
                references["cited_by_count"] = openalex_data["cited_by_count"]
            if openalex_data.get("related_works"):
                references["related_works"] = openalex_data["related_works"]

        return {"references": references} if references else {}

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
        self._process_semantic_scholar_authors(results, all_authors)
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
        if not isinstance(cr_authors, list):
            return

        for author in cr_authors:
            if not isinstance(author, dict):
                continue
            name = (author.get("name") or "").strip()
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
        if not isinstance(oa_authors, list):
            return

        for author in oa_authors:
            if not isinstance(author, dict):
                continue
            name = (author.get("display_name") or "").strip()
            if not name:
                continue
            key = name.lower()
            institutions = []
            author_institutions = author.get("institutions", [])
            if isinstance(author_institutions, list):
                for inst in author_institutions:
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

    def _process_semantic_scholar_authors(
        self, results: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process authors from Semantic Scholar."""
        semantic_data = results.get("semantic_scholar")
        if not semantic_data or not isinstance(semantic_data, dict):
            return

        ss_authors = semantic_data.get("authors", [])
        if not isinstance(ss_authors, list):
            return

        for author in ss_authors:
            if not isinstance(author, dict):
                continue
            self._process_single_semantic_scholar_author(author, all_authors)

    def _process_single_semantic_scholar_author(
        self, author: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process a single author from Semantic Scholar."""
        name = (author.get("name") or "").strip()
        if not name:
            return
        key = name.lower()

        affiliations = self._extract_semantic_scholar_affiliations(author)

        if key not in all_authors:
            self._create_semantic_scholar_author_entry(
                author, name, affiliations, all_authors, key
            )
        else:
            self._update_semantic_scholar_author_entry(author, affiliations, all_authors, key)

    def _extract_semantic_scholar_affiliations(
        self, author: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract affiliations from a Semantic Scholar author."""
        affiliations = []
        author_affiliations = author.get("affiliations", [])
        if isinstance(author_affiliations, list):
            for affil in author_affiliations:
                if isinstance(affil, str):
                    affiliations.append({"name": affil})
                elif isinstance(affil, dict):
                    affiliations.append(affil)
        return affiliations

    def _create_semantic_scholar_author_entry(
        self,
        author: dict[str, Any],
        name: str,
        affiliations: list[dict[str, Any]],
        all_authors: dict[str, dict[str, Any]],
        key: str,
    ) -> None:
        """Create a new author entry from Semantic Scholar data."""
        all_authors[key] = {
            "name": name,
            "author_id": author.get("author_id"),
            "semantic_scholar_id": author.get("author_id"),
            "affiliations": affiliations if affiliations else None,
            "sources": ["semantic_scholar"],
        }

    def _update_semantic_scholar_author_entry(
        self,
        author: dict[str, Any],
        affiliations: list[dict[str, Any]],
        all_authors: dict[str, dict[str, Any]],
        key: str,
    ) -> None:
        """Update an existing author entry with Semantic Scholar data."""
        existing = all_authors[key]
        if not existing.get("semantic_scholar_id") and author.get("author_id"):
            existing["semantic_scholar_id"] = author.get("author_id")
        if not existing.get("affiliations") and affiliations:
            existing["affiliations"] = affiliations
        existing["sources"].append("semantic_scholar")

    def _process_datacite_authors(
        self, results: dict[str, Any], all_authors: dict[str, dict[str, Any]]
    ) -> None:
        """Process authors from DataCite."""
        datacite_data = results.get("datacite")
        if not datacite_data or not isinstance(datacite_data, dict):
            return

        dc_creators = datacite_data.get("creators", [])
        if not isinstance(dc_creators, list):
            return

        for creator in dc_creators:
            if not isinstance(creator, dict):
                continue
            name = (creator.get("name") or "").strip()
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

    def _apply_ror_enrichment_to_authors(  # noqa: C901
        self,
        merged: dict[str, Any],
        results: dict[str, Any],
    ) -> None:
        """
        Apply ROR enrichment data to institutions in author records.

        Parameters
        ----------
        merged : dict
            Merged data dictionary (modified in-place)
        results : dict
            Raw results from all sources including ROR data
        """
        ror_data = results.get("ror")
        if not ror_data:
            return

        authors = merged.get("authors", [])
        if not authors:
            return

        # Create a mapping of normalized ROR IDs to ROR data
        ror_mapping = {}
        for ror_id, data in ror_data.items():
            # Normalize the ROR ID for consistent matching
            normalized_id = ror_id
            if ror_id.startswith("https://ror.org/"):
                normalized_id = ror_id[len("https://ror.org/") :]
            ror_mapping[normalized_id] = data

        # Apply ROR enrichment to each author's institutions
        for author in authors:
            if not isinstance(author, dict):
                continue

            institutions = author.get("institutions", [])
            for inst in institutions:
                if not isinstance(inst, dict):
                    continue

                # Skip institutions that are already ROR-enriched
                if inst.get("ror_enriched"):
                    continue

                ror_id = inst.get("ror_id")
                if not ror_id:
                    continue

                # Normalize the institution's ROR ID
                normalized_ror_id = ror_id
                if ror_id.startswith("https://ror.org/"):
                    normalized_ror_id = ror_id[len("https://ror.org/") :]

                # Find matching ROR data
                ror_info = ror_mapping.get(normalized_ror_id)
                if ror_info:
                    # Enrich the institution with ROR data
                    self._enrich_institution_with_ror(inst, ror_info)

    def _enrich_institution_with_ror(  # noqa: C901
        self,
        institution: dict[str, Any],
        ror_data: dict[str, Any],
    ) -> None:
        """
        Enrich a single institution dictionary with ROR data.

        Parameters
        ----------
        institution : dict
            Institution data from author affiliations (modified in-place)
        ror_data : dict
            ROR API response data
        """
        # Add basic ROR information
        if not institution.get("country") and ror_data.get("country"):
            institution["country"] = ror_data["country"]
        if not institution.get("country_code") and ror_data.get("country_code"):
            institution["country_code"] = ror_data["country_code"]
        if not institution.get("city") and ror_data.get("city"):
            institution["city"] = ror_data["city"]
        if not institution.get("latitude") and ror_data.get("latitude"):
            institution["latitude"] = ror_data["latitude"]
        if not institution.get("longitude") and ror_data.get("longitude"):
            institution["longitude"] = ror_data["longitude"]

        # Add institution type if not present
        if not institution.get("type") and ror_data.get("types"):
            institution["type"] = ror_data["types"][0] if ror_data["types"] else None

        # Add website if not present
        if not institution.get("website") and ror_data.get("website"):
            institution["website"] = ror_data["website"]

        # Add established year
        if not institution.get("established") and ror_data.get("established"):
            institution["established"] = ror_data["established"]

        # Add external IDs from ROR
        external_ids = institution.get("external_ids", [])
        ror_external_ids = ror_data.get("external_ids", [])
        for ror_ext_id in ror_external_ids:
            ext_type = ror_ext_id.get("type")
            preferred = ror_ext_id.get("preferred")
            if ext_type and preferred:
                # Check if this external ID type already exists
                existing_types = {eid.get("type") for eid in external_ids}
                if ext_type not in existing_types:
                    external_ids.append(
                        {
                            "type": ext_type,
                            "preferred": preferred,
                            "all": ror_ext_id.get("all", [preferred]),
                        }
                    )

        if external_ids:
            institution["external_ids"] = external_ids

        # Add relationships and domains
        if not institution.get("relationships") and ror_data.get("relationships"):
            institution["relationships"] = ror_data["relationships"]
        if not institution.get("domains") and ror_data.get("domains"):
            institution["domains"] = ror_data["domains"]

        # Mark that this institution has been enriched with ROR
        institution["ror_enriched"] = True
