"""
Unit tests for ArticleClient.

Tests the ArticleClient class methods including:
- Article details retrieval
- Citations and references
- Database links and supplementary files
- Lab links and data links
- Format and parameter validation
"""

from unittest.mock import Mock, patch
import pytest
from pyeuropepmc.clients.article import ArticleClient
from pyeuropepmc.core.exceptions import ValidationError


class TestArticleClient:
    """Test suite for ArticleClient class."""

    @pytest.fixture
    def article_client(self):
        """Create an ArticleClient instance for testing."""
        return ArticleClient()

    @pytest.fixture
    def mock_response(self):
        """Mock API response data."""
        return {
            "version": "6.5",
            "hitCount": 1,
            "resultList": {
                "result": [{
                    "id": "12345",
                    "pmid": "12345",
                    "source": "MED",
                    "title": "Test Article Title"
                }]
            }
        }

    # Basic initialization test
    def test_initialization(self, article_client):
        """Test ArticleClient initialization."""
        assert isinstance(article_client, ArticleClient)
        assert article_client.rate_limit_delay == 1.0

    # Test get_article_details method
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_article_details_success(self, mock_get, article_client, mock_response):
        """Test successful article details retrieval."""
        mock_response_obj = Mock()
        mock_response_obj.json.return_value = mock_response
        mock_get.return_value = mock_response_obj

        result = article_client.get_article_details("med", "12345")

        assert result == mock_response
        mock_get.assert_called_once_with(
            "article/med/12345",
            params={"resultType": "core", "format": "json"}
        )

    def test_get_article_details_invalid_source(self, article_client):
        """Test article details with invalid source."""
        with pytest.raises(ValidationError):
            article_client.get_article_details("invalid", "12345")

    def test_validate_format_valid(self, article_client):
        """Test validation with valid format."""
        # Should not raise any exception
        article_client._validate_format("json")
        article_client._validate_format("xml")

    def test_validate_format_invalid(self, article_client):
        """Test validation with invalid format."""
        with pytest.raises(ValidationError):
            article_client._validate_citations_format("invalid")

    # Additional comprehensive tests for coverage
    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_citations_with_all_params(self, mock_get, article_client):
        """Test citations with all parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {"citationList": {}, "hitCount": 1}
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/xml"}
        mock_get.return_value = mock_response

        article_client.get_citations(
            "MED", "12345", page=2, page_size=50,
            format="xml", extra_param="test"
        )

        mock_get.assert_called_once_with(
            "MED/12345/citations",
            params={"page": 2, "pageSize": 50, "format": "xml", "extra_param": "test"}
        )

    @patch('pyeuropepmc.clients.article.ArticleClient._get')
    def test_get_supplementary_files_basic(self, mock_get, article_client):
        """Test basic supplementary files retrieval."""
        mock_response = Mock()
        mock_response.content = b"test binary data"
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/zip"}
        mock_get.return_value = mock_response

        result = article_client.get_supplementary_files("PMC12345")

        assert result == b"test binary data"
        mock_get.assert_called_once_with(
            "PMC12345/supplementaryFiles", params={'includeInlineImage': 'true'}, stream=True
        )

    def test_validation_source_and_id_edge_cases(self, article_client):
        """Test edge cases for source and ID validation."""
        # Valid cases
        article_client._validate_source_and_id("MED", "12345")
        article_client._validate_source_and_id("PMC", "PMC123")

        # Invalid source length
        with pytest.raises(ValidationError):
            article_client._validate_source_and_id("MEDLINE", "12345")

        # Empty article ID
        with pytest.raises(ValidationError):
            article_client._validate_source_and_id("MED", "")

    def test_pagination_validation_edge_cases(self, article_client):
        """Test edge cases for pagination validation."""
        # Valid cases
        article_client._validate_pagination(1, 1)
        article_client._validate_pagination(999, 1000)

        # Invalid page
        with pytest.raises(ValidationError):
            article_client._validate_pagination(0, 25)

        # Invalid page size
        with pytest.raises(ValidationError):
            article_client._validate_pagination(1, 1001)
