import logging
from unittest.mock import patch

import pytest

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ParsingError, SearchError
from pyeuropepmc.parser import EuropePMCParser
from pyeuropepmc.search import SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
@pytest.mark.parametrize(
    "format_type, expected_output",
    [
        ("json", list),  # JSON format should return list
        ("xml", list),  # XML format should return list (parsed results)
        ("dc", list),  # Dublin Core format should return list (parsed results)
    ],
)
def test_search_and_parse_parametrized(
    search_cancer_json, search_cancer_xml, search_cancer_dc_xml, format_type, expected_output
) -> None:
    """Test search_and_parse with different formats."""
    client = SearchClient()

    # Map format to appropriate fixture data
    format_data = {
        "json": search_cancer_json,
        "xml": search_cancer_xml,
        "dc": search_cancer_dc_xml,
    }

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = format_data[format_type]

        # Use appropriate parser method based on format
        if format_type == "json":
            with patch.object(EuropePMCParser, "parse_json") as mock_parse:
                mock_parse.return_value = [{"title": "Parsed result"}]
                result = client.search_and_parse("cancer", format=format_type)
                mock_parse.assert_called_once()
        elif format_type == "xml":
            with patch.object(EuropePMCParser, "parse_xml") as mock_parse:
                mock_parse.return_value = [{"title": "Parsed result"}]
                result = client.search_and_parse("cancer", format=format_type)
                mock_parse.assert_called_once()
        else:  # dc
            with patch.object(EuropePMCParser, "parse_dc") as mock_parse:
                mock_parse.return_value = [{"title": "Parsed result"}]
                result = client.search_and_parse("cancer", format=format_type)
                mock_parse.assert_called_once()

        # Verify the result type matches expectation
        assert isinstance(result, expected_output)

        # Verify search was called with correct format
        mock_search.assert_called_once()
        search_args = mock_search.call_args[1]
        assert search_args["format"] == format_type

    client.close()


@pytest.mark.unit
@pytest.mark.parametrize(
    "format_type, expected_exception",
    [
        ("invalid", SearchError),
        ("pdf", SearchError),
        ("html", SearchError),
    ],
)
def test_search_and_parse_format_validation(format_type, expected_exception) -> None:
    """Test search_and_parse with invalid formats."""
    client = SearchClient()

    with pytest.raises(expected_exception):
        client.search_and_parse("test", format=format_type)

    client.close()


@pytest.mark.unit
def test_search_and_parse_type_mismatch() -> None:
    """Test search_and_parse handles type mismatch between format and data."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        # Return JSON data but claim it's XML format
        mock_search.return_value = {"test": "data"}

        # This should raise ParsingError due to type mismatch (dict instead of str for XML)
        with pytest.raises(ParsingError) as exc_info:
            client.search_and_parse("test", format="xml")

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.PARSE004

        # Check that the error message contains the expected content
        error_str = str(exc_info.value)
        assert "[PARSE004]" in error_str
        assert "Unsupported data format" in error_str

    client.close()


@pytest.mark.unit
def test_search_and_parse_with_kwargs() -> None:
    """Test search_and_parse passes kwargs to search method."""
    client = SearchClient()

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = {"test": "data"}

        with patch.object(EuropePMCParser, "parse_json") as mock_parse:
            mock_parse.return_value = ["parsed"]

            client.search_and_parse(
                "test",
                format="json",
                resultType="core",
                pageSize=50,
                email="test@example.com",
            )

            # Verify search was called with all kwargs
            mock_search.assert_called_once()
            search_kwargs = mock_search.call_args[1]
            assert search_kwargs["format"] == "json"
            assert search_kwargs["resultType"] == "core"
            assert search_kwargs["pageSize"] == 50
            assert search_kwargs["email"] == "test@example.com"

    client.close()


@pytest.mark.unit
def test_search_and_parse_xml_format() -> None:
    """Test search_and_parse with XML format specifically."""
    client = SearchClient()

    xml_data = "<resultList><result><title>Test</title></result></resultList>"

    with patch.object(client, "search") as mock_search:
        mock_search.return_value = xml_data

        with patch.object(EuropePMCParser, "parse_xml") as mock_parse:
            mock_parse.return_value = [{"title": "Test"}]

            result = client.search_and_parse("test", format="xml")

            # Verify result is list
            assert isinstance(result, list)
            assert result == [{"title": "Test"}]

            # Verify parser was called with XML data
            mock_parse.assert_called_once_with(xml_data)

    client.close()


@pytest.mark.unit
def test_search_and_parse_unknown_format_error() -> None:
    """Test search_and_parse raises SearchError for unknown format."""
    from pyeuropepmc.exceptions import SearchError

    client = SearchClient()

    # Test with completely unknown format
    with pytest.raises(SearchError) as exc_info:
        client.search_and_parse("test", format="unknown")

    # Check for new error code message
    error_msg = str(exc_info.value)
    assert "SEARCH004" in error_msg or "Invalid format parameter" in error_msg

    client.close()
