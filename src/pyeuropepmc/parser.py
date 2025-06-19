from typing import Any, Dict, List

import defusedxml.ElementTree as ET


class EuropePMCParser:
    @staticmethod
    def parse_json(data: Any) -> List[Dict[str, Any]]:
        """
        Parses Europe PMC JSON response and returns a list of result dicts.
        """
        if isinstance(data, dict):
            results = data.get("resultList", {}).get("result", [])
            if isinstance(results, list) and all(isinstance(item, dict) for item in results):
                return results
        return []

    @staticmethod
    def parse_xml(xml_str: str) -> List[Dict[str, Any]]:
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
        except ET.ParseError:
            pass  # Optionally log error
        return results

    @staticmethod
    def parse_dc(dc_str: str) -> List[Dict[str, Any]]:
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
        except ET.ParseError:
            pass  # Optionally log error
        return results
