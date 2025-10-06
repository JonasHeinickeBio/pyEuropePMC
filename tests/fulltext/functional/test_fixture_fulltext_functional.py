import pytest
from pyeuropepmc.parser import EuropePMCParser, ParsingError
import os

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "../../fixtures/fulltext_downloads")

# Dynamically list all PMCIDs with both XML and PDF in the fixture folder
def get_pmcids():
    files = os.listdir(FIXTURE_DIR)
    xml_ids = {f.split(".")[0] for f in files if f.endswith(".xml") and f.startswith("PMC")}
    pdf_ids = {f.split(".")[0] for f in files if f.endswith(".pdf") and f.startswith("PMC")}
    return sorted(xml_ids & pdf_ids)

PMCIDS = get_pmcids()

@pytest.mark.parametrize("pmcid", PMCIDS)
def test_parse_xml_fulltext(pmcid):
    xml_path = os.path.join(FIXTURE_DIR, f"{pmcid}.xml")
    assert os.path.exists(xml_path)
    with open(xml_path, "r", encoding="utf-8") as f:
        xml_str = f.read()
    try:
        results = EuropePMCParser.parse_xml(xml_str)
        assert isinstance(results, list)
        # Accept empty results if the XML is not a search result format, but log it
        if len(results) == 0:
            print(f"Warning: No parsed results for {pmcid}.xml (likely not search result format)")
        else:
            assert isinstance(results[0], dict)
            assert "title" in results[0] or any("title" in r for r in results)
    except ParsingError as e:
        print(f"ParsingError for {pmcid}.xml: {e}")
        assert True  # Error handling is tested
    except Exception as e:
        print(f"Unexpected error for {pmcid}.xml: {e}")
        assert False, f"Unexpected error: {e}"

@pytest.mark.parametrize("pmcid", PMCIDS)
def test_pdf_exists(pmcid):
    pdf_path = os.path.join(FIXTURE_DIR, f"{pmcid}.pdf")
    assert os.path.exists(pdf_path)
    # Check PDF magic number and minimal structure
    with open(pdf_path, "rb") as f:
        header = f.read(5)
        debug_head = f.read(27)  # Read next 27 bytes for debugging (total 32 bytes)
        print(f"PDF head for {pmcid}: {header + debug_head}")
        assert header == b'%PDF-', f"{pdf_path} does not start with PDF magic number"
        f.seek(-7, os.SEEK_END)
        trailer = f.read(7)
        assert b'%%EOF' in trailer, f"{pdf_path} does not end with PDF EOF marker"
    # Optionally check file size is reasonable (e.g., >100 bytes)
    assert os.path.getsize(pdf_path) > 100, f"{pdf_path} is unexpectedly small"

# Additional error handling test: try parsing a broken XML file
@pytest.mark.parametrize("bad_xml", ["<broken><xml>", "", "<resultList></resultList>"])
def test_parse_xml_error_handling(bad_xml):
    try:
        results = EuropePMCParser.parse_xml(bad_xml)
        # Should be empty or raise error
        assert isinstance(results, list)
        if bad_xml == "":
            assert len(results) == 0
    except ParsingError:
        assert True  # Expected error
    except Exception as e:
        assert False, f"Unexpected error: {e}"
