import logging
from typing import Any

import defusedxml.ElementTree as ET

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ParsingError


class EuropePMCParser:
    logger = logging.getLogger("EuropePMCParser")

    @staticmethod
    def parse_json(data: Any) -> list[dict[str, Any]]:
        """
        Parses Europe PMC JSON response and returns a list of result dicts.
        """
        try:
            if isinstance(data, dict):
                results = data.get("resultList", {}).get("result", [])
                if isinstance(results, list) and all(isinstance(item, dict) for item in results):
                    return results
            elif isinstance(data, list):
                # If data is already a list of dicts
                if all(isinstance(item, dict) for item in data):
                    return data
            else:
                error_msg = (
                    f"Invalid data format for JSON parsing: expected dict or list, "
                    f"got {type(data).__name__}. Check if the API response is valid."
                )
                EuropePMCParser.logger.error(error_msg)
                context = {
                    "expected_type": "dict or list",
                    "actual_type": type(data).__name__,
                }
                raise ParsingError(ErrorCodes.PARSE001, context)
        except Exception as e:
            error_msg = (
                f"Unexpected error while parsing JSON response: {e}. "
                f"The API response may be malformed or the data structure "
                f"may have changed."
            )
            EuropePMCParser.logger.error(error_msg)
            raise
        return []

    @staticmethod
    def parse_xml(xml_str: str) -> list[dict[str, Any]]:
        """
        Parses Europe PMC XML response and returns a list of result dicts.
        """
        results = []
        try:
            root = ET.fromstring(xml_str)
            # Find all <result> elements under <resultList>
            for result_elem in root.findall(".//resultList/result"):
                result = {child.tag: child.text for child in result_elem}
                results.append(result)
        except ET.ParseError as e:
            error_msg = (
                f"XML parsing error: {e}. The XML response from Europe PMC API "
                f"appears to be malformed or incomplete. "
                f"Check if the response is valid XML."
            )
            EuropePMCParser.logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = (
                f"Unexpected error while parsing XML response: {e}. "
                f"The XML structure may have changed or the response may be corrupted."
            )
            EuropePMCParser.logger.error(error_msg)
            raise
        return results

    @staticmethod
    def parse_dc(dc_str: str) -> list[dict[str, Any]]:
        """
        Parses Europe PMC DC XML response and returns a list of result dicts.
        """
        results = []
        try:
            root = ET.fromstring(dc_str)
            # DC uses RDF/Description structure
            ns = {
                "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                "dc": "http://purl.org/dc/elements/1.1/",
                "dcterms": "http://purl.org/dc/terms/",
            }
            for desc in root.findall(".//rdf:Description", ns):
                result: dict[Any, Any] = {}
                for child in desc:
                    # Remove namespace from tag
                    tag = child.tag.split("}", 1)[-1]
                    # Handle multiple creators, contributors, etc.
                    if tag in result:
                        if isinstance(result[tag], list):
                            result[tag].append(child.text)
                        else:
                            result[tag] = [result[tag]]
                            if child.text is not None:
                                result[tag].append(child.text)
                    else:
                        result[tag] = child.text
                results.append(result)
        except ET.ParseError as e:
            error_msg = (
                f"Dublin Core XML parsing error: {e}. The DC XML response from "
                f"Europe PMC API appears to be malformed. "
                f"Check if the response is valid DC XML format."
            )
            EuropePMCParser.logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = (
                f"Unexpected error while parsing Dublin Core XML response: {e}. "
                f"The DC XML structure may have changed or the namespace may be invalid."
            )
            EuropePMCParser.logger.error(error_msg)
            raise
        return results
