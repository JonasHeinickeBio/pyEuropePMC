from unittest.mock import MagicMock, patch

from pyeuropepmc.features.bibliography.models import Reference
from pyeuropepmc.features.bibliography.reference import (
    IdentifierType,
    ReferenceResolver,
    detect_identifier_type,
)


class TestDetectIdentifierType:
    def test_doi(self):
        assert detect_identifier_type("10.1038/nature14539") == IdentifierType.DOI

    def test_pmid(self):
        assert detect_identifier_type("25686660") == IdentifierType.PMID

    def test_pmcid(self):
        assert detect_identifier_type("PMC123456") == IdentifierType.PMCID

    def test_arxiv(self):
        assert detect_identifier_type("2301.12345") == IdentifierType.ARXIV
        assert detect_identifier_type("arXiv:2301.12345") == IdentifierType.ARXIV

    def test_unknown(self):
        assert detect_identifier_type("not-an-id") == IdentifierType.UNKNOWN


class TestReferenceResolver:
    @patch("pyeuropepmc.features.bibliography.reference.ReferenceResolver._resolve_via_crossref")
    def test_resolve_doi(self, mock_crossref):
        mock_ref = Reference(
            title="Test Paper", doi="10.1234/test", authors=["Smith, J"], source="crossref"
        )
        mock_crossref.return_value = mock_ref
        resolver = ReferenceResolver()
        result = resolver.resolve_doi("10.1234/test")
        assert result is not None
        assert result.title == "Test Paper"
        assert result.doi == "10.1234/test"

    @patch("pyeuropepmc.features.bibliography.reference.ReferenceResolver._get_search_client")
    def test_resolve_pmid(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.search.return_value = {
            "results": [
                {
                    "title": "PM Paper",
                    "doi": "10.1234/b",
                    "pmid": "12345678",
                    "pubYear": "2020",
                    "journalTitle": "J",
                    "authorString": "Doe, J",
                }
            ]
        }
        resolver = ReferenceResolver()
        result = resolver.resolve_pmid("12345678")
        assert result is not None
        assert result.title == "PM Paper"
        assert result.source == "europe_pmc"

    @patch("pyeuropepmc.features.bibliography.reference.ReferenceResolver._resolve_via_pmc")
    @patch("pyeuropepmc.features.bibliography.reference.ReferenceResolver._resolve_via_crossref")
    def test_resolve_arxiv(self, mock_crossref, mock_pmc):
        # Europe PMC has nothing -> falls back to the CrossRef arXiv DOI.
        mock_pmc.return_value = None
        mock_ref = Reference(
            title="ArXiv Paper", doi="10.48550/arXiv.2301.12345", source="crossref"
        )
        mock_crossref.return_value = mock_ref
        resolver = ReferenceResolver()
        result = resolver.resolve_arxiv("2301.12345")
        assert result is not None
        assert result.title == "ArXiv Paper"
        mock_crossref.assert_called_once_with("10.48550/arxiv.2301.12345")

    def test_resolve_many(self):
        resolver = ReferenceResolver()
        with (
            patch.object(
                resolver,
                "resolve_doi",
                return_value=Reference(title="Paper A", doi="10.1234/a", source="crossref"),
            ),
            patch.object(
                resolver,
                "resolve_pmid",
                return_value=Reference(title="Paper B", pmid="99999", source="europe_pmc"),
            ),
        ):
            ids = ["10.1234/a", "99999"]
            results = resolver.resolve_many(ids)
            assert len(results) == 2

    def test_resolve_invalid_doi_returns_none(self):
        resolver = ReferenceResolver()
        with (
            patch.object(resolver, "_resolve_via_crossref", return_value=None),
            patch.object(resolver, "_resolve_via_pmc", return_value=None),
        ):
            result = resolver.resolve_doi("10.0000/invalid")
            assert result is None

    def test_resolve_invalid_pmid_returns_none(self):
        resolver = ReferenceResolver()
        with patch.object(resolver, "_resolve_via_pmc", return_value=None):
            result = resolver.resolve_pmid("00000000")
            assert result is None

    def test_resolve_auto_detect(self):
        resolver = ReferenceResolver()
        with patch.object(
            resolver, "resolve_doi", return_value=Reference(doi="10.1234/x", source="crossref")
        ) as mock_doi:
            result = resolver.resolve("10.1234/x")
            mock_doi.assert_called_once()
            assert result is not None

    def test_resolve_unknown_type_returns_none(self):
        resolver = ReferenceResolver()
        result = resolver.resolve("???")
        assert result is None
