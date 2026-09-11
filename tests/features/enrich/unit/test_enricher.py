"""Unit tests for paper enrichment orchestrator."""

from unittest.mock import Mock, patch

import pytest

from pyeuropepmc.features.enrich.enricher import EnrichmentConfig, PaperEnricher


class TestEnrichmentConfig:
    """Tests for EnrichmentConfig."""

    def test_default_configuration(self):
        """Test default configuration."""
        config = EnrichmentConfig()
        assert config.enable_crossref is True
        assert config.enable_unpaywall is False
        assert config.enable_semantic_scholar is True
        assert config.enable_openalex is True

    def test_unpaywall_requires_email(self, monkeypatch):
        """Test that enabling Unpaywall without email raises ValueError."""
        monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
        with pytest.raises(ValueError, match="unpaywall_email is required"):
            EnrichmentConfig(enable_unpaywall=True)

    def test_unpaywall_with_email(self):
        """Test enabling Unpaywall with email."""
        config = EnrichmentConfig(
            enable_unpaywall=True,
            unpaywall_email="test@example.com",
        )
        assert config.enable_unpaywall is True
        assert config.unpaywall_email == "test@example.com"

    def test_custom_rate_limit(self):
        """Test custom rate limit configuration."""
        config = EnrichmentConfig(rate_limit_delay=2.0)
        assert config.rate_limit_delay == 2.0


class TestPaperEnricher:
    """Tests for PaperEnricher."""

    def test_initialization_default_config(self):
        """Test initialization with default configuration."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Europe PMC is the base; CrossRef / S2 / OpenAlex / iCite top it up
        assert "europepmc" in enricher.clients
        assert "crossref" in enricher.clients
        assert "semantic_scholar" in enricher.clients
        assert "openalex" in enricher.clients
        assert "icite" in enricher.clients
        assert "unpaywall" not in enricher.clients

    def test_initialization_all_clients(self):
        """Test initialization with all clients enabled."""
        config = EnrichmentConfig(
            enable_crossref=True,
            enable_unpaywall=True,
            enable_semantic_scholar=True,
            enable_openalex=True,
            unpaywall_email="test@example.com",
        )
        enricher = PaperEnricher(config)

        # europepmc, crossref, unpaywall, semantic_scholar, openalex, icite, ror
        assert len(enricher.clients) == 7
        assert "europepmc" in enricher.clients
        assert "crossref" in enricher.clients
        assert "unpaywall" in enricher.clients
        assert "semantic_scholar" in enricher.clients
        assert "openalex" in enricher.clients
        assert "icite" in enricher.clients
        assert "ror" in enricher.clients  # ROR is enabled by default

    def test_context_manager(self):
        """Test context manager protocol."""
        config = EnrichmentConfig()
        with PaperEnricher(config) as enricher:
            assert len(enricher.clients) > 0

    def test_enrich_without_doi_raises(self):
        """Test that enrich without DOI raises ValueError."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        with pytest.raises(ValueError, match="identifier .* is required"):
            enricher.enrich_paper()

    @patch("pyeuropepmc.features.enrich.sources.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.features.enrich.sources.semantic_scholar.SemanticScholarClient.enrich")
    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient.enrich")
    def test_enrich_paper_success(self, mock_openalex, mock_semantic, mock_crossref):
        """Test successful paper enrichment."""
        # Mock responses from each client
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test Article",
            "citation_count": 42,
        }
        mock_semantic.return_value = {
            "source": "semantic_scholar",
            "citation_count": 40,
            "influential_citation_count": 5,
        }
        mock_openalex.return_value = {
            "source": "openalex",
            "citation_count": 45,
            "is_oa": True,
        }

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result is not None
        assert result["doi"] == "10.1234/test"
        assert len(result["sources"]) == 3
        assert "crossref" in result["sources"]
        assert "semantic_scholar" in result["sources"]
        assert "openalex" in result["sources"]
        assert result["crossref"]["title"] == "Test Article"
        assert result["merged"] is not None

    @patch("pyeuropepmc.features.enrich.sources.crossref.CrossRefClient.enrich")
    def test_enrich_paper_partial_failure(self, mock_crossref):
        """Test enrichment when some clients fail."""
        # CrossRef succeeds
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test Article",
        }

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Mock other clients to return None
        with patch.object(enricher.clients["semantic_scholar"], "enrich", return_value=None):
            with patch.object(enricher.clients["openalex"], "enrich", return_value=None):
                result = enricher.enrich_paper(identifier="10.1234/test")

                assert result is not None
                assert len(result["sources"]) == 1
                assert "crossref" in result["sources"]

    def test_enrich_paper_all_failures(self):
        """Test enrichment when all clients fail."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)

        # Mock all clients to return None
        for client in enricher.clients.values():
            client.enrich = Mock(return_value=None)

        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result is not None
        assert len(result["sources"]) == 0
        assert result["merged"] == {}

    @patch("pyeuropepmc.features.enrich.sources.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.features.enrich.sources.semantic_scholar.SemanticScholarClient.enrich")
    def test_merge_results_citation_count(self, mock_semantic, mock_crossref):
        """Test merging of citation counts from multiple sources."""
        mock_crossref.return_value = {
            "source": "crossref",
            "citation_count": 42,
        }
        mock_semantic.return_value = {
            "source": "semantic_scholar",
            "citation_count": 40,
        }

        config = EnrichmentConfig(enable_openalex=False)
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        # Should use the maximum citation count
        assert result["merged"]["citation_count"] == 42
        assert len(result["merged"]["citation_counts"]) == 2

    @patch("pyeuropepmc.features.enrich.sources.crossref.CrossRefClient.enrich")
    @patch("pyeuropepmc.features.enrich.sources.openalex.OpenAlexClient.enrich")
    def test_merge_results_oa_status(self, mock_openalex, mock_crossref):
        """Test merging of OA status."""
        mock_crossref.return_value = {
            "source": "crossref",
            "title": "Test",
        }
        mock_openalex.return_value = {
            "source": "openalex",
            "is_oa": True,
            "oa_status": "gold",
            "oa_url": "https://example.com/paper.pdf",
        }

        config = EnrichmentConfig(enable_semantic_scholar=False)
        enricher = PaperEnricher(config)
        result = enricher.enrich_paper(identifier="10.1234/test")

        assert result["merged"]["is_oa"] is True
        assert result["merged"]["oa_status"] == "gold"
        assert result["merged"]["oa_url"] == "https://example.com/paper.pdf"

    # --- _resolve_ids tests ---

    def test_resolve_ids_doi_url(self):
        """A doi.org URL is recognized and the DOI is extracted."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("https://doi.org/10.1234/test")
        assert out["doi"] == "10.1234/test"

    def test_resolve_ids_dx_doi_url(self):
        """The dx.doi.org subdomain is also recognized."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("http://dx.doi.org/10.1234/test")
        assert out["doi"] == "10.1234/test"

    def test_resolve_ids_spoofed_host_not_treated_as_doi_url(self):
        """A URL that merely contains the substring 'doi.org/' in its path
        (e.g. hosted on an unrelated domain) must not be mistaken for a real
        doi.org URL - only the actual host is authoritative."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("https://evil.example/doi.org/10.1234/fake")
        assert out["doi"] is None

    def test_resolve_ids_lookalike_host_not_treated_as_doi_url(self):
        """A host like doi.org.evil.example must not match doi.org."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("https://doi.org.evil.example/10.1234/fake")
        assert out["doi"] is None

    def test_resolve_ids_bare_doi(self):
        """A bare DOI (10.xxxx/...) is recognized directly."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("10.1234/test")
        assert out["doi"] == "10.1234/test"

    def test_resolve_ids_pmcid(self):
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("PMC123456")
        assert out["pmcid"] == "PMC123456"

    def test_resolve_ids_pmid(self):
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        out = enricher._resolve_ids("123456")
        assert out["pmid"] == "123456"

    def test_resolve_ids_search_exception_is_swallowed(self):
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with patch(
            "pyeuropepmc.features.enrich.enricher.SearchClient",
            side_effect=RuntimeError("boom"),
        ):
            out = enricher._resolve_ids("10.1234/test")
        assert out["doi"] == "10.1234/test"

    def test_close(self):
        """Test close method."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        # Should not raise
        enricher.close()

    # --- _resolve_to_doi tests ---

    def test_resolve_to_doi_doi_url(self):
        """Test DOI URL extraction."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        doi = enricher._resolve_to_doi("https://doi.org/10.1234/test")
        assert doi == "10.1234/test"

    def test_resolve_to_doi_already_doi(self):
        """Test identifier already a DOI returns as-is."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        doi = enricher._resolve_to_doi("10.1234/test")
        assert doi == "10.1234/test"

    @patch("pyeuropepmc.features.enrich.enricher.SearchClient")
    def test_resolve_to_doi_pmcid(self, mock_search_client):
        """Test PMCID resolution to DOI via SearchClient."""
        mock_instance = mock_search_client.return_value.__enter__.return_value
        mock_instance.search.return_value = {
            "resultList": {"result": [{"doi": "10.1234/test"}]}
        }
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        doi = enricher._resolve_to_doi("PMC123456")
        assert doi == "10.1234/test"
        mock_instance.search.assert_called_once_with(query="PMCID:PMC123456", limit=1)

    def test_resolve_to_doi_invalid_raises(self):
        """Test invalid identifier raises ValueError."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with pytest.raises(ValueError, match="Invalid identifier"):
            enricher._resolve_to_doi("invalid")

    @patch("pyeuropepmc.features.enrich.enricher.SearchClient")
    def test_resolve_to_doi_pmcid_no_results(self, mock_search_client):
        """Test PMCID with no search results raises ValueError."""
        mock_instance = mock_search_client.return_value.__enter__.return_value
        mock_instance.search.return_value = {
            "resultList": {"result": []}
        }
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with pytest.raises(ValueError, match="Could not resolve PMCID"):
            enricher._resolve_to_doi("PMC999999")

    @patch("pyeuropepmc.features.enrich.enricher.SearchClient")
    def test_resolve_to_doi_pmcid_no_doi_in_result(self, mock_search_client):
        """Test PMCID result without DOI field raises ValueError."""
        mock_instance = mock_search_client.return_value.__enter__.return_value
        mock_instance.search.return_value = {
            "resultList": {"result": [{"pmcid": "PMC123456"}]}
        }
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with pytest.raises(ValueError, match="Could not resolve PMCID"):
            enricher._resolve_to_doi("PMC123456")

    # --- enrich convenience method tests ---

    def test_enrich_with_single_paper(self):
        """Test enrich with single paper list delegates to enrich_paper."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        papers = [{"doi": "10.1234/test"}]
        with patch.object(enricher, "enrich_paper", return_value={"doi": "10.1234/test"}) as mock_enrich:
            result = enricher.enrich(papers=papers)
            mock_enrich.assert_called_once_with(identifier="10.1234/test")
            assert result == {"doi": "10.1234/test"}

    def test_enrich_with_single_paper_pmcid(self):
        """Test enrich with single paper using PMCID."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        papers = [{"pmcid": "PMC123456"}]
        with patch.object(enricher, "enrich_paper", return_value={"doi": "10.1234/test"}) as mock_enrich:
            result = enricher.enrich(papers=papers)
            mock_enrich.assert_called_once_with(identifier="PMC123456")

    def test_enrich_with_multiple_papers(self):
        """Test enrich with multiple papers delegates to enrich_papers_batch."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        papers = [{"doi": "10.1234/a"}, {"doi": "10.1234/b"}]
        expected = {"10.1234/a": {}, "10.1234/b": {}}
        with patch.object(enricher, "enrich_papers_batch", return_value=expected) as mock_batch:
            result = enricher.enrich(papers=papers)
            mock_batch.assert_called_once_with(["10.1234/a", "10.1234/b"])
            assert result == expected

    def test_enrich_with_identifier_kwarg(self):
        """Test enrich with identifier kwarg delegates to enrich_paper."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with patch.object(enricher, "enrich_paper", return_value={"doi": "10.1234/test"}) as mock_enrich:
            result = enricher.enrich(identifier="10.1234/test")
            mock_enrich.assert_called_once_with(identifier="10.1234/test")
            assert result == {"doi": "10.1234/test"}

    def test_enrich_without_papers_or_identifier_raises(self):
        """Test enrich without papers or identifier raises ValueError."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        with pytest.raises(ValueError, match="Either papers list or identifier required"):
            enricher.enrich()

    # --- enrich_papers_batch tests ---

    @patch("pyeuropepmc.features.enrich.enricher.BatchEnricher")
    def test_enrich_papers_batch(self, mock_batch_cls):
        """Test batch enrichment delegates to BatchEnricher."""
        mock_instance = mock_batch_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        expected = {"10.1234/a": {"doi": "10.1234/a"}}
        mock_instance.enrich_papers_with_progress.return_value = expected

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        identifiers = ["10.1234/a"]
        result = enricher.enrich_papers_batch(identifiers)
        mock_batch_cls.assert_called_once_with(config)
        mock_instance.enrich_papers_with_progress.assert_called_once_with(
            identifiers, save_responses=True, save_dir=None
        )
        assert result == expected

    # --- enrich_from_metadata_files tests ---

    @patch("pyeuropepmc.features.enrich.enricher.FileEnricher")
    def test_enrich_from_metadata_files(self, mock_file_cls):
        """Test file-based enrichment delegates to FileEnricher."""
        mock_instance = mock_file_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        expected = {"file1.json": {"doi": "10.1234/test"}}
        mock_instance.enrich_from_files.return_value = expected

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        result = enricher.enrich_from_metadata_files(["file1.json"])
        mock_file_cls.assert_called_once_with(config)
        mock_instance.enrich_from_files.assert_called_once_with(["file1.json"])
        assert result == expected

    def test_enrich_from_metadata_files_with_path_objects(self):
        """Test file-based enrichment with Path objects."""
        from pathlib import Path
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        paths = [Path("file1.json"), Path("file2.json")]
        with patch.object(enricher, "enrich_from_metadata_files", wraps=enricher.enrich_from_metadata_files) as spy:
            with patch("pyeuropepmc.features.enrich.enricher.FileEnricher") as mock_file_cls:
                mock_instance = mock_file_cls.return_value
                mock_instance.__enter__.return_value = mock_instance
                mock_instance.enrich_from_files.return_value = {}
                enricher.enrich_from_metadata_files(paths)
                mock_instance.enrich_from_files.assert_called_once_with(["file1.json", "file2.json"])

    # --- generate_enrichment_report tests ---

    def test_generate_enrichment_report(self):
        """Test report generation delegates to EnrichmentReporter."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        enricher.reporter.generate_report = Mock(return_value="Generated report")
        result = enricher.generate_enrichment_report({"doi": "10.1234/test"})
        assert result == "Generated report"

    def test_generate_enrichment_report_empty(self):
        """Test report generation with empty result."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        enricher.reporter.generate_report = Mock(return_value="No data")
        result = enricher.generate_enrichment_report({})
        assert result == "No data"

    # --- _enrich_institutions_with_ror tests ---

    def test_enrich_institutions_with_ror(self):
        """Test ROR enrichment of author institutions."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        mock_ror = Mock()
        mock_ror._normalize_ror_id.return_value = "012345678"
        mock_ror.enrich.return_value = {"name": "Test University", "country": "US"}
        enricher.clients["ror"] = mock_ror

        merged_data = {
            "authors": [
                {
                    "institutions": [
                        {"ror_id": "012345678", "display_name": "Test Univ"}
                    ]
                }
            ]
        }
        result = enricher._enrich_institutions_with_ror(merged_data)
        assert "012345678" in result
        assert result["012345678"]["name"] == "Test University"
        mock_ror.enrich.assert_called_once_with(identifier="012345678")

    def test_enrich_institutions_with_ror_skips_already_enriched(self):
        """Test ROR enrichment skips already enriched institutions."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        mock_ror = Mock()
        enricher.clients["ror"] = mock_ror

        merged_data = {
            "authors": [
                {
                    "institutions": [
                        {"ror_id": "012345678", "display_name": "Test Univ", "ror_enriched": True}
                    ]
                }
            ]
        }
        result = enricher._enrich_institutions_with_ror(merged_data)
        assert result == {}
        mock_ror.enrich.assert_not_called()

    def test_enrich_institutions_with_ror_no_ror_ids(self):
        """Test ROR enrichment when no ROR IDs exist."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        mock_ror = Mock()
        enricher.clients["ror"] = mock_ror

        merged_data = {"authors": [{"institutions": [{"display_name": "Test Univ"}]}]}
        result = enricher._enrich_institutions_with_ror(merged_data)
        assert result == {}
        mock_ror.enrich.assert_not_called()

    def test_enrich_institutions_with_ror_no_client(self):
        """Test ROR enrichment returns empty dict when no ROR client."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        if "ror" in enricher.clients:
            del enricher.clients["ror"]
        result = enricher._enrich_institutions_with_ror({"authors": []})
        assert result == {}

    def test_enrich_institutions_with_ror_client_enrich_fails(self):
        """Test ROR enrichment handles client enrichment failure gracefully."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        mock_ror = Mock()
        mock_ror._normalize_ror_id.return_value = "012345678"
        mock_ror.enrich.return_value = None
        enricher.clients["ror"] = mock_ror

        merged_data = {
            "authors": [
                {
                    "institutions": [
                        {"ror_id": "012345678", "display_name": "Test Univ"}
                    ]
                }
            ]
        }
        result = enricher._enrich_institutions_with_ror(merged_data)
        assert result == {}

    # --- _save_responses tests ---

    def test_save_responses_creates_files(self):
        """Test _save_responses writes JSON files to disk."""
        import tempfile
        from pathlib import Path

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        results = {
            "identifier": "10.1234/test",
            "doi": "10.1234/test",
            "sources": ["crossref"],
            "crossref": {"source": "crossref", "title": "Test Article"},
            "merged": {"citation_count": 42},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            enricher._save_responses(results, save_dir=tmp_dir)
            saved_files = list(Path(tmp_dir).iterdir())
            # Should create raw_crossref_* and merged_* files
            assert len(saved_files) == 2
            filenames = [f.name for f in saved_files]
            assert any("raw_crossref" in f for f in filenames)
            assert any("merged" in f for f in filenames)

    def test_save_responses_creates_directory(self):
        """Test _save_responses creates the save directory if needed."""
        import tempfile
        from pathlib import Path

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        results = {
            "identifier": "10.1234/test",
            "doi": "10.1234/test",
            "sources": [],
            "merged": {},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            new_dir = Path(tmp_dir) / "new_subdir"
            enricher._save_responses(results, save_dir=str(new_dir))
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_save_responses_default_directory(self):
        """Test _save_responses uses default directory when save_dir is None."""
        from pathlib import Path

        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        results = {
            "identifier": "10.1234/test",
            "doi": "10.1234/test",
            "sources": [],
            "merged": {},
        }
        with patch.object(Path, "mkdir") as mock_mkdir:
            with patch("builtins.open", Mock()):
                enricher._save_responses(results, save_dir=None)
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # --- close with client errors ---

    def test_close_with_client_errors(self):
        """Test close handles client errors gracefully."""
        config = EnrichmentConfig()
        enricher = PaperEnricher(config)
        bad_client = Mock()
        bad_client.close.side_effect = RuntimeError("Connection error")
        enricher.clients["bad"] = bad_client
        # Should not raise
        enricher.close()
        bad_client.close.assert_called_once()
