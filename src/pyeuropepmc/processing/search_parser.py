import logging
from typing import Any

import defusedxml.ElementTree as ET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.models import AuthorEntity, InstitutionEntity, JournalEntity, PaperEntity

# Type aliases for better readability
ParsedResult = dict[str, str | list[str]]
ParsedResults = list[ParsedResult]

# XML Namespace constants
XML_NAMESPACES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


class EuropePMCParser:
    """Parser for Europe PMC search API responses in various formats (JSON, XML, DC)."""

    logger = logging.getLogger("EuropePMCParser")

    @staticmethod
    def parse_csv(csv_str: str) -> list[dict[str, Any]]:
        """Parse Europe PMC CSV response and return a list of result dictionaries.

        Args:
            csv_str: CSV string from Europe PMC API

        Returns:
            List of parsed result dictionaries

        Raises:
            ParsingError: If CSV parsing fails
        """
        return EuropePMCParser._handle_parsing_errors(
            EuropePMCParser._parse_csv_data, csv_str, "CSV"
        )

    @staticmethod
    def _parse_csv_data(csv_str: str) -> list[dict[str, Any]]:
        """Internal method to parse CSV data without error handling."""
        import csv
        from io import StringIO

        reader = csv.DictReader(StringIO(csv_str))
        return [row for row in reader]

    @staticmethod
    def parse_json(data: Any) -> list[dict[str, str | list[str]]]:
        """Parse Europe PMC JSON response and return a list of result dictionaries.

        Args:
            data: JSON data from Europe PMC API (dict or list)

        Returns:
            List of parsed result dictionaries

        Raises:
            ParsingError: If data format is invalid or parsing fails
        """
        if data is None or (isinstance(data, str) and not data.strip()):
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        return EuropePMCParser._handle_parsing_errors(
            EuropePMCParser._parse_json_data, data, "JSON"
        )

    @staticmethod
    def _parse_json_data(data: Any) -> list[dict[str, str | list[str]]]:
        """Internal method to parse JSON data without error handling."""
        if data is None:
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        if isinstance(data, dict):
            return EuropePMCParser._extract_results_from_dict(data)
        elif isinstance(data, list):
            return EuropePMCParser._validate_result_list(data)
        else:
            EuropePMCParser._raise_format_error("dict or list", type(data).__name__)
            return []

    @staticmethod
    def _extract_results_from_dict(data: dict[str, Any]) -> list[dict[str, str | list[str]]]:
        """Extract results from Europe PMC API dictionary response."""
        if not isinstance(data, dict):
            EuropePMCParser._raise_format_error("dict", type(data).__name__)
        results = data.get("resultList", {}).get("result", [])
        return EuropePMCParser._validate_result_list(results)

    @staticmethod
    def _validate_result_list(results: Any) -> list[dict[str, str | list[str]]]:
        """
        Validate that results is a list of dictionaries.
        Log and report errors for invalid items.
        """
        if results is None:
            return []
        if not isinstance(results, list):
            EuropePMCParser.logger.error(
                f"Result list parsing failed: Expected list but got "
                f"{type(results).__name__}. Returning empty results."
            )
            EuropePMCParser.logger.debug(f"Invalid results value: {results!r}")
            return []
        valid_items = []
        invalid_items = []
        for idx, item in enumerate(results):
            if isinstance(item, dict):
                valid_items.append(item)
            else:
                EuropePMCParser.logger.error(
                    f"Result item parsing failed at index {idx}: Expected dict but got "
                    f"{type(item).__name__}. Item: {item!r}"
                )
                invalid_items.append((idx, item))
        if invalid_items:
            EuropePMCParser.logger.warning(
                f"Found {len(invalid_items)} invalid items in results. "
                f"Only valid items will be returned."
            )
        return valid_items

    @staticmethod
    def _handle_parsing_errors(
        parse_func: Any, data: Any, format_type: str
    ) -> list[dict[str, str | list[str]]]:
        """Generic error handling wrapper for parsing functions."""
        try:
            result = parse_func(data)
            if not isinstance(result, list):
                return []
            return result
        except ParsingError:
            raise
        except ET.ParseError as e:
            error_msg = f"{format_type} parsing error: {e}. The response appears malformed."
            EuropePMCParser.logger.error(error_msg)
            raise ParsingError(
                ErrorCodes.PARSE002, {"error": str(e), "format": format_type, "message": error_msg}
            ) from e
        except Exception as e:
            error_msg = f"Unexpected {format_type} parsing error: {e}"
            EuropePMCParser.logger.error(error_msg)
            raise ParsingError(
                ErrorCodes.PARSE003, {"error": str(e), "format": format_type, "message": error_msg}
            ) from e

    @staticmethod
    def _raise_format_error(expected: str, actual: str) -> None:
        """Raise a standardized format error."""
        error_msg = f"Invalid data format: expected {expected}, got {actual}"
        EuropePMCParser.logger.error(error_msg)
        context = {"expected_type": expected, "actual_type": actual}
        raise ParsingError(ErrorCodes.PARSE001, context)

    @staticmethod
    def parse_xml(xml_str: str) -> list[dict[str, str | list[str]]]:
        """Parse Europe PMC XML response and return a list of result dictionaries.

        Args:
            xml_str: XML string from Europe PMC API

        Returns:
            List of parsed result dictionaries

        Raises:
            ParsingError: If XML parsing fails
        """
        if xml_str is None or not isinstance(xml_str, str) or not xml_str.strip():
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        return EuropePMCParser._handle_parsing_errors(
            EuropePMCParser._parse_xml_data, xml_str, "XML"
        )

    @staticmethod
    def _parse_xml_data(xml_str: str) -> list[dict[str, str | list[str]]]:
        """
        Internal method to parse XML data without error handling.
        Logs errors for malformed records.
        """
        if xml_str is None or not isinstance(xml_str, str) or not xml_str.strip():
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            error_msg = f"XML parsing error: {e}. The response appears malformed."
            EuropePMCParser.logger.error(error_msg)
            raise ParsingError(ErrorCodes.PARSE002, {"error": str(e), "message": error_msg}) from e
        results = []
        result_elems = root.findall(".//resultList/result")
        if not result_elems:
            error_msg = "No <resultList>/<result> elements found in XML."
            EuropePMCParser.logger.error(error_msg)
            raise ParsingError(ErrorCodes.PARSE004, {"message": error_msg, "__str__": error_msg})
        for idx, result_elem in enumerate(result_elems):
            try:
                record = EuropePMCParser._extract_xml_element_data(result_elem)
                results.append(record)
            except Exception as e:
                EuropePMCParser.logger.error(
                    f"XML record parsing failed at index {idx}: {type(e).__name__}: {e}. "
                    f"Element: {ET.tostring(result_elem, encoding='unicode')}"
                )
        return results

    @staticmethod
    def _extract_xml_element_data(element: Any) -> dict[str, str | list[str]]:
        """Extract data from a single XML element."""
        return {child.tag: child.text for child in element}

    @staticmethod
    def parse_dc(dc_str: str) -> list[dict[str, str | list[str]]]:
        """Parse Europe PMC Dublin Core XML response and return result dictionaries.

        Args:
            dc_str: Dublin Core XML string from Europe PMC API

        Returns:
            List of parsed result dictionaries

        Raises:
            ParsingError: If DC XML parsing fails
        """
        if dc_str is None or not isinstance(dc_str, str) or not dc_str.strip():
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        return EuropePMCParser._handle_parsing_errors(
            EuropePMCParser._parse_dc_data, dc_str, "Dublin Core XML"
        )

    @staticmethod
    def _parse_dc_data(dc_str: str) -> list[dict[str, str | list[str]]]:
        """
        Internal method to parse Dublin Core XML data without error handling.
        Logs errors for malformed records.
        """
        if dc_str is None or not isinstance(dc_str, str) or not dc_str.strip():
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": "Content cannot be None or empty."}
            )
        try:
            root = ET.fromstring(dc_str)
        except ET.ParseError as e:
            error_msg = f"DC XML parsing error: {e}. The response appears malformed."
            EuropePMCParser.logger.error(error_msg)
            raise ParsingError(ErrorCodes.PARSE002, {"error": str(e), "message": error_msg}) from e
        results = []
        for idx, desc in enumerate(root.findall(".//rdf:Description", XML_NAMESPACES)):
            try:
                record = EuropePMCParser._extract_dc_description_data(desc)
                results.append(record)
            except Exception as e:
                EuropePMCParser.logger.error(
                    f"DC record parsing failed at index {idx}: {type(e).__name__}: {e}. "
                    f"Element: {ET.tostring(desc, encoding='unicode')}"
                )
        return results

    @staticmethod
    def _extract_dc_description_data(description: Any) -> dict[str, str | list[str]]:
        """Extract data from a Dublin Core description element."""
        result: dict[str, str | list[str]] = {}
        for child in description:
            tag = EuropePMCParser._remove_namespace_from_tag(child.tag)
            EuropePMCParser._add_tag_to_result(result, tag, child.text)
        # Defensive: ensure 'title' key exists for tests expecting it
        if "title" not in result:
            result["title"] = ""
        return result

    @staticmethod
    def _remove_namespace_from_tag(tag: str) -> str:
        """Remove XML namespace from tag name."""
        return tag.split("}", 1)[-1] if "}" in tag else tag

    @staticmethod
    def _add_tag_to_result(result: dict[str, str | list[str]], tag: str, text: str | None) -> None:
        """Add tag-text pair to result, handling multiple values."""
        if tag in result:
            EuropePMCParser._handle_duplicate_tag(result, tag, text)
        else:
            if text is not None:
                result[tag] = text

    @staticmethod
    def _handle_duplicate_tag(
        result: dict[str, str | list[str]], tag: str, text: str | None
    ) -> None:
        """Handle duplicate tags by converting to list of strings only."""
        val = result[tag]
        if isinstance(val, list):
            # Flatten if nested list
            flat_list: list[str] = []
            for v in val:
                if isinstance(v, list):
                    flat_list.extend([str(x) for x in v])
                else:
                    flat_list.append(str(v))
            if text is not None:
                flat_list.append(str(text))
            result[tag] = flat_list
        else:
            if text is not None:
                result[tag] = [str(val), str(text)]
            else:
                result[tag] = [str(val)]

    # Entity creation methods (moved from converters)

    @staticmethod
    def parse_affiliation_string(affiliation_text: str) -> InstitutionEntity:
        """
        Parse an affiliation string into an InstitutionEntity.

        This function attempts to extract institution name, department, city, state/country
        from common affiliation string patterns.

        Parameters
        ----------
        affiliation_text : str
            Raw affiliation text from Europe PMC

        Returns
        -------
        InstitutionEntity
            Parsed institution entity
        """
        if not affiliation_text or not affiliation_text.strip():
            return InstitutionEntity(display_name="")

        text = affiliation_text.strip()

        # Split by commas and clean up
        parts = [part.strip() for part in text.split(",") if part.strip()]

        if not parts:
            return InstitutionEntity(display_name=text)

        # Initialize variables
        institution_name = ""
        department = ""
        city = ""
        country = ""

        # Common country patterns
        country_patterns = [
            "USA",
            "United States",
            "UK",
            "United Kingdom",
            "Germany",
            "France",
            "Italy",
            "Spain",
            "Canada",
            "Australia",
            "Japan",
            "China",
            "India",
        ]

        # Check if last part is a country
        if len(parts) >= 2 and any(
            country.lower() in parts[-1].lower() for country in country_patterns
        ):
            country = parts[-1]
            remaining_parts = parts[:-1]
        else:
            remaining_parts = parts

        # Try to extract city from remaining parts (often the second-to-last part)
        if len(remaining_parts) >= 2:
            # Check if second-to-last part looks like a city (not containing department keywords)
            potential_city = remaining_parts[-1]
            dept_keywords = [
                "department",
                "school",
                "faculty",
                "institute",
                "center",
                "program",
                "division",
                "section",
                "unit",
                "group",
                "laboratory",
                "lab",
                "college",
                "university",
                "hospital",
                "clinic",
                "foundation",
                "association",
            ]
            # If the potential city doesn't contain department keywords and is reasonably short,
            # treat it as a city
            if (
                not any(dept in potential_city.lower() for dept in dept_keywords)
                and len(potential_city.split()) <= 3
            ):  # Cities are usually 1-3 words
                city = potential_city
                remaining_parts = remaining_parts[:-1]

        # The remaining parts are likely institution name and possibly department
        if remaining_parts:
            first_part = remaining_parts[0]
            # Check if first part looks like a department
            dept_keywords = [
                "department",
                "school",
                "faculty",
                "institute",
                "center",
                "program",
                "division",
                "section",
                "unit",
                "group",
                "laboratory",
                "lab",
            ]
            if any(dept in first_part.lower() for dept in dept_keywords):
                department = first_part
                institution_name = ", ".join(remaining_parts[1:])
            else:
                institution_name = ", ".join(remaining_parts)

        # If we still don't have a clear institution name, use the whole text
        if not institution_name:
            institution_name = text

        # Clean up institution name (remove email addresses, etc.)
        institution_name = institution_name.split("Electronic address:")[0].strip()
        institution_name = institution_name.split("E-mail:")[0].strip()
        institution_name = institution_name.split("Email:")[0].strip()

        return InstitutionEntity(
            display_name=institution_name,
            city=city if city else None,
            country=country if country else None,
            institution_type=department if department else None,
        )

    @staticmethod
    def extract_authors_and_entities(
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[AuthorEntity], list[InstitutionEntity]]:
        """Extract authors and create AuthorEntity and InstitutionEntity objects
        from search result."""
        authors = []
        author_entities = []
        institution_entities = []
        author_list = result.get("authorList", {}).get("author", [])

        # Extract ORCIDs from authorIdList as fallback
        author_id_list = result.get("authorIdList", {}).get("authorId", [])
        available_orcids = [
            aid.get("value") for aid in author_id_list if aid.get("type") == "ORCID"
        ]

        if isinstance(author_list, list):
            for author in author_list:
                # Extract ORCID from author object first
                orcid = (
                    author.get("authorId", {}).get("value")
                    if author.get("authorId", {}).get("type") == "ORCID"
                    else None
                )

                # If no ORCID in author object, try to assign from available ORCIDs
                if not orcid and available_orcids:
                    orcid = available_orcids.pop(0)

                author_dict = {
                    "full_name": author.get("fullName"),
                    "first_name": author.get("firstName"),
                    "last_name": author.get("lastName"),
                    "initials": author.get("initials"),
                    "orcid": orcid,
                }
                # Add affiliations if available
                affiliations = []
                affiliation_details = author.get("authorAffiliationDetailsList", {}).get(
                    "authorAffiliation", []
                )
                if isinstance(affiliation_details, list):
                    affiliations = [
                        aff.get("affiliation")
                        for aff in affiliation_details
                        if aff.get("affiliation")
                    ]
                if affiliations:
                    author_dict["affiliations"] = affiliations
                authors.append(author_dict)

                # Create InstitutionEntity objects from affiliations
                author_institutions = []
                for affiliation_text in affiliations:
                    institution_entity = EuropePMCParser.parse_affiliation_string(affiliation_text)
                    if institution_entity.display_name:  # Only add if we have a name
                        author_institutions.append(institution_entity)
                        institution_entities.append(institution_entity)

                # Create AuthorEntity object with institutions
                author_entity = AuthorEntity(
                    full_name=author.get("fullName"),
                    first_name=author.get("firstName"),
                    last_name=author.get("lastName"),
                    initials=author.get("initials"),
                    orcid=orcid,
                    affiliation_text=", ".join(affiliations) if affiliations else None,
                    institutions=author_institutions if author_institutions else None,
                )
                author_entities.append(author_entity)

        return authors, author_entities, institution_entities

    @staticmethod
    def extract_keywords_and_mesh(result: dict[str, Any]) -> list[str]:
        """Extract keywords and MeSH terms from search result."""
        keywords = []
        # Add keywords from keywordList
        keyword_list = result.get("keywordList", {}).get("keyword", [])
        if isinstance(keyword_list, list):
            keywords.extend(keyword_list)
        elif isinstance(keyword_list, str):
            keywords.append(keyword_list)

        # Add MeSH descriptors as keywords for backward compatibility
        mesh_headings = result.get("meshHeadingList", {}).get("meshHeading", [])
        if isinstance(mesh_headings, list):
            for mesh in mesh_headings:
                descriptor = mesh.get("descriptorName")
                if descriptor and mesh.get("majorTopic_YN") == "Y":
                    keywords.append(f"MeSH:{descriptor}")

        return keywords

    @staticmethod
    def extract_mesh_headings(result: dict[str, Any]) -> list[Any]:
        """
        Extract structured MeSH headings from search result.

        Parameters
        ----------
        result : dict
            Search result dictionary from Europe PMC API

        Returns
        -------
        list[MeSHHeadingEntity]
            List of structured MeSH heading entities with qualifiers
        """
        from pyeuropepmc.models.mesh import MeSHHeadingEntity

        mesh_headings = []
        mesh_heading_list = result.get("meshHeadingList", {}).get("meshHeading", [])

        if isinstance(mesh_heading_list, list):
            for mesh_data in mesh_heading_list:
                try:
                    heading = MeSHHeadingEntity.from_dict(mesh_data)
                    mesh_headings.append(heading)
                except (KeyError, ValueError) as e:
                    # Log warning but continue processing
                    descriptor = mesh_data.get("descriptorName", "unknown")
                    print(f"Warning: Failed to parse MeSH heading '{descriptor}': {e}")

        return mesh_headings

    @staticmethod
    def extract_open_access_info(
        result: dict[str, Any],
    ) -> tuple[bool, bool, bool, bool, str | None]:
        """Extract open access information from search result."""
        is_open_access = result.get("isOpenAccess") == "Y"
        in_epmc = result.get("inEPMC") == "Y"
        in_pmc = result.get("inPMC") == "Y"
        has_pdf = result.get("hasPDF") == "Y"

        # Extract URLs
        full_text_urls = result.get("fullTextUrlList", {}).get("fullTextUrl", [])
        oa_url = None
        if isinstance(full_text_urls, list):
            for url_info in full_text_urls:
                if url_info.get("availabilityCode") == "OA":
                    oa_url = url_info.get("url")
                    break

        return is_open_access, in_epmc, in_pmc, has_pdf, oa_url

    @staticmethod
    def extract_citation_info(
        result: dict[str, Any],
    ) -> tuple[int | None, bool, bool, bool, bool, bool]:
        """Extract citation and reference information from search result."""
        cited_by_count = result.get("citedByCount")
        has_references = result.get("hasReferences") == "Y"
        has_text_mined_terms = result.get("hasTextMinedTerms") == "Y"
        has_db_cross_references = result.get("hasDbCrossReferences") == "Y"
        has_labs_links = result.get("hasLabsLinks") == "Y"
        has_tm_accession_numbers = result.get("hasTMAccessionNumbers") == "Y"

        return (
            int(cited_by_count) if cited_by_count is not None else None,
            has_references,
            has_text_mined_terms,
            has_db_cross_references,
            has_labs_links,
            has_tm_accession_numbers,
        )

    @staticmethod
    def extract_publication_metadata(
        result: dict[str, Any],
    ) -> tuple[str | None, list[dict[str, Any]], dict[str, Any] | None]:
        """Extract publication type, funders, and license information from search result."""
        # Extract publication type
        pub_type_list = result.get("pubTypeList", {}).get("pubType", [])
        pub_type = pub_type_list[0] if isinstance(pub_type_list, list) and pub_type_list else None

        # Extract grant/funder information
        funders = []
        grants_list = result.get("grantsList", {}).get("grant", [])
        if isinstance(grants_list, list):
            for grant in grants_list:
                funder_dict = {
                    "agency": grant.get("agency"),
                    "grant_id": grant.get("grantId"),
                    "acronym": grant.get("acronym"),
                }
                funders.append(funder_dict)

        # Extract license information if available
        license_info = result.get("license")

        return pub_type, funders, license_info

    @staticmethod
    def create_paper_entity_from_result(
        result: dict[str, Any],
    ) -> tuple[PaperEntity, dict[str, Any]]:
        """Create a comprehensive PaperEntity from search result data."""
        # Extract basic identifiers
        doi = result.get("doi")
        pmcid = result.get("pmcid")
        pmid = result.get("pmid")

        # Extract journal information
        journal_info = result.get("journalInfo", {})
        journal_title = journal_info.get("journal", {}).get("title") or result.get("journalTitle")
        journal_issn = journal_info.get("journal", {}).get("issn")
        volume = journal_info.get("volume")
        issue = journal_info.get("issue")
        page_info = result.get("pageInfo")

        # Create JournalEntity if journal information is available
        journal_entity = None
        if journal_title or journal_issn:
            journal_entity = JournalEntity.from_search_result(
                {
                    "title": journal_title,
                    "issn": journal_issn,
                }
            )

        # Extract publication dates
        pub_year = result.get("pubYear")
        first_publication_date = result.get("firstPublicationDate")
        first_index_date = result.get("firstIndexDate")

        # Extract authors and entities
        authors, author_entities, institution_entities = (
            EuropePMCParser.extract_authors_and_entities(result)
        )
        keywords = EuropePMCParser.extract_keywords_and_mesh(result)
        is_open_access, in_epmc, in_pmc, has_pdf, oa_url = (
            EuropePMCParser.extract_open_access_info(result)
        )
        (
            cited_by_count,
            has_references,
            has_text_mined_terms,
            has_db_cross_references,
            has_labs_links,
            has_tm_accession_numbers,
        ) = EuropePMCParser.extract_citation_info(result)
        pub_type, funders, license_info = EuropePMCParser.extract_publication_metadata(result)

        # Create the PaperEntity with all extracted information
        paper_entity = PaperEntity(
            # Basic identifiers
            doi=doi,
            pmcid=pmcid,
            pmid=pmid,
            title=result.get("title"),
            abstract=result.get("abstractText"),
            # Publication metadata
            journal=journal_entity,
            volume=volume,
            issue=issue,
            pages=page_info,
            publication_year=int(pub_year) if pub_year else None,
            first_page=None,  # Could be extracted from page_info if needed
            last_page=None,  # Could be extracted from page_info if needed
            # Authors and keywords
            authors=authors,  # Keep author dictionaries for backward compatibility
            keywords=keywords,
            # Open access and availability
            is_oa=is_open_access,
            oa_url=oa_url,
            has_pdf=has_pdf,
            in_epmc=in_epmc,
            in_pmc=in_pmc,
            # Citation and reference metrics
            cited_by_count=cited_by_count,
            # Publication metadata
            pub_type=pub_type,
            journal_issn=journal_issn,
            page_info=page_info,
            # Indexing and availability flags
            has_references=has_references,
            has_text_mined_terms=has_text_mined_terms,
            has_db_cross_references=has_db_cross_references,
            has_labs_links=has_labs_links,
            has_tm_accession_numbers=has_tm_accession_numbers,
            # Dates
            first_index_date=first_index_date,
            first_publication_date=first_publication_date,
            # Additional metadata
            funders=funders,
            license=license_info,
        )

        # Return both the paper entity and related entities
        related_entities = {"authors": author_entities, "institutions": institution_entities}
        return paper_entity, related_entities

    @staticmethod
    def parse_search_results_with_entities(
        search_results: list[dict[str, Any]] | dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Parse search results and create entities_data format suitable for RDF conversion."""
        entities_data = []

        # Handle both single result and list of results
        results_list = [search_results] if isinstance(search_results, dict) else search_results

        for result in results_list:
            try:
                # Create a comprehensive paper entity from search result
                paper_entity, related_entities = EuropePMCParser.create_paper_entity_from_result(
                    result
                )
                entities_data.append(
                    {
                        "entity": paper_entity,
                        "related_entities": related_entities,
                    }
                )
            except Exception as e:
                EuropePMCParser.logger.warning(f"Failed to process search result: {e}")
                continue

        return entities_data
