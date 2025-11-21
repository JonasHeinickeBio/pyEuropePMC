"""
Unit tests for AnnotationsClient.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from pyeuropepmc.clients.annotations import AnnotationsClient
from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.core.exceptions import ValidationError, APIClientError


@pytest.fixture
def annotations_client():
    """Create an AnnotationsClient instance for testing."""
    return AnnotationsClient(rate_limit_delay=0.1)


@pytest.fixture
def cached_annotations_client():
    """Create an AnnotationsClient with caching enabled."""
    cache_config = CacheConfig(enabled=True)
    return AnnotationsClient(rate_limit_delay=0.1, cache_config=cache_config)


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "annotations": [
            {
                "type": "entity",
                "exact": "malaria",
                "tags": [
                    {
                        "uri": "DOID:12365",
                        "name": "malaria",
                        "type": "Disease",
                    }
                ],
                "section": "abstract",
                "provider": {"name": "Europe PMC"},
            }
        ],
        "totalCount": 1,
        "page": 1,
        "pageSize": 25,
    }
    return response


class TestAnnotationsClientInitialization:
    """Test AnnotationsClient initialization."""

    def test_init_default(self):
        """Test default initialization."""
        client = AnnotationsClient()
        assert client.rate_limit_delay == 1.0
        assert not client.is_closed
        assert client._cache is not None

    def test_init_with_rate_limit(self):
        """Test initialization with custom rate limit."""
        client = AnnotationsClient(rate_limit_delay=2.0)
        assert client.rate_limit_delay == 2.0

    def test_init_with_cache_config(self):
        """Test initialization with cache configuration."""
        cache_config = CacheConfig(enabled=True)
        client = AnnotationsClient(cache_config=cache_config)
        assert client._cache is not None

    def test_repr(self, annotations_client):
        """Test string representation."""
        repr_str = repr(annotations_client)
        assert "AnnotationsClient" in repr_str
        assert "rate_limit_delay" in repr_str
        assert "status=active" in repr_str

    def test_context_manager(self):
        """Test context manager usage."""
        with AnnotationsClient() as client:
            assert not client.is_closed
        # Client should be closed after exiting context


class TestGetAnnotationsByArticleIds:
    """Test get_annotations_by_article_ids method."""

    @patch.object(AnnotationsClient, "_get")
    def test_get_annotations_by_article_ids_success(
        self, mock_get, annotations_client, mock_response
    ):
        """Test successful retrieval of annotations by article IDs."""
        mock_get.return_value = mock_response

        result = annotations_client.get_annotations_by_article_ids(["PMC1234567"])

        assert isinstance(result, dict)
        assert "annotations" in result
        assert result["totalCount"] == 1
        mock_get.assert_called_once()

    @patch.object(AnnotationsClient, "_get")
    def test_get_annotations_with_filters(
        self, mock_get, annotations_client, mock_response
    ):
        """Test retrieval with provider and type filters."""
        mock_get.return_value = mock_response

        result = annotations_client.get_annotations_by_article_ids(
            ["PMC1234567"],
            provider="Europe PMC",
            annotation_type="Disease",
        )

        assert isinstance(result, dict)
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "provider" in call_args[1]["params"]
        assert "type" in call_args[1]["params"]

    def test_get_annotations_invalid_article_ids(self, annotations_client):
        """Test with invalid article IDs."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_article_ids([])

        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_article_ids(None)

    def test_get_annotations_invalid_section(self, annotations_client):
        """Test with invalid section parameter."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_article_ids(
                ["PMC1234567"], section="invalid"
            )

    def test_get_annotations_invalid_format(self, annotations_client):
        """Test with invalid format parameter."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_article_ids(
                ["PMC1234567"], format="INVALID"
            )


class TestGetAnnotationsByEntity:
    """Test get_annotations_by_entity method."""

    @patch.object(AnnotationsClient, "_get")
    def test_get_annotations_by_entity_success(
        self, mock_get, annotations_client, mock_response
    ):
        """Test successful retrieval of annotations by entity."""
        mock_get.return_value = mock_response

        result = annotations_client.get_annotations_by_entity(
            entity_id="CHEBI:16236", entity_type="CHEBI"
        )

        assert isinstance(result, dict)
        assert "annotations" in result
        mock_get.assert_called_once()

    def test_get_annotations_by_entity_invalid_id(self, annotations_client):
        """Test with invalid entity ID."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id="", entity_type="CHEBI"
            )

        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id=None, entity_type="CHEBI"
            )

    def test_get_annotations_by_entity_invalid_type(self, annotations_client):
        """Test with invalid entity type."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id="CHEBI:16236", entity_type=""
            )

    def test_get_annotations_by_entity_invalid_pagination(self, annotations_client):
        """Test with invalid pagination parameters."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id="CHEBI:16236", entity_type="CHEBI", page=0
            )

        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id="CHEBI:16236", entity_type="CHEBI", page_size=0
            )

        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_entity(
                entity_id="CHEBI:16236", entity_type="CHEBI", page_size=2000
            )


class TestGetAnnotationsByProvider:
    """Test get_annotations_by_provider method."""

    @patch.object(AnnotationsClient, "_get")
    def test_get_annotations_by_provider_success(
        self, mock_get, annotations_client, mock_response
    ):
        """Test successful retrieval of annotations by provider."""
        mock_get.return_value = mock_response

        result = annotations_client.get_annotations_by_provider("Europe PMC")

        assert isinstance(result, dict)
        assert "annotations" in result
        mock_get.assert_called_once()

    def test_get_annotations_by_provider_invalid(self, annotations_client):
        """Test with invalid provider."""
        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_provider("")

        with pytest.raises(ValidationError):
            annotations_client.get_annotations_by_provider(None)

    @patch.object(AnnotationsClient, "_get")
    def test_get_annotations_by_provider_with_filters(
        self, mock_get, annotations_client, mock_response
    ):
        """Test retrieval with additional filters."""
        mock_get.return_value = mock_response

        result = annotations_client.get_annotations_by_provider(
            "Europe PMC",
            article_ids=["PMC1234567"],
            annotation_type="Disease",
        )

        assert isinstance(result, dict)
        mock_get.assert_called_once()


class TestCacheManagement:
    """Test cache management methods."""

    def test_clear_cache(self, cached_annotations_client):
        """Test cache clearing."""
        result = cached_annotations_client.clear_cache()
        assert isinstance(result, bool)

    def test_get_cache_stats(self, cached_annotations_client):
        """Test getting cache statistics."""
        stats = cached_annotations_client.get_cache_stats()
        assert isinstance(stats, dict)

    def test_get_cache_health(self, cached_annotations_client):
        """Test getting cache health."""
        health = cached_annotations_client.get_cache_health()
        assert isinstance(health, dict)

    def test_invalidate_annotations_cache(self, cached_annotations_client):
        """Test invalidating annotation cache."""
        result = cached_annotations_client.invalidate_annotations_cache()
        assert isinstance(result, int)


class TestValidationMethods:
    """Test validation methods."""

    def test_validate_section(self, annotations_client):
        """Test section validation."""
        # Valid sections should not raise
        annotations_client._validate_section("all")
        annotations_client._validate_section("abstract")
        annotations_client._validate_section("fulltext")

        # Invalid section should raise
        with pytest.raises(ValidationError):
            annotations_client._validate_section("invalid")

    def test_validate_format(self, annotations_client):
        """Test format validation."""
        # Valid formats should not raise
        annotations_client._validate_format("JSON-LD")
        annotations_client._validate_format("JSON")
        annotations_client._validate_format("XML")
        annotations_client._validate_format("json-ld")

        # Invalid format should raise
        with pytest.raises(ValidationError):
            annotations_client._validate_format("INVALID")

    def test_validate_pagination(self, annotations_client):
        """Test pagination validation."""
        # Valid pagination should not raise
        annotations_client._validate_pagination(1, 25)
        annotations_client._validate_pagination(10, 100)

        # Invalid page should raise
        with pytest.raises(ValidationError):
            annotations_client._validate_pagination(0, 25)

        # Invalid page_size should raise
        with pytest.raises(ValidationError):
            annotations_client._validate_pagination(1, 0)

        with pytest.raises(ValidationError):
            annotations_client._validate_pagination(1, 2000)


class TestCloseAndCleanup:
    """Test close and cleanup methods."""

    def test_close(self):
        """Test closing the client."""
        client = AnnotationsClient()
        assert not client.is_closed
        client.close()
        assert client.is_closed

    def test_double_close(self):
        """Test closing an already closed client."""
        client = AnnotationsClient()
        client.close()
        # Second close should not raise
        client.close()
        assert client.is_closed
