"""
Comprehensive unit tests for ArticleClient with high coverage.

Tests all methods and edge cases using pytest and unittest.mock.
"""

import json
from unittest.mock import Mock, patch, call
import pytest
import requests
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.core.exceptions import ValidationError, APIClientError
from pyeuropepmc.core.error_codes import ErrorCodes


class TestArticleClientComprehensive:
    """Comprehensive test suite for ArticleClient with high coverage."""

    @pytest.fixture
    def article_client(self):
        """Create an ArticleClient instance for testing."""
        return ArticleClient(rate_limit_delay=0.5)

    @pytest.fixture
    def mock_response_obj(self):
        """Create a properly configured mock response object."""
        def _create_mock_response(json_data, status_code=200, headers=None):
            if headers is None:
                headers = {"Content-Type": "application/json"}
            mock_response = Mock()
            mock_response.json.return_value = json_data
            mock_response.status_code = status_code
            mock_response.headers = headers
            mock_response.text = json.dumps(json_data) if json_data else ""
            mock_response.content = b"test binary data"
            return mock_response
        return _create_mock_response

    @pytest.fixture
    def mock_json_response(self):
        """Mock JSON API response data."""
        return {
            "version": "6.9",
            "hitCount": 2,
            "request": {"id": "12345", "source": "MED"},
            "result": {
                "id": "12345",
                "pmid": "12345",
                "source": "MED",
                "title": "Test Article Title",
                "authorList": {"author": [{"fullName": "Test Author"}]},
                "journalInfo": {"journal": {"title": "Test Journal"}},
                "citedByCount": 10,
                "hasTextMinedTerms": "Y",
                "hasReferences": "Y",
                "hasSuppl": "N",
                "pmcid": "PMC123456"
            },
            "citationList": {
                "citation": [
                    {"id": "cite1", "title": "Citation 1"},
                    {"id": "cite2", "title": "Citation 2"}
                ]
            },
            "referenceList": {
                "reference": [
                    {"id": "ref1", "title": "Reference 1"},
                    {"id": "ref2", "title": "Reference 2"}
                ]
            }
        }

    @pytest.fixture
    def mock_jsonp_response(self):
        """Mock JSONP response data."""
        return 'processData({"version":"6.9","hitCount":0,"citationList":{}})'

    @pytest.fixture
    def mock_binary_response(self):
        """Mock binary response for supplementary files."""
        return b"mock binary data for supplementary files"

    # Test initialization
    def test_initialization_default(self):
        """Test ArticleClient initialization with defaults."""
        client = ArticleClient()
        assert isinstance(client, ArticleClient)
        assert client.rate_limit_delay == 1.0
        assert client.logger.name == "pyeuropepmc.clients.article"

    def test_initialization_custom_delay(self):
        """Test ArticleClient initialization with custom delay."""
        client = ArticleClient(rate_limit_delay=2.5)
        assert client.rate_limit_delay == 2.5

    # Test get_article_details
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_article_details_success(self, mock_get, article_client, mock_json_response, mock_response_obj):
        """Test successful article details retrieval."""
        mock_response = mock_response_obj(mock_json_response)
        mock_get.return_value = mock_response

        result = article_client.get_article_details("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "article/MED/12345",
            params={"resultType": "core", "format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_article_details_with_params(self, mock_get, article_client, mock_json_response, mock_response_obj):
        """Test article details with additional parameters."""
        mock_response = mock_response_obj(mock_json_response)
        mock_get.return_value = mock_response

        result = article_client.get_article_details(
            "PMC", "PMC123", result_type="lite", format="xml", custom_param="value"
        )

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "article/PMC/PMC123",
            params={"resultType": "lite", "format": "xml", "custom_param": "value"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_article_details_api_error(self, mock_get, article_client):
        """Test article details API error handling."""
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(APIClientError) as exc_info:
            article_client.get_article_details("MED", "12345")

        assert exc_info.value.error_code == ErrorCodes.NET001
        assert "source" in exc_info.value.context
        assert "article_id" in exc_info.value.context

    # Test get_citations
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_citations_success(self, mock_get, article_client, mock_json_response, mock_response_obj):
        """Test successful citations retrieval."""
        mock_response = mock_response_obj(mock_json_response)
        mock_get.return_value = mock_response

        result = article_client.get_citations("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "MED/12345/citations",
            params={"page": 1, "pageSize": 25, "format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_citations_with_pagination(self, mock_get, article_client, mock_json_response, mock_response_obj):
        """Test citations with pagination parameters."""
        mock_response = mock_response_obj(mock_json_response)
        mock_get.return_value = mock_response

        result = article_client.get_citations("MED", "12345", page=2, page_size=50)

        mock_get.assert_called_once_with(
            "MED/12345/citations",
            params={"page": 2, "pageSize": 50, "format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_citations_with_callback(self, mock_get, article_client, mock_jsonp_response):
        """Test citations with JSONP callback."""
        mock_response = Mock()
        mock_response.text = mock_jsonp_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/x-javascript"}
        mock_get.return_value = mock_response

        result = article_client.get_citations("MED", "12345", callback="processData")

        assert result == {"jsonp_response": mock_jsonp_response}
        mock_get.assert_called_once_with(
            "MED/12345/citations",
            params={"page": 1, "pageSize": 25, "format": "json", "callback": "processData"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_citations_api_error(self, mock_get, article_client):
        """Test citations API error handling."""
        mock_get.side_effect = Exception("API Error")

        with pytest.raises(APIClientError) as exc_info:
            article_client.get_citations("MED", "12345")

        assert exc_info.value.error_code == ErrorCodes.NET001

    # Test get_references
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_references_success(self, mock_get, article_client, mock_json_response):
        """Test successful references retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = mock_json_response
        mock_get.return_value = mock_response

        result = article_client.get_references("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "MED/12345/references",
            params={"page": 1, "pageSize": 25, "format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_references_with_callback(self, mock_get, article_client, mock_jsonp_response):
        """Test references with JSONP callback."""
        mock_response = Mock()
        mock_response.text = mock_jsonp_response
        mock_get.return_value = mock_response

        result = article_client.get_references("MED", "12345", callback="myCallback", format="json")

        assert result == {"jsonp_response": mock_jsonp_response}

    # Test get_database_links
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_database_links_success(self, mock_get, article_client, mock_json_response):
        """Test successful database links retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = mock_json_response
        mock_get.return_value = mock_response

        result = article_client.get_database_links("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "MED/12345/databaseLinks",
            params={"page": 1, "pageSize": 25, "format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_database_links_with_callback(self, mock_get, article_client, mock_jsonp_response):
        """Test database links with JSONP callback."""
        mock_response = Mock()
        mock_response.text = mock_jsonp_response
        mock_get.return_value = mock_response

        result = article_client.get_database_links("MED", "12345", callback="dbCallback")

        assert result == {"jsonp_response": mock_jsonp_response}

    # Test get_supplementary_files
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_supplementary_files_success(self, mock_get, article_client, mock_binary_response):
        """Test successful supplementary files retrieval."""
        mock_response = Mock()
        mock_response.content = mock_binary_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/zip"}
        mock_get.return_value = mock_response

        result = article_client.get_supplementary_files("PMC123456")

        assert result == mock_binary_response
        mock_get.assert_called_once_with(
            "PMC123456/supplementaryFiles",
            params={"includeInlineImage": "true"}, stream=True
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_supplementary_files_with_image_control(self, mock_get, article_client, mock_binary_response):
        """Test supplementary files with image inclusion control."""
        mock_response = Mock()
        mock_response.content = mock_binary_response
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/zip"}
        mock_get.return_value = mock_response

        result = article_client.get_supplementary_files(
            "PMC123456",
            include_inline_image=True
        )

        assert result == mock_binary_response
        mock_get.assert_called_once_with(
            "PMC123456/supplementaryFiles",
            params={"includeInlineImage": "true"},
            stream=True
        )

    # Test get_lab_links
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_lab_links_success(self, mock_get, article_client, mock_json_response):
        """Test successful lab links retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = mock_json_response
        mock_get.return_value = mock_response

        result = article_client.get_lab_links("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "MED/12345/labsLinks",
            params={"format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_lab_links_with_provider(self, mock_get, article_client, mock_json_response):
        """Test lab links with provider ID."""
        mock_response = Mock()
        mock_response.json.return_value = mock_json_response
        mock_get.return_value = mock_response

        result = article_client.get_lab_links("MED", "12345", provider_id="provider123")

        mock_get.assert_called_once_with(
            "MED/12345/labsLinks",
            params={"format": "json", "providerId": "provider123"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_lab_links_with_callback(self, mock_get, article_client, mock_jsonp_response):
        """Test lab links with JSONP callback."""
        mock_response = Mock()
        mock_response.text = mock_jsonp_response
        mock_get.return_value = mock_response

        result = article_client.get_lab_links("MED", "12345", callback="labCallback")

        assert result == {"jsonp_response": mock_jsonp_response}

    # Test get_data_links
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_data_links_success(self, mock_get, article_client, mock_json_response):
        """Test successful data links retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = mock_json_response
        mock_get.return_value = mock_response

        result = article_client.get_data_links("MED", "12345")

        assert result == mock_json_response
        mock_get.assert_called_once_with(
            "MED/12345/datalinks",
            params={"format": "json"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_data_links_with_callback(self, mock_get, article_client, mock_jsonp_response):
        """Test data links with JSONP callback."""
        mock_response = Mock()
        mock_response.text = mock_jsonp_response
        mock_get.return_value = mock_response

        result = article_client.get_data_links("MED", "12345", callback="dataCallback")

        assert result == {"jsonp_response": mock_jsonp_response}

    # Validation tests
    def test_validate_source_and_id_valid(self, article_client):
        """Test source and ID validation with valid inputs."""
        # Should not raise any exception
        article_client._validate_source_and_id("MED", "12345")
        article_client._validate_source_and_id("PMC", "PMC123456")
        article_client._validate_source_and_id("PPR", "pprid123")

    def test_validate_source_and_id_invalid_source(self, article_client):
        """Test source validation with invalid source."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_source_and_id("INVALID", "12345")

        assert exc_info.value.error_code == ErrorCodes.VALID001
        assert "source" in exc_info.value.context["field_name"]

        with pytest.raises(ValidationError):
            article_client._validate_source_and_id("", "12345")

        with pytest.raises(ValidationError):
            article_client._validate_source_and_id("TOOLONG", "12345")

    def test_validate_source_and_id_invalid_article_id(self, article_client):
        """Test article ID validation with invalid ID."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_source_and_id("MED", "")

        assert exc_info.value.error_code == ErrorCodes.VALID001
        assert "article_id" in exc_info.value.context["field_name"]

        with pytest.raises(ValidationError):
            article_client._validate_source_and_id("MED", None)

    def test_validate_pagination_valid(self, article_client):
        """Test pagination validation with valid inputs."""
        # Should not raise any exception
        article_client._validate_pagination(1, 25)
        article_client._validate_pagination(10, 1000)
        article_client._validate_pagination(1, 1)

    def test_validate_pagination_invalid_page(self, article_client):
        """Test pagination validation with invalid page."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_pagination(0, 25)

        assert "page" in exc_info.value.context["field_name"]

        with pytest.raises(ValidationError):
            article_client._validate_pagination(-1, 25)

    def test_validate_pagination_invalid_page_size(self, article_client):
        """Test pagination validation with invalid page size."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_pagination(1, 0)

        assert "page_size" in exc_info.value.context["field_name"]

        with pytest.raises(ValidationError):
            article_client._validate_pagination(1, 1001)

    def test_validate_citations_format_valid(self, article_client):
        """Test citations format validation with valid formats."""
        # Should not raise any exception
        article_client._validate_citations_format("json")
        article_client._validate_citations_format("xml")

    def test_validate_citations_format_invalid(self, article_client):
        """Test citations format validation with invalid format."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_citations_format("invalid")

        assert "format" in exc_info.value.context["field_name"]

    def test_validate_callback_valid(self, article_client):
        """Test callback validation with valid inputs."""
        # Should not raise any exception
        article_client._validate_callback(None, "json")
        article_client._validate_callback("myCallback", "json")
        article_client._validate_callback("processData", "json")

    def test_validate_callback_invalid_format(self, article_client):
        """Test callback validation with non-JSON format."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_callback("myCallback", "xml")

        assert exc_info.value.field_name == "callback"
        assert "requires format to be 'json'" in exc_info.value.message

    def test_validate_callback_invalid_type(self, article_client):
        """Test callback validation with invalid type."""
        with pytest.raises(ValidationError) as exc_info:
            article_client._validate_callback(123, "json")

        assert exc_info.value.field_name == "callback"
        assert "must be a string" in exc_info.value.message

    # Edge cases and error handling
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_all_methods_error_handling(self, mock_get, article_client):
        """Test error handling across all methods."""
        mock_get.side_effect = Exception("Network error")

        methods_to_test = [
            ("get_citations", ("MED", "12345")),
            ("get_references", ("MED", "12345")),
            ("get_database_links", ("MED", "12345")),
            ("get_lab_links", ("MED", "12345")),
            ("get_data_links", ("MED", "12345")),
        ]

        for method_name, args in methods_to_test:
            with pytest.raises(APIClientError):
                getattr(article_client, method_name)(*args)

    def test_comprehensive_validation_combinations(self, article_client):
        """Test various validation combinations."""
        # Test multiple validation errors
        invalid_combinations = [
            ("", "", 0, 0, "invalid", "callback"),  # All invalid
            ("TOOLONG", "12345", -1, 2000, "badformat", None),  # Multiple issues
        ]

        for source, article_id, page, page_size, format_val, callback in invalid_combinations:
            if source and len(source) != 3:
                with pytest.raises(ValidationError):
                    article_client._validate_source_and_id(source, article_id)

            if page <= 0:
                with pytest.raises(ValidationError):
                    article_client._validate_pagination(page, page_size)

            if format_val not in ["json", "xml"]:
                with pytest.raises(ValidationError):
                    article_client._validate_citations_format(format_val)

    # Integration-style tests with realistic data
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_realistic_citation_workflow(self, mock_get, article_client):
        """Test a realistic citation retrieval workflow."""
        # Mock multiple pages of citations
        page1_response = Mock()
        page1_response.json.return_value = {
            "hitCount": 150,
            "citationList": {"citation": [{"id": f"cite{i}"} for i in range(25)]}
        }
        page1_response.status_code = 200
        page1_response.headers = {"Content-Type": "application/json"}

        page2_response = Mock()
        page2_response.json.return_value = {
            "hitCount": 150,
            "citationList": {"citation": [{"id": f"cite{i}"} for i in range(25, 50)]}
        }
        page2_response.status_code = 200
        page2_response.headers = {"Content-Type": "application/json"}

        mock_get.side_effect = [page1_response, page2_response]

        # Get first page
        result1 = article_client.get_citations("MED", "12345", page=1, page_size=25)
        assert len(result1["citationList"]["citation"]) == 25

        # Get second page
        result2 = article_client.get_citations("MED", "12345", page=2, page_size=25)
        assert len(result2["citationList"]["citation"]) == 25

        # Verify correct API calls
        expected_calls = [
            call("MED/12345/citations", params={"page": 1, "pageSize": 25, "format": "json"}),
            call("MED/12345/citations", params={"page": 2, "pageSize": 25, "format": "json"})
        ]
        mock_get.assert_has_calls(expected_calls)
