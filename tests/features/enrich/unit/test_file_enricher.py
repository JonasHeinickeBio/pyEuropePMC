"""
Unit tests for FileEnricher.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.enrich.config import EnrichmentConfig
from pyeuropepmc.features.enrich.file_enricher import FileEnricher


@pytest.fixture
def config():
    """Fixture for EnrichmentConfig."""
    return EnrichmentConfig()


@pytest.fixture
def file_enricher(config):
    """Fixture for FileEnricher with mocked PaperEnricher."""
    with patch("pyeuropepmc.features.enrich.enricher.PaperEnricher") as MockPaperEnricher:
        mock_instance = MagicMock()
        mock_instance.enrich_paper.return_value = {
            "sources": ["crossref"],
            "merged": {"title": "Enriched Title", "doi": "10.1234/test"},
            "enrichment_timestamp": "2024-01-01T00:00:00",
        }
        MockPaperEnricher.return_value = mock_instance
        enricher = FileEnricher(config)
        yield enricher


class TestFileEnricher:
    """Tests for FileEnricher."""

    def test_initialization(self, config):
        """Test FileEnricher initialization."""
        with patch("pyeuropepmc.features.enrich.enricher.PaperEnricher"):
            enricher = FileEnricher(config)
        assert enricher.config == config
        assert enricher.enricher is not None

    def test_enrich_from_files_single(self, file_enricher):
        """Test enriching from a single file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"doi": "10.1234/test", "title": "Original Title"}, f)
            f.flush()
            temp_path = f.name

        try:
            results = file_enricher.enrich_from_files([temp_path])
            assert temp_path in results
            result = results[temp_path]
            assert "original" in result
            assert "enriched" in result
            assert "merged" in result
            assert result["merged"]["title"] == "Enriched Title"  # enriched overrides
            assert result["merged"]["doi"] == "10.1234/test"
            assert "enrichment_sources" in result["merged"]
            assert "enrichment_timestamp" in result["merged"]
        finally:
            os.unlink(temp_path)

    def test_enrich_from_files_multiple(self, file_enricher):
        """Test enriching from multiple files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f1, \
                tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f2:
            json.dump({"doi": "10.1234/test1", "title": "Paper 1"}, f1)
            json.dump({"doi": "10.1234/test2", "title": "Paper 2"}, f2)
            f1.flush()
            f2.flush()
            paths = [f1.name, f2.name]

        try:
            results = file_enricher.enrich_from_files(paths)
            assert len(results) == 2
            for path in paths:
                assert path in results
        finally:
            for path in paths:
                os.unlink(path)

    def test_enrich_from_files_missing_identifier(self, file_enricher):
        """Test enriching from file without identifier."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"title": "No DOI or PMCID"}, f)
            f.flush()
            temp_path = f.name

        try:
            results = file_enricher.enrich_from_files([temp_path])
            assert "error" in results[temp_path]
            assert "No DOI or PMCID" in results[temp_path]["error"]
        finally:
            os.unlink(temp_path)

    def test_enrich_from_files_invalid_json(self, file_enricher):
        """Test enriching from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json content")
            f.flush()
            temp_path = f.name

        try:
            results = file_enricher.enrich_from_files([temp_path])
            assert "error" in results[temp_path]
        finally:
            os.unlink(temp_path)

    def test_enrich_from_files_empty_list(self, file_enricher):
        """Test enriching from empty list."""
        results = file_enricher.enrich_from_files([])
        assert results == {}

    def test_enrich_from_files_with_pmcid(self, file_enricher):
        """Test enriching using PMCID when DOI is missing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"pmcid": "PMC1234567", "title": "PMC Paper"}, f)
            f.flush()
            temp_path = f.name

        try:
            results = file_enricher.enrich_from_files([temp_path])
            assert temp_path in results
            assert "error" not in results[temp_path]
        finally:
            os.unlink(temp_path)

    def test_enrich_from_files_enricher_error(self, config):
        """Test enriching when enricher raises error."""
        with patch("pyeuropepmc.features.enrich.enricher.PaperEnricher") as MockPaperEnricher:
            mock_instance = MagicMock()
            mock_instance.enrich_paper.side_effect = ValueError("API Error")
            MockPaperEnricher.return_value = mock_instance
            enricher = FileEnricher(config)

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump({"doi": "10.1234/test"}, f)
                f.flush()
                temp_path = f.name

            try:
                results = enricher.enrich_from_files([temp_path])
                assert "error" in results[temp_path]
            finally:
                os.unlink(temp_path)

    def test_enrich_from_directory(self, file_enricher):
        """Test enriching from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a metadata file in the directory
            file_path = os.path.join(tmpdir, "paper1.json")
            with open(file_path, "w") as f:
                json.dump({"doi": "10.1234/test"}, f)

            results = file_enricher.enrich_from_directory(tmpdir)
            assert len(results) == 1
            assert file_path in results

    def test_enrich_from_directory_no_files(self, file_enricher):
        """Test enriching from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = file_enricher.enrich_from_directory(tmpdir)
            assert results == {}

    def test_enrich_from_directory_nonexistent(self, file_enricher):
        """Test enriching from nonexistent directory."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            file_enricher.enrich_from_directory("/nonexistent/path")

    def test_enrich_from_directory_recursive(self, file_enricher):
        """Test enriching from directory recursively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            file_path = os.path.join(subdir, "paper.json")
            with open(file_path, "w") as f:
                json.dump({"doi": "10.1234/test"}, f)

            # Non-recursive should find 0 files
            results_nonrec = file_enricher.enrich_from_directory(tmpdir, recursive=False)
            assert len(results_nonrec) == 0

            # Recursive should find 1 file
            results_rec = file_enricher.enrich_from_directory(tmpdir, recursive=True)
            assert len(results_rec) == 1

    def test_enrich_from_directory_custom_pattern(self, file_enricher):
        """Test enriching with custom pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "paper1.json"), "w") as f:
                json.dump({"doi": "10.1234/1"}, f)
            with open(os.path.join(tmpdir, "paper1.txt"), "w") as f:
                f.write("not json")

            results = file_enricher.enrich_from_directory(tmpdir, pattern="*.json")
            assert len(results) == 1

    def test_save_enriched_files(self, file_enricher):
        """Test saving enriched files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "paper1.json")
            with open(input_path, "w") as f:
                json.dump({"doi": "10.1234/test", "title": "Original"}, f)

            # Enrich first
            results = file_enricher.enrich_from_files([input_path])

            # Save to output directory
            output_dir = os.path.join(tmpdir, "output")
            saved = file_enricher.save_enriched_files(results, output_dir)
            assert len(saved) == 1
            assert os.path.exists(saved[0])
            assert "_enriched" in saved[0]

            # Verify saved content
            with open(saved[0]) as f:
                saved_data = json.load(f)
            assert saved_data["title"] == "Enriched Title"

    def test_save_enriched_files_no_overwrite(self, file_enricher):
        """Test saving without overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "paper1.json")
            with open(input_path, "w") as f:
                json.dump({"doi": "10.1234/test"}, f)

            results = file_enricher.enrich_from_files([input_path])

            output_dir = os.path.join(tmpdir, "output")
            # Save twice - second should skip
            saved1 = file_enricher.save_enriched_files(results, output_dir)
            saved2 = file_enricher.save_enriched_files(results, output_dir, overwrite=False)
            assert len(saved1) == 1
            assert len(saved2) == 0  # skipped

    def test_save_enriched_files_overwrite(self, file_enricher):
        """Test saving with overwrite enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "paper1.json")
            with open(input_path, "w") as f:
                json.dump({"doi": "10.1234/test"}, f)

            results = file_enricher.enrich_from_files([input_path])

            output_dir = os.path.join(tmpdir, "output")
            saved1 = file_enricher.save_enriched_files(results, output_dir)
            saved2 = file_enricher.save_enriched_files(results, output_dir, overwrite=True)
            assert len(saved1) == 1
            assert len(saved2) == 1  # overwritten

    def test_save_enriched_files_skips_errors(self, file_enricher):
        """Test saving skips files with errors."""
        results = {
            "/path/to/file.json": {"error": "Some error occurred"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            saved = file_enricher.save_enriched_files(results, tmpdir)
            assert saved == []

    def test_save_enriched_files_creates_output_dir(self, file_enricher):
        """Test that output directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "paper.json")
            with open(input_path, "w") as f:
                json.dump({"doi": "10.1234/test"}, f)

            results = file_enricher.enrich_from_files([input_path])
            output_dir = os.path.join(tmpdir, "new", "nested", "output")
            saved = file_enricher.save_enriched_files(results, output_dir)
            assert len(saved) == 1
            assert os.path.isdir(output_dir)

    def test_context_manager(self, config):
        """Test context manager protocol."""
        with patch("pyeuropepmc.features.enrich.enricher.PaperEnricher") as MockPaperEnricher:
            mock_instance = MagicMock()
            MockPaperEnricher.return_value = mock_instance

            with FileEnricher(config) as enricher:
                assert enricher is not None

            mock_instance.close.assert_called_once()

    def test_close(self, config):
        """Test close method."""
        with patch("pyeuropepmc.features.enrich.enricher.PaperEnricher") as MockPaperEnricher:
            mock_instance = MagicMock()
            MockPaperEnricher.return_value = mock_instance

            enricher = FileEnricher(config)
            enricher.close()
            mock_instance.close.assert_called_once()
