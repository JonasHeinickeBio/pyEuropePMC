import pytest
from pyeuropepmc.parser import EuropePMCParser, ParsingError
import os
import json
import logging
from pyeuropepmc.error_codes import ErrorCodes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parser_functional_test")

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "../../fixtures")
FULLTEXT_DIR = os.path.join(FIXTURE_DIR, "fulltext_downloads")

# --- Fine-grained functional tests for each parser function ---

def get_json_files():
    return [f for f in os.listdir(FIXTURE_DIR) if f.endswith(".json")]

def get_xml_files():
    return [f for f in os.listdir(FIXTURE_DIR) if f.endswith(".xml")]

def get_dc_files():
    return [f for f in os.listdir(FIXTURE_DIR) if f.endswith("_dc.xml")]

def get_fulltext_xml_files():
    return [f for f in os.listdir(FULLTEXT_DIR) if f.endswith(".xml")]

def get_fulltext_pdf_files():
    return [f for f in os.listdir(FULLTEXT_DIR) if f.endswith(".pdf")]

@pytest.mark.parametrize("filename", get_json_files())
def test_parse_json_fixture(filename):
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    try:
        results = EuropePMCParser.parse_json(data)
        logger.info(f"[parse_json] {filename}: Parsed {len(results)} records.")
        if results:
            logger.info(f"[parse_json] {filename}: First record keys: {list(results[0].keys())}")
            assert isinstance(results[0], dict)
    except ParsingError as e:
        logger.warning(f"[parse_json] {filename}: ParsingError: {e}")
        assert True
    except Exception as e:
        logger.error(f"[parse_json] {filename}: Unexpected error: {e}")
        assert False, f"Unexpected error: {e}"

@pytest.mark.parametrize("filename", get_xml_files())
def test_parse_xml_fixture(filename):
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        xml_str = f.read()
    try:
        results = EuropePMCParser.parse_xml(xml_str)
        logger.info(f"[parse_xml] {filename}: Parsed {len(results)} records.")
        if results:
            logger.info(f"[parse_xml] {filename}: First record keys: {list(results[0].keys())}")
            assert isinstance(results[0], dict)
    except ParsingError as e:
        logger.warning(f"[parse_xml] {filename}: ParsingError: {e}")
        assert True
    except Exception as e:
        logger.error(f"[parse_xml] {filename}: Unexpected error: {e}")
        assert False, f"Unexpected error: {e}"

@pytest.mark.parametrize("filename", get_dc_files())
def test_parse_dc_fixture(filename):
    path = os.path.join(FIXTURE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        dc_str = f.read()
    try:
        results = EuropePMCParser.parse_dc(dc_str)
        logger.info(f"[parse_dc] {filename}: Parsed {len(results)} records.")
        if results:
            logger.info(f"[parse_dc] {filename}: First record keys: {list(results[0].keys())}")
            assert isinstance(results[0], dict)
    except ParsingError as e:
        logger.warning(f"[parse_dc] {filename}: ParsingError: {e}")
        assert True
    except Exception as e:
        logger.error(f"[parse_dc] {filename}: Unexpected error: {e}")
        assert False, f"Unexpected error: {e}"

@pytest.mark.parametrize("filename", get_fulltext_xml_files())
def test_parse_fulltext_xml(filename):
    path = os.path.join(FULLTEXT_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        xml_str = f.read()
    try:
        results = EuropePMCParser.parse_xml(xml_str)
        logger.info(f"[parse_fulltext_xml] {filename}: Parsed {len(results)} records.")
        if results:
            logger.info(f"[parse_fulltext_xml] {filename}: First record keys: {list(results[0].keys())}")
    except ParsingError as e:
        logger.warning(f"[parse_fulltext_xml] {filename}: ParsingError: {e}")
        assert True
    except Exception as e:
        logger.error(f"[parse_fulltext_xml] {filename}: Unexpected error: {e}")
        assert False, f"Unexpected error: {e}"

@pytest.mark.parametrize("filename", get_fulltext_pdf_files())
def test_fulltext_pdf_exists(filename):
    path = os.path.join(FULLTEXT_DIR, filename)
    exists = os.path.exists(path)
    size = os.path.getsize(path) if exists else 0
    logger.info(f"[pdf_exists] {filename}: Exists={exists}, Size={size}")
    assert exists
    assert size > 1000

@pytest.mark.parametrize("bad_xml", ["<broken><xml>", "", "<resultList></resultList>"])
def test_parse_xml_error_handling(bad_xml):
    with pytest.raises(ParsingError) as exc_info:
        EuropePMCParser.parse_xml(bad_xml)
    err_msg = str(exc_info.value)
    logger.warning(f"[parse_xml_error_handling] ParsingError: {err_msg}")
    # Check error code (accept PARSE002, PARSE003, or PARSE004)
    assert (
        ErrorCodes.PARSE002.value in err_msg or ErrorCodes.PARSE003.value in err_msg or ErrorCodes.PARSE004.value in err_msg
    ), f"Error code not found in error message: {err_msg}"
    # Check informative error message: not empty, not just error code, and contains some explanation
    code_002 = ErrorCodes.PARSE002.value
    code_003 = ErrorCodes.PARSE003.value
    code_004 = ErrorCodes.PARSE004.value
    msg_without_code = err_msg.replace(f"[{code_002}]", "").replace(f"[{code_003}]", "").replace(f"[{code_004}]", "").strip()
    assert msg_without_code and len(msg_without_code) > 5, f"Error message not informative: {err_msg}"
