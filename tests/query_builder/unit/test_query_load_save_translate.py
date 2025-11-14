"""
Tests for QueryBuilder load, save, translate, and evaluate functionality.

This module tests the integration with the search-query package for:
- Loading queries from strings and JSON files
- Saving queries to JSON files with metadata
- Translating queries between platforms
- Evaluating search effectiveness
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pyeuropepmc.query.query_builder import QueryBuilder
from pyeuropepmc.core.exceptions import QueryBuilderError


class TestQueryBuilderFromString:
    """Test loading queries from strings."""

    def test_from_string_basic(self) -> None:
        """Test loading a simple query from a string."""
        query_string = "cancer AND treatment"
        qb = QueryBuilder.from_string(query_string, platform="pubmed")

        assert qb is not None
        assert qb._parts == [query_string]
        assert qb._parsed_query is not None

    def test_from_string_with_validate(self) -> None:
        """Test loading with validation enabled."""
        query_string = "cancer AND treatment"
        qb = QueryBuilder.from_string(query_string, platform="pubmed", validate=True)

        assert qb is not None
        assert qb._validate is True

    def test_from_string_different_platforms(self) -> None:
        """Test loading queries from different platform syntaxes."""
        # PubMed syntax
        pubmed_query = "cancer[ti]"
        qb_pubmed = QueryBuilder.from_string(pubmed_query, platform="pubmed")
        assert qb_pubmed is not None

        # Web of Science syntax
        wos_query = "TI=cancer"
        qb_wos = QueryBuilder.from_string(wos_query, platform="wos")
        assert qb_wos is not None

    def test_from_string_empty_raises_error(self) -> None:
        """Test that empty string raises QueryBuilderError."""
        with pytest.raises(QueryBuilderError):
            QueryBuilder.from_string("", platform="pubmed")

    def test_from_string_whitespace_raises_error(self) -> None:
        """Test that whitespace-only string raises QueryBuilderError."""
        with pytest.raises(QueryBuilderError):
            QueryBuilder.from_string("   ", platform="pubmed")

    def test_from_string_invalid_syntax_raises_error(self) -> None:
        """Test that invalid query syntax raises QueryBuilderError."""
        # Unbalanced parentheses
        with pytest.raises(QueryBuilderError):
            QueryBuilder.from_string("(cancer AND treatment", platform="pubmed")


class TestQueryBuilderFromFile:
    """Test loading queries from JSON files."""

    def test_from_file_standard_format(self) -> None:
        """Test loading a query from a standard JSON file."""
        # Create a temporary JSON file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            search_data = {
                "search_string": "cancer AND treatment",
                "platform": "pubmed",
                "version": "1",
                "authors": [{"name": "John Doe", "ORCID": "0000-0000-0000-0001"}],
                "date": {
                    "data_entry": "2025-01-01",
                    "search_conducted": "2025-01-01",
                },
                "database": ["PubMed", "PMC"],
                "record_info": {},
            }
            json.dump(search_data, tmp_file)
            tmp_path = tmp_file.name

        try:
            # Load the query
            qb = QueryBuilder.from_file(tmp_path)

            assert qb is not None
            assert qb._parts == ["cancer AND treatment"]
            assert qb._parsed_query is not None
            assert qb._search_file is not None
        finally:
            # Clean up
            Path(tmp_path).unlink()

    def test_from_file_not_found_raises_error(self) -> None:
        """Test that non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            QueryBuilder.from_file("/nonexistent/path/to/file.json")

    def test_from_file_with_validate(self) -> None:
        """Test loading from file with validation enabled."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            search_data = {
                "search_string": "cancer AND treatment",
                "platform": "pubmed",
                "version": "1",
                "authors": [],
                "date": {},
                "record_info": {},
            }
            json.dump(search_data, tmp_file)
            tmp_path = tmp_file.name

        try:
            qb = QueryBuilder.from_file(tmp_path, validate=True)
            assert qb._validate is True
        finally:
            Path(tmp_path).unlink()


class TestQueryBuilderSave:
    """Test saving queries to JSON files."""

    def test_save_basic(self) -> None:
        """Test saving a simple query to a JSON file."""
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Save the query
            qb.save(tmp_path, platform="pubmed")

            # Verify file was created
            assert Path(tmp_path).exists()

            # Load and verify contents
            with open(tmp_path) as f:
                data = json.load(f)

            assert "search_string" in data
            assert "platform" in data
            assert data["platform"] == "pubmed"
            assert "version" in data
            assert "cancer" in data["search_string"]
            assert "treatment" in data["search_string"]
        finally:
            Path(tmp_path).unlink()

    def test_save_with_metadata(self) -> None:
        """Test saving a query with full metadata."""
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment")

        authors = [{"name": "Jane Smith", "ORCID": "0000-0000-0000-0002"}]
        date_info = {
            "data_entry": "2025-11-06",
            "search_conducted": "2025-11-06",
        }
        database = ["PubMed", "PMC", "Europe PMC"]
        record_info = {"project": "Cancer Research Review"}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            qb.save(
                tmp_path,
                platform="pubmed",
                authors=authors,
                date_info=date_info,
                database=database,
                record_info=record_info,
            )

            # Verify contents
            with open(tmp_path) as f:
                data = json.load(f)

            assert data["authors"] == authors
            assert data["date"] == date_info
            # Database is wrapped in a dict by SearchFile
            assert data["database"] == {"databases": database}
            assert data["record_info"] == record_info
        finally:
            Path(tmp_path).unlink()

    def test_save_with_generic_query(self) -> None:
        """Test saving with generic query representation."""
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            qb.save(tmp_path, platform="pubmed", include_generic=True)

            with open(tmp_path) as f:
                data = json.load(f)

            # Should have generic_query field
            assert "generic_query" in data
            assert data["generic_query"] is not None
        finally:
            Path(tmp_path).unlink()


class TestQueryBuilderTranslate:
    """Test translating queries between platforms."""

    def test_translate_pubmed_to_wos(self) -> None:
        """Test translating from PubMed to Web of Science syntax."""
        # Create a query in PubMed syntax
        query_string = "cancer[ti]"
        qb = QueryBuilder.from_string(query_string, platform="pubmed")

        # Translate to Web of Science
        wos_query = qb.translate("wos")

        assert wos_query is not None
        assert isinstance(wos_query, str)
        # WoS uses TI= for title
        assert "TI=" in wos_query or "TI:" in wos_query

    def test_translate_to_generic(self) -> None:
        """Test translating to generic syntax."""
        qb = QueryBuilder()
        query = qb.keyword("cancer", field="title").and_().keyword("treatment")
        qb_str = qb.build()

        # Create from string to get parsed query
        qb2 = QueryBuilder.from_string(qb_str, platform="pubmed")

        # Translate to generic
        generic_query = qb2.translate("generic")

        assert generic_query is not None
        assert isinstance(generic_query, str)

    def test_translate_without_parsed_query(self) -> None:
        """Test translate when query hasn't been parsed yet."""
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment")

        # Should still work even without pre-parsed query
        translated = qb.translate("wos")
        assert translated is not None

    def test_translate_invalid_platform_raises_error(self) -> None:
        """Test that invalid target platform raises error."""
        qb = QueryBuilder()
        query = qb.keyword("cancer")

        # search-query should raise an error for invalid platforms
        with pytest.raises(QueryBuilderError):
            qb.translate("invalid_platform")


class TestQueryBuilderToQueryObject:
    """Test converting to search-query Query objects."""

    def test_to_query_object_basic(self) -> None:
        """Test converting QueryBuilder to Query object."""
        qb = QueryBuilder()
        query = qb.keyword("cancer").and_().keyword("treatment")

        query_obj = qb.to_query_object()

        assert query_obj is not None
        # Check it has expected Query object attributes
        assert hasattr(query_obj, "evaluate") or hasattr(query_obj, "to_string")

    def test_to_query_object_cached(self) -> None:
        """Test that Query object is cached."""
        qb = QueryBuilder()
        query = qb.keyword("cancer")

        # First call creates and caches
        query_obj1 = qb.to_query_object()

        # Second call returns cached
        query_obj2 = qb.to_query_object()

        assert query_obj1 is query_obj2

    def test_to_query_object_from_parsed(self) -> None:
        """Test to_query_object when query was loaded from string."""
        query_string = "cancer AND treatment"
        qb = QueryBuilder.from_string(query_string, platform="pubmed")

        query_obj = qb.to_query_object()

        assert query_obj is not None
        # Should use the already parsed query
        assert qb._parsed_query is query_obj


class TestQueryBuilderEvaluate:
    """Test query evaluation functionality."""

    def test_evaluate_basic(self) -> None:
        """Test basic query evaluation."""
        # Create sample records
        records = {
            "r1": {
                "title": "Cancer treatment research",
                "colrev_status": "rev_included",
            },
            "r2": {
                "title": "Cancer diagnosis methods",
                "colrev_status": "rev_included",
            },
            "r3": {
                "title": "Unrelated medical topic",
                "colrev_status": "rev_excluded",
            },
        }

        # Create a query that can be evaluated
        qb = QueryBuilder().keyword("cancer")
        results = qb.evaluate(records, platform="pubmed")

        # Should have recall, precision, and f1_score
        assert "recall" in results
        assert "precision" in results
        assert "f1_score" in results

        # Since "cancer" appears in both included titles, recall should be 1.0
        assert results["recall"] == 1.0

    def test_evaluate_perfect_recall(self) -> None:
        """Test evaluation with perfect recall."""
        records = {
            "r1": {
                "title": "Microsourcing platforms for online labor",
                "colrev_status": "rev_included",
            },
            "r2": {
                "title": "Online work and the future of microsourcing",
                "colrev_status": "rev_included",
            },
        }

        # Use pubmed syntax for evaluation
        qb = QueryBuilder().keyword("online")
        results = qb.evaluate(records, platform="pubmed")

        # Should match all included records
        assert results["recall"] == 1.0

    def test_evaluate_uses_cached_query(self) -> None:
        """Test that evaluate uses cached Query object."""
        # Use pubmed syntax to get a proper parsed query
        qb = QueryBuilder().keyword("cancer")

        # Pre-load query object
        query_obj = qb.to_query_object()

        records = {
            "r1": {
                "title": "Cancer research",
                "colrev_status": "rev_included",
            },
        }

        results = qb.evaluate(records, platform="pubmed")

        # Should use the same cached object
        assert qb._parsed_query is query_obj


class TestIntegrationLoadSaveTranslate:
    """Integration tests for load/save/translate workflow."""

    def test_round_trip_save_load(self) -> None:
        """Test saving and loading a query preserves content."""
        # Create a query
        qb1 = QueryBuilder()
        query = qb1.keyword("cancer").and_().keyword("treatment")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Save
            qb1.save(tmp_path, platform="pubmed")

            # Load
            qb2 = QueryBuilder.from_file(tmp_path)

            # Should have same query string
            assert qb1.build() == qb2.build()
        finally:
            Path(tmp_path).unlink()

    def test_load_translate_save(self) -> None:
        """Test loading, translating, and saving a query."""
        # Create initial query file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            search_data = {
                "search_string": "cancer[ti]",
                "platform": "pubmed",
                "version": "1",
                "authors": [],
                "date": {},
                "record_info": {},
            }
            json.dump(search_data, tmp_file)
            tmp_path1 = tmp_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            tmp_path2 = tmp_file.name

        try:
            # Load PubMed query
            qb = QueryBuilder.from_file(tmp_path1)

            # Translate to WoS
            wos_query = qb.translate("wos")

            # Create new QueryBuilder with translated query
            qb_wos = QueryBuilder.from_string(wos_query, platform="wos")

            # Save WoS version
            qb_wos.save(tmp_path2, platform="wos")

            # Verify saved file
            with open(tmp_path2) as f:
                data = json.load(f)

            assert data["platform"] == "wos"
        finally:
            Path(tmp_path1).unlink()
            Path(tmp_path2).unlink()


class TestSearchQueryNotAvailable:
    """Test behavior when search-query package is not available."""

    @patch("pyeuropepmc.query.query_builder.parse", side_effect=ImportError("No module named 'search_query'"))
    def test_from_string_raises_import_error(self, mock_parse) -> None:
        """Test that from_string raises ImportError when package not available."""
        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            QueryBuilder.from_string("cancer", platform="pubmed")

    @patch("pyeuropepmc.query.query_builder.load_search_file", side_effect=ImportError("No module named 'search_query'"))
    def test_from_file_raises_import_error(self, mock_load) -> None:
        """Test that from_file raises ImportError when package not available."""
        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            QueryBuilder.from_file("test.json")

    @patch("pyeuropepmc.query.query_builder.parse", side_effect=ImportError("No module named 'search_query'"))
    def test_save_raises_import_error(self, mock_parse) -> None:
        """Test that save raises ImportError when package not available."""
        qb = QueryBuilder()
        qb.keyword("cancer")

        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            qb.save("test.json")

    @patch("pyeuropepmc.query.query_builder.parse", side_effect=ImportError("No module named 'search_query'"))
    def test_translate_raises_import_error(self, mock_parse) -> None:
        """Test that translate raises ImportError when package not available."""
        qb = QueryBuilder()
        qb.keyword("cancer")

        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            qb.translate("wos")

    @patch("pyeuropepmc.query.query_builder.parse", side_effect=ImportError("No module named 'search_query'"))
    def test_to_query_object_raises_import_error(self, mock_parse) -> None:
        """Test that to_query_object raises ImportError when package not available."""
        qb = QueryBuilder()
        qb.keyword("cancer")

        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            qb.to_query_object()

    @patch("pyeuropepmc.query.query_builder.parse", side_effect=ImportError("No module named 'search_query'"))
    def test_evaluate_raises_import_error(self, mock_parse) -> None:
        """Test that evaluate raises ImportError when package not available."""
        qb = QueryBuilder()
        qb.keyword("cancer")

        records = {"r1": {"title": "test", "colrev_status": "rev_included"}}

        with pytest.raises(QueryBuilderError, match="search-query package is required"):
            qb.evaluate(records)
