import logging
import re
from typing import Any

import defusedxml.ElementTree as ET

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ParsingError

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
    def validate_search_result(result: dict[str, Any]) -> dict[str, Any]:
        """Validate and clean a search result dictionary.

        Args:
            result: Raw search result dictionary

        Returns:
            Validated and cleaned result dictionary
        """
        if not isinstance(result, dict):
            raise ParsingError(
                ErrorCodes.PARSE003, {"message": f"Expected dict, got {type(result).__name__}"}
            )

        # Basic validation - ensure we have some form of identifier
        identifiers = [result.get("doi"), result.get("pmcid"), result.get("pmid")]
        if not any(identifiers):
            EuropePMCParser.logger.warning("Search result missing identifiers (doi, pmcid, pmid)")

        # Clean and normalize common fields
        cleaned = {}
        for key, value in result.items():
            if isinstance(value, str):
                cleaned[key] = value.strip()
            elif isinstance(value, dict):
                cleaned[key] = EuropePMCParser._clean_nested_dict(value)
            elif isinstance(value, list):
                cleaned[key] = EuropePMCParser._clean_list(value)
            else:
                cleaned[key] = value

        return cleaned

    @staticmethod
    def _clean_nested_dict(data: dict[str, Any]) -> dict[str, Any]:
        """Clean nested dictionary values."""
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = value.strip()
            else:
                cleaned[key] = value
        return cleaned

    @staticmethod
    def _clean_list(data: list[Any]) -> list[Any]:
        """Clean list values."""
        cleaned = []
        for item in data:
            if isinstance(item, str):
                cleaned.append(item.strip())
            elif isinstance(item, dict):
                cleaned.append(EuropePMCParser._clean_nested_dict(item))
            else:
                cleaned.append(item)
        return cleaned

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
    def parse_affiliation_string(text: str) -> "InstitutionEntity":
        """
        Parse affiliation string into InstitutionEntity with enhanced institution type detection.

        This method uses improved pattern recognition to extract institution information
        and determine institution type based on keywords and context.

        Parameters
        ----------
        text : str
            Raw affiliation text from Europe PMC

        Returns
        -------
        InstitutionEntity
            Parsed institution entity with extracted information
        """
        from pyeuropepmc.models import InstitutionEntity, InstitutionType

        if not text or not text.strip():
            return InstitutionEntity(display_name="Unknown Institution")

        # Clean the input text
        text = text.strip()

        # Split by commas to get components
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if not parts:
            return InstitutionEntity(display_name="Unknown Institution")

        # Parse affiliation using pattern recognition
        # Common patterns: [Department,] Institution [, City] [, State/Postal] [, Country]

        # Initialize
        department = ""
        institution_name = ""
        city = None
        country = None
        confidence = 0.1

        # Start from the end and work backwards
        remaining_parts = parts[:]

        # 1. Extract country (if last part matches country pattern)
        country_patterns = [
            "USA",
            "United States",
            "United States of America",
            "UK",
            "United Kingdom",
            "Great Britain",
            "Canada",
            "Australia",
            "Germany",
            "France",
            "Italy",
            "Spain",
            "Japan",
            "China",
            "India",
            "Russia",
            "Brazil",
            "Mexico",
            "Argentina",
            "Chile",
            "Colombia",
            "South Africa",
            "Israel",
            "Turkey",
            "Netherlands",
            "Belgium",
            "Switzerland",
            "Austria",
            "Sweden",
            "Norway",
            "Denmark",
            "Finland",
            "Poland",
            "Czech Republic",
            "Hungary",
            "Portugal",
            "Greece",
            "Ireland",
            "New Zealand",
            "Singapore",
            "South Korea",
            "Taiwan",
            "Thailand",
            "Malaysia",
            "Philippines",
            "Vietnam",
            "Indonesia",
            "Pakistan",
            "Bangladesh",
            "Egypt",
            "Saudi Arabia",
            "UAE",
            "United Arab Emirates",
        ]

        if remaining_parts and any(
            country.lower() in remaining_parts[-1].lower() for country in country_patterns
        ):
            country = remaining_parts.pop()
            confidence += 0.2

        # 2. Extract city/address (next part from end, if it looks like location)
        if remaining_parts:
            potential_city = remaining_parts[-1]

            # Heuristics for identifying city/location:
            # - Contains postal code
            # - Contains state abbreviation
            # - Is a known city name
            # - Is short and doesn't contain institution keywords
            has_postal = bool(re.search(r"\d{5}", potential_city))
            has_state = bool(re.search(r"\b[A-Z]{2}\b", potential_city))
            known_cities = [
                "Boston",
                "New York",
                "London",
                "Paris",
                "Berlin",
                "Tokyo",
                "San Francisco",
                "Los Angeles",
                "Chicago",
                "Stanford",
                "Cambridge",
                "Heidelberg",
                "Munich",
                "Bethesda",
                "Rockville",
            ]
            is_known_city = any(city in potential_city for city in known_cities)

            institution_keywords = [
                "university",
                "college",
                "institute",
                "center",
                "hospital",
                "school",
                "department",
                "faculty",
                "laboratory",
                "foundation",
                "association",
                "corporation",
                "company",
                "national",
                "federal",
            ]

            has_institution_word = any(
                word in potential_city.lower() for word in institution_keywords
            )
            is_short_location = len(potential_city.split()) <= 3 and len(potential_city) <= 20

            if (
                has_postal
                or has_state
                or is_known_city
                or (is_short_location and not has_institution_word)
            ):
                city = potential_city
                remaining_parts.pop()
                confidence += 0.15

        # 3. Extract department (if first remaining part looks like department)
        if remaining_parts:
            dept_keywords = [
                "department",
                "dept",
                "faculty",
                "institute",
                "center",
                "centre",
                "program",
                "division",
                "section",
                "unit",
                "group",
                "laboratory",
                "lab",
                "clinic",
                "chair",
            ]

            first_part = remaining_parts[0]
            # Be more specific about department detection - avoid false positives like "Medical School"
            is_department = False
            first_lower = first_part.lower()
            for keyword in dept_keywords:
                if keyword in first_lower:
                    # Check if it's actually a department (e.g., "Department of X" or "X Department")
                    # Avoid false positives like "Medical School" where "school" is part of the institution name
                    if keyword in [
                        "department",
                        "dept",
                        "faculty",
                        "institute",
                        "center",
                        "centre",
                        "program",
                        "division",
                        "section",
                        "unit",
                        "group",
                        "laboratory",
                        "lab",
                        "clinic",
                        "chair",
                    ]:
                        # For these, require the keyword to be at the start or have "of" after it
                        if (
                            first_lower.startswith(keyword)
                            or f" {keyword} of" in first_lower
                            or f" {keyword} for" in first_lower
                        ):
                            is_department = True
                            break
                    else:
                        is_department = True
                        break

            if is_department:
                department = first_part
                remaining_parts.pop(0)
                confidence += 0.15

        # 4. Everything else is the institution
        if remaining_parts:
            institution_name = ", ".join(remaining_parts)
        else:
            # If no parts left, this might be a simple institution-only affiliation
            institution_name = text.split(",")[0].strip()

        # Clean up institution name
        institution_name = EuropePMCParser._clean_institution_name(institution_name)

        # Determine institution type
        institution_type = EuropePMCParser._determine_institution_type(
            institution_name, department
        )

        # Final confidence calculation
        if institution_name and institution_name != "Unknown Institution":
            confidence += 0.3
        if institution_type != InstitutionType.other:
            confidence += 0.1

        confidence = max(0.1, min(1.0, confidence))

        return InstitutionEntity(
            display_name=institution_name,
            city=city,
            country=country,
            institution_type=institution_type,
            confidence=confidence,
        )

    @staticmethod
    def _determine_institution_type(institution_name: str, department: str) -> "InstitutionType":
        """
        Determine institution type based on keywords in name and department.

        Parameters
        ----------
        institution_name : str
            Name of the institution
        department : str
            Department name (if any)

        Returns
        -------
        InstitutionType
            Classified institution type
        """
        from pyeuropepmc.models import InstitutionType

        text_to_check = f"{institution_name} {department}".lower()

        # Healthcare institutions
        healthcare_keywords = [
            "hospital",
            "clinic",
            "medical center",
            "medical centre",
            "health",
            "cancer",
            "cardiology",
            "neurology",
            "surgery",
            "medicine",
            "pharmacy",
        ]
        if any(keyword in text_to_check for keyword in healthcare_keywords):
            return InstitutionType.healthcare

        # Educational institutions
        education_keywords = [
            "university",
            "college",
            "school",
            "academy",
            "institute",
            "faculty",
            "department",
            "laboratory",
            "lab",
            "research center",
            "research centre",
        ]
        if any(keyword in text_to_check for keyword in education_keywords):
            return InstitutionType.education

        # Government institutions
        government_keywords = [
            "national",
            "federal",
            "ministry",
            "agency",
            "bureau",
            "office",
            "department of",
            "centers for disease control",
            "nih",
            "nci",
            "fda",
            "national institutes",
            "public health",
        ]
        if any(keyword in text_to_check for keyword in government_keywords):
            return InstitutionType.government

        # Company/corporate
        company_keywords = [
            "inc",
            "ltd",
            "llc",
            "corp",
            "corporation",
            "company",
            "pharma",
            "biotech",
            "therapeutics",
            "biosciences",
            "biomedical",
            "genetics",
        ]
        if any(keyword in text_to_check for keyword in company_keywords):
            return InstitutionType.company

        # Nonprofit/foundation
        nonprofit_keywords = [
            "foundation",
            "association",
            "society",
            "council",
            "alliance",
            "institute for",
            "center for",
            "centre for",
        ]
        if any(keyword in text_to_check for keyword in nonprofit_keywords):
            return InstitutionType.nonprofit

        # Research facility
        facility_keywords = [
            "laboratory",
            "facility",
            "observatory",
            "station",
            "center",
            "centre",
            "park",
            "reserve",
        ]
        if any(keyword in text_to_check for keyword in facility_keywords):
            return InstitutionType.facility

        # Default to other
        return InstitutionType.other

    @staticmethod
    def _clean_institution_name(name: str) -> str:
        """Clean institution name by removing unwanted suffixes and patterns."""
        if not name:
            return ""

        # Remove common unwanted patterns
        patterns_to_remove = [
            r"Electronic address:.*",
            r"E-mail:.*",
            r"Email:.*",
            r"Tel:.*",
            r"Fax:.*",
            r"Phone:.*",
            r"\(\w+\)",  # Remove parenthetical abbreviations at end
        ]

        cleaned = name
        for pattern in patterns_to_remove:
            import re

            cleaned = re.split(pattern, cleaned, flags=re.IGNORECASE)[0].strip()

        # Remove trailing punctuation
        cleaned = cleaned.rstrip(".,;:- ")

        return cleaned

    @staticmethod
    def extract_authors_and_entities(
        result: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list["AuthorEntity"], list["InstitutionEntity"]]:
        """Extract authors and create AuthorEntity and InstitutionEntity objects
        from search result with enhanced role and quality information."""
        from pyeuropepmc.models import AuthorEntity

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
            for idx, author in enumerate(author_list):
                # Extract ORCID from author object first
                orcid = (
                    author.get("authorId", {}).get("value")
                    if author.get("authorId", {}).get("type") == "ORCID"
                    else None
                )

                # If no ORCID in author object, try to assign from available ORCIDs
                if not orcid and available_orcids:
                    orcid = available_orcids.pop(0)

                # Determine author position
                position = EuropePMCParser._determine_author_position(idx, len(author_list))

                # Extract author roles (if available in the data)
                roles = EuropePMCParser._extract_author_roles(author)

                # Calculate author data quality score
                quality_score = EuropePMCParser._calculate_author_quality_score(author, orcid)

                author_dict = {
                    "full_name": author.get("fullName"),
                    "first_name": author.get("firstName"),
                    "last_name": author.get("lastName"),
                    "initials": author.get("initials"),
                    "orcid": orcid,
                    "position": position.value if position else None,
                    "roles": [role.value for role in roles] if roles else None,
                    "quality_score": quality_score,
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
                        # Avoid duplicates
                        if institution_entity not in institution_entities:
                            institution_entities.append(institution_entity)

                # Create AuthorEntity object with enhanced information
                author_entity = AuthorEntity(
                    full_name=author.get("fullName"),
                    first_name=author.get("firstName"),
                    last_name=author.get("lastName"),
                    initials=author.get("initials"),
                    orcid=orcid,
                    affiliation_text=", ".join(affiliations) if affiliations else None,
                    position=position,
                )
                author_entities.append(author_entity)

        return authors, author_entities, institution_entities

    @staticmethod
    def _determine_author_position(index: int, total_authors: int) -> "AuthorPosition | None":
        """Determine the position of an author in the author list."""
        from pyeuropepmc.models import AuthorPosition

        if total_authors == 0:
            return None
        elif index == 0:
            return AuthorPosition.first
        elif index == total_authors - 1:
            return AuthorPosition.last
        elif total_authors <= 3:
            return AuthorPosition.middle
        else:
            return AuthorPosition.middle

    @staticmethod
    def _extract_author_roles(author: dict[str, Any]) -> list["AuthorRole"]:
        """Extract author roles from author data. Currently returns empty list as
        Europe PMC doesn't typically provide role information in search results."""
        # Note: Europe PMC search API doesn't typically include author roles
        # This method is prepared for future enhancements when role data becomes available
        return []

    @staticmethod
    def _calculate_author_quality_score(author: dict[str, Any], orcid: str | None) -> float:
        """Calculate a quality score for author data completeness."""
        score = 0.0
        total_checks = 0

        # Check for full name (high importance)
        if author.get("fullName"):
            score += 1.0
            total_checks += 1
        else:
            total_checks += 1

        # Check for ORCID (high importance for disambiguation)
        if orcid:
            score += 1.0
        total_checks += 1

        # Check for first/last name
        if author.get("firstName") and author.get("lastName"):
            score += 0.8
        elif author.get("firstName") or author.get("lastName"):
            score += 0.4
        total_checks += 1

        # Check for affiliations
        affiliations = author.get("authorAffiliationDetailsList", {}).get("authorAffiliation", [])
        if affiliations and len(affiliations) > 0:
            score += 0.6
        total_checks += 1

        return score / total_checks if total_checks > 0 else 0.0

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
        # TODO: Implement MeSHHeadingEntity class in schema
        # from pyeuropepmc.models.mesh import MeSHHeadingEntity

        mesh_headings = []
        mesh_heading_list = result.get("meshHeadingList", {}).get("meshHeading", [])

        if isinstance(mesh_heading_list, list):
            for mesh_data in mesh_heading_list:
                try:
                    # heading = MeSHHeadingEntity.from_dict(mesh_data)
                    # mesh_headings.append(heading)
                    # For now, just return the raw data
                    mesh_headings.append(mesh_data)
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
    ) -> tuple["PaperEntity", dict[str, Any]]:
        """Create a comprehensive PaperEntity from search result data with validation and quality scoring."""
        from pyeuropepmc.models import GrantEntity, JournalEntity, PaperEntity

        # Validate and clean the result first
        result = EuropePMCParser.validate_search_result(result)

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

        # Calculate overall paper quality score
        quality_score = EuropePMCParser._calculate_paper_quality_score(result, author_entities)

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
            grants=[
                GrantEntity(funding_source=f.get("agency"), award_id=f.get("grantId"))
                for f in funders
            ]
            if funders
            else None,
            license=license_info,
        )

        # Return both the paper entity and related entities
        related_entities = {"authors": author_entities, "institutions": institution_entities}
        return paper_entity, related_entities

    @staticmethod
    def _calculate_paper_quality_score(
        result: dict[str, Any], author_entities: list["AuthorEntity"]
    ) -> float:
        """Calculate an overall quality score for the paper data."""
        score = 0.0
        total_checks = 0

        # Identifier quality (high importance)
        identifiers = [result.get("doi"), result.get("pmcid"), result.get("pmid")]
        valid_identifiers = sum(1 for id_val in identifiers if id_val)
        if valid_identifiers >= 1:
            score += 0.4  # At least one identifier
        if valid_identifiers >= 2:
            score += 0.3  # Multiple identifiers
        total_checks += 1

        # Title presence
        if result.get("title"):
            score += 0.3
        total_checks += 1

        # Abstract presence
        if result.get("abstractText"):
            score += 0.2
        total_checks += 1

        # Author quality (placeholder - would need author quality scores)
        # For now, just check if authors exist
        if author_entities:
            score += 0.2  # Has authors
        total_checks += 1

        # Journal information
        journal_info = result.get("journalInfo", {})
        if journal_info.get("journal", {}).get("title"):
            score += 0.2
        total_checks += 1

        # Publication year
        if result.get("pubYear"):
            score += 0.1
        total_checks += 1

        # Open access information
        if result.get("isOpenAccess") is not None:
            score += 0.1
        total_checks += 1

        return score / total_checks if total_checks > 0 else 0.0

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
