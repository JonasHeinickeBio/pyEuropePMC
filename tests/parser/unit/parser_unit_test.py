import logging

import defusedxml.ElementTree as ET
import pytest

from pyeuropepmc.parser import EuropePMCParser

logger = logging.getLogger("pyeuropepmc.parser")


@pytest.mark.unit
def test_parse_json_with_search_cancer_json(search_cancer_json):
    results = EuropePMCParser.parse_json(search_cancer_json)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    if results:
        assert "id" in results[0] or "pmid" in results[0]


@pytest.mark.unit
def test_parse_json_with_search_cancer_core_json(search_cancer_core_json):
    results = EuropePMCParser.parse_json(search_cancer_core_json)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    if results:
        assert "id" in results[0] or "pmid" in results[0]


@pytest.mark.unit
def test_parse_json_with_search_cancer_idlist_json(search_cancer_idlist_json):
    results = EuropePMCParser.parse_json(search_cancer_idlist_json)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    if results:
        assert "id" in results[0] or "pmid" in results[0]


@pytest.mark.unit
def test_parse_json_with_search_no_results_json(search_no_results_json):
    results = EuropePMCParser.parse_json(search_no_results_json)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert results == []


@pytest.mark.unit
def test_parse_xml_with_search_cancer_xml(search_cancer_xml):
    results = EuropePMCParser.parse_xml(search_cancer_xml)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    if results:
        assert "id" in results[0] or "pmid" in results[0]


@pytest.mark.unit
def test_parse_dc_with_search_cancer_dc_xml(search_cancer_dc_xml):
    results = EuropePMCParser.parse_dc(search_cancer_dc_xml)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    if results:
        # DC format should have at least one of these keys
        assert any(k in results[0] for k in ("title", "creator", "identifier"))


@pytest.mark.unit
def test_parse_json_with_search_1000results_cancer_json(search_1000results_cancer_json):
    results = EuropePMCParser.parse_json(search_1000results_cancer_json)
    logger.debug(f"Results length: {len(results)}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)
    assert len(results) >= 1000


@pytest.mark.unit
def test_parse_json_with_fetch_10pages_cancer_json(fetch_10pages_cancer_json):
    first_page = fetch_10pages_cancer_json[0]
    results = EuropePMCParser.parse_json(first_page)
    logger.debug(f"Results: {results}")
    assert isinstance(results, list)
    assert all(isinstance(r, dict) for r in results)


@pytest.mark.unit
def test_parse_dc_with_invalid_xml_raises_error():
    invalid_xml = "<root><invalid></root>"
    with pytest.raises(ET.ParseError):
        EuropePMCParser.parse_dc(invalid_xml)


@pytest.mark.unit
def test_parse_xml_with_invalid_xml_raises_error():
    invalid_xml = "<root><invalid></root>"
    with pytest.raises(ET.ParseError):
        EuropePMCParser.parse_xml(invalid_xml)


@pytest.mark.unit
def test_parse_json_with_invalid_data():
    invalid_data = "not a json"
    with pytest.raises(Exception):
        EuropePMCParser.parse_json(invalid_data)
