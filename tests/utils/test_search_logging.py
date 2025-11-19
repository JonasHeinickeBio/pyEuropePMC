"""
Unit tests for search logging functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pyeuropepmc.utils.search_logging import (
    SearchLog,
    SearchLogEntry,
    generate_private_key,
    prisma_summary,
    record_peer_review,
    record_platform,
    record_query,
    record_results,
    sign_and_zip_results,
    sign_file,
    start_search,
    zip_results,
    record_export,
)


class TestSearchLogEntry:
    """Test SearchLogEntry dataclass."""

    def test_entry_creation(self):
        """Test basic entry creation."""
        entry = SearchLogEntry(
            database="EuropePMC",
            query="cancer AND immunotherapy",
            filters={"date": "2020-2024", "open_access": True},
            results_returned=150,
            notes="First search iteration",
            platform="API v1.0",
        )

        assert entry.database == "EuropePMC"
        assert entry.query == "cancer AND immunotherapy"
        assert entry.filters == {"date": "2020-2024", "open_access": True}
        assert entry.results_returned == 150
        assert entry.notes == "First search iteration"
        assert entry.platform == "API v1.0"
        assert entry.raw_results_path is None
        assert entry.export_path is None
        assert entry.date_run is not None

    def test_entry_defaults(self):
        """Test entry with default values."""
        entry = SearchLogEntry(
            database="PubMed",
            query="diabetes",
            filters={},
        )

        assert entry.database == "PubMed"
        assert entry.query == "diabetes"
        assert entry.filters == {}
        assert entry.results_returned is None
        assert entry.notes is None
        assert entry.raw_results_path is None
        assert entry.platform is None
        assert entry.export_path is None
        assert entry.date_run is not None


class TestSearchLog:
    """Test SearchLog dataclass."""

    def test_log_creation(self):
        """Test basic log creation."""
        log = SearchLog(
            title="Cancer Immunotherapy Search",
            executed_by="Dr. Smith",
            deduplicated_total=500,
            final_included=25,
        )

        assert log.title == "Cancer Immunotherapy Search"
        assert log.executed_by == "Dr. Smith"
        assert log.deduplicated_total == 500
        assert log.final_included == 25
        assert log.entries == []
        assert log.peer_reviewed is None
        assert log.export_format is None
        assert log.created_at is not None
        assert log.last_updated is not None

    def test_log_defaults(self):
        """Test log with default values."""
        log = SearchLog(title="Test Search")

        assert log.title == "Test Search"
        assert log.executed_by is None
        assert log.deduplicated_total is None
        assert log.final_included is None
        assert log.entries == []
        assert log.peer_reviewed is None
        assert log.export_format is None

    def test_add_entry(self):
        """Test adding entries to log."""
        log = SearchLog(title="Test")

        entry1 = SearchLogEntry(database="DB1", query="query1", filters={})
        entry2 = SearchLogEntry(database="DB2", query="query2", filters={})

        log.add_entry(entry1)
        assert len(log.entries) == 1
        assert log.entries[0] == entry1

        log.add_entry(entry2)
        assert len(log.entries) == 2
        assert log.entries[1] == entry2

        # Should update last_updated
        assert log.last_updated > log.created_at

    def test_to_dict(self):
        """Test log serialization to dict."""
        log = SearchLog(title="Test", executed_by="User")
        log.add_entry(SearchLogEntry(database="DB", query="query", filters={}))

        data = log.to_dict()
        assert data["title"] == "Test"
        assert data["executed_by"] == "User"
        assert len(data["entries"]) == 1
        assert "created_at" in data
        assert "last_updated" in data

    @pytest.mark.parametrize("format", ["json", "csv", "ris"])
    def test_export_formats(self, format):
        """Test exporting log in different formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log = SearchLog(title="Test Export")
            log.add_entry(SearchLogEntry(
                database="EuropePMC",
                query="cancer",
                filters={"date": "2020-2024"},
                results_returned=100,
            ))

            export_path = Path(temp_dir) / f"test.{format}"

            result_path = log.export(export_path, format=format)

            assert result_path.exists()
            assert result_path == export_path

            # Check export format was recorded
            assert log.export_format == format

            # Verify file content based on format
            if format == "json":
                with open(result_path) as f:
                    data = json.load(f)
                    assert data["title"] == "Test Export"
                    assert len(data["entries"]) == 1
            elif format == "csv":
                content = result_path.read_text()
                assert "database" in content
                assert "EuropePMC" in content
            elif format == "ris":
                content = result_path.read_text()
                assert "TY  - SER" in content
                assert "DB  - EuropePMC" in content

    def test_export_unsupported_format(self):
        """Test exporting with unsupported format."""
        log = SearchLog(title="Test")

        with pytest.raises(ValueError, match="Unsupported export format"):
            log.export("test.txt", format="unsupported")

    def test_save(self):
        """Test saving log to JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log = SearchLog(title="Test Save")
            log.add_entry(SearchLogEntry(database="DB", query="query", filters={}))

            save_path = Path(temp_dir) / "test_log.json"

            result_path = log.save(save_path)

            assert result_path.exists()
            assert result_path == save_path

            # Verify content
            with open(result_path) as f:
                data = json.load(f)
                assert data["title"] == "Test Save"
                assert len(data["entries"]) == 1


class TestSearchLoggingFunctions:
    """Test standalone search logging functions."""

    def test_start_search(self):
        """Test starting a new search log."""
        log = start_search("Test Search", executed_by="Tester")

        assert isinstance(log, SearchLog)
        assert log.title == "Test Search"
        assert log.executed_by == "Tester"
        assert log.entries == []

    def test_record_query_basic(self):
        """Test recording a basic query."""
        log = SearchLog(title="Test")

        record_query(
            log=log,
            database="EuropePMC",
            query="cancer research",
            filters={"date": "2020-2024"},
            results_returned=150,
            notes="Test query",
        )

        assert len(log.entries) == 1
        entry = log.entries[0]
        assert entry.database == "EuropePMC"
        assert entry.query == "cancer research"
        assert entry.filters == {"date": "2020-2024"}
        assert entry.results_returned == 150
        assert entry.notes == "Test query"
        assert entry.raw_results_path is None

    def test_record_query_with_raw_results(self):
        """Test recording query with raw results."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log = SearchLog(title="Test")

            raw_results = {"results": [{"id": "1", "title": "Paper 1"}]}
            results_dir = Path(temp_dir) / "raw"

            record_query(
                log=log,
                database="EuropePMC",
                query="test",
                filters={},
                raw_results=raw_results,
                raw_results_dir=results_dir,
                raw_results_filename="test_results.json",
            )

            assert len(log.entries) == 1
            entry = log.entries[0]
            assert entry.raw_results_path is not None

            # Verify file was created
            results_file = Path(entry.raw_results_path)
            assert results_file.exists()

            # Verify content
            with open(results_file) as f:
                saved_data = json.load(f)
                assert saved_data == raw_results

    def test_record_query_raw_results_error(self):
        """Test recording query when raw results save fails."""
        log = SearchLog(title="Test")

        # Use invalid directory to trigger error
        record_query(
            log=log,
            database="EuropePMC",
            query="test",
            filters={},
            raw_results={"test": "data"},
            raw_results_dir="/invalid/path/that/does/not/exist",
        )

        # Entry should still be created, but without raw_results_path
        assert len(log.entries) == 1
        entry = log.entries[0]
        assert entry.raw_results_path is None

    def test_record_results(self):
        """Test recording aggregate results."""
        log = SearchLog(title="Test")

        record_results(log, deduplicated_total=500, final_included=25)

        assert log.deduplicated_total == 500
        assert log.final_included == 25

    def test_record_peer_review(self):
        """Test recording peer review status."""
        log = SearchLog(title="Test")

        record_peer_review(log, "PRESS checklist completed")

        assert log.peer_reviewed == "PRESS checklist completed"

    def test_record_platform(self):
        """Test recording platform for last entry."""
        log = SearchLog(title="Test")
        log.add_entry(SearchLogEntry(database="DB", query="query", filters={}))

        record_platform(log, "API v2.0")

        assert log.entries[-1].platform == "API v2.0"

    def test_record_export(self):
        """Test recording export information."""
        log = SearchLog(title="Test")
        log.add_entry(SearchLogEntry(database="DB", query="query", filters={}))

        record_export(log, "/path/to/export.csv", "csv")

        assert log.entries[-1].export_path == "/path/to/export.csv"
        assert log.export_format == "csv"

    def test_prisma_summary(self):
        """Test generating PRISMA summary."""
        log = SearchLog(title="Cancer Search", executed_by="Researcher")

        # Add some entries
        log.add_entry(SearchLogEntry(
            database="EuropePMC",
            query="cancer",
            filters={},
            results_returned=100,
        ))
        log.add_entry(SearchLogEntry(
            database="PubMed",
            query="neoplasm",
            filters={},
            results_returned=80,
        ))

        log.deduplicated_total = 150
        log.final_included = 20

        summary = prisma_summary(log)

        assert summary["title"] == "Cancer Search"
        assert summary["executed_by"] == "Researcher"
        assert summary["records_by_database"] == {"EuropePMC": 100, "PubMed": 80}
        assert summary["total_records_identified"] == 180
        assert summary["deduplicated_total"] == 150
        assert summary["final_included"] == 20

    def test_zip_results(self):
        """Test zipping result files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            file1 = Path(temp_dir) / "file1.txt"
            file2 = Path(temp_dir) / "file2.txt"
            file1.write_text("content 1")
            file2.write_text("content 2")

            zip_path = Path(temp_dir) / "results.zip"

            result_path = zip_results([str(file1), str(file2)], zip_path)

            assert result_path == str(zip_path)
            assert zip_path.exists()

            # Verify zip contents
            import zipfile
            with zipfile.ZipFile(zip_path) as zf:
                assert "file1.txt" in zf.namelist()
                assert "file2.txt" in zf.namelist()

    @patch("cryptography.hazmat.primitives.asymmetric.rsa")
    @patch("cryptography.hazmat.primitives.serialization.load_pem_private_key")
    def test_sign_file(self, mock_load_pem, mock_rsa):
        """Test signing a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file and mock key
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            key_file = Path(temp_dir) / "key.pem"
            # Create a dummy key file (the actual content doesn't matter since we're mocking)
            key_file.write_text("dummy key content for testing\nnot a real private key")

            # Set up mock RSA class
            mock_rsa.RSAPrivateKey = Mock

            # Mock the cryptographic operations
            mock_private_key = Mock()
            mock_private_key.sign.return_value = b"signature"
            mock_load_pem.return_value = mock_private_key

            sig_path = sign_file(test_file, key_file)

            expected_sig = str(test_file) + ".sig"
            assert sig_path == expected_sig

            # Verify signature file was created
            sig_file = Path(sig_path)
            assert sig_file.exists()
            assert sig_file.read_bytes() == b"signature"

    @patch("pyeuropepmc.utils.search_logging.sign_file")
    @patch("pyeuropepmc.utils.search_logging.zip_results")
    def test_sign_and_zip_results(self, mock_zip, mock_sign):
        """Test signing and zipping results."""
        mock_zip.return_value = "/path/to/results.zip"
        mock_sign.return_value = "/path/to/results.zip.sig"

        with tempfile.TemporaryDirectory() as temp_dir:
            files = ["file1.txt", "file2.txt"]
            zip_path = Path(temp_dir) / "results.zip"
            key_path = Path(temp_dir) / "key.pem"

            result = sign_and_zip_results(files, zip_path, private_key_path=key_path)

            assert result == ("/path/to/results.zip", "/path/to/results.zip.sig")
            mock_zip.assert_called_once_with(files, zip_path)
            mock_sign.assert_called_once_with("/path/to/results.zip", key_path)

    @patch("pyeuropepmc.utils.search_logging.zip_results")
    def test_sign_and_zip_results_no_signing(self, mock_zip):
        """Test zipping results without signing."""
        mock_zip.return_value = "/path/to/results.zip"

        result = sign_and_zip_results(["file1.txt"], "/path/to/results.zip")

        assert result == "/path/to/results.zip"
        mock_zip.assert_called_once()

    @patch("pyeuropepmc.utils.search_logging.rsa")
    @patch("pyeuropepmc.utils.search_logging.serialization")
    def test_generate_private_key(self, mock_serialization, mock_rsa):
        """Test generating a private key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock key generation
            mock_private_key = Mock()
            mock_public_key = Mock()
            mock_private_key.public_key.return_value = mock_public_key
            mock_private_key.private_bytes.return_value = b"private key data"
            mock_public_key.public_bytes.return_value = b"public key data"

            mock_rsa.generate_private_key.return_value = mock_private_key

            private_path = Path(temp_dir) / "private.pem"
            public_path = Path(temp_dir) / "public.pem"

            result_private, result_public = generate_private_key(
                private_path,
                public_path,
                name="Test User",
                email="test@example.com",
            )

            assert result_private == str(private_path)
            assert result_public == str(public_path)

            # Verify files were created
            assert private_path.exists()
            assert public_path.exists()

    def test_generate_private_key_no_crypto(self):
        """Test key generation when cryptography is not available."""
        with patch("pyeuropepmc.utils.search_logging.serialization", None):
            with pytest.raises(ImportError):
                generate_private_key("/tmp/key.pem")
