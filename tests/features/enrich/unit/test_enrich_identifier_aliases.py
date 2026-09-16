"""Identifier keyword aliases, reports and saved responses of the enrichment layer.

Docstrings showed ``enricher.enrich_paper(doi=...)`` and ``client.enrich(doi=...)``;
both raised ValueError because the identifier parameter is ``identifier``.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.enrich.enricher import EnrichmentConfig, PaperEnricher
from pyeuropepmc.features.enrich.reporter import EnrichmentReporter
from pyeuropepmc.features.enrich.sources.crossref import CrossRefClient
from pyeuropepmc.features.enrich.sources.datacite import DataCiteClient
from pyeuropepmc.features.enrich.sources.icite import ICiteClient
from pyeuropepmc.features.enrich.sources.openalex import OpenAlexClient
from pyeuropepmc.features.enrich.sources.orcid import OrcidClient
from pyeuropepmc.features.enrich.sources.unpaywall import UnpaywallClient

DOI = "10.1371/journal.pone.0308090"

# conftest.py stubs ICiteClient.enrich for the whole directory; keep the real one.
_REAL_ICITE_ENRICH = ICiteClient.enrich


def _enricher_with(clients: dict[str, MagicMock]) -> PaperEnricher:
    config = EnrichmentConfig(
        enable_europepmc=False,
        enable_crossref=False,
        enable_semantic_scholar=False,
        enable_openalex=False,
        enable_icite=False,
        enable_ror=False,
    )
    enricher = PaperEnricher(config)
    enricher.clients = dict(clients)
    return enricher


class TestEnrichPaperAliases:
    @pytest.mark.parametrize(
        ("keyword", "value"),
        [("doi", DOI), ("pmid", "39116051"), ("pmcid", "PMC11308925")],
    )
    def test_keyword_alias_is_the_identifier(self, keyword, value):
        crossref = MagicMock()
        crossref.enrich.return_value = {"title": "T", "citation_count": 3}
        enricher = _enricher_with({"crossref": crossref})

        result = enricher.enrich_paper(**{keyword: value})

        assert result["identifier"] == value
        assert result["sources"] == ["crossref"]
        # the alias is consumed, not forwarded as an API parameter
        assert keyword not in crossref.enrich.call_args.kwargs

    def test_identifier_wins_over_alias(self):
        crossref = MagicMock()
        crossref.enrich.return_value = None
        enricher = _enricher_with({"crossref": crossref})

        result = enricher.enrich_paper(DOI, doi="10.9999/other")

        assert result["identifier"] == DOI

    def test_no_identifier_still_raises(self):
        with pytest.raises(ValueError, match="identifier"):
            _enricher_with({}).enrich_paper()

    def test_docstring_example_form(self):
        """The class docstring's call and result access work as written."""
        crossref = MagicMock()
        crossref.enrich.return_value = {"citation_count": 7}
        enricher = _enricher_with({"crossref": crossref})

        enriched = enricher.enrich_paper("10.1371/journal.pone.0123456")

        assert enriched.get("sources") == ["crossref"]
        assert enriched["merged"].get("citation_count") == 7


class TestClientEnrichAliases:
    @pytest.mark.parametrize(
        ("client_cls", "kwargs", "keyword"),
        [
            (CrossRefClient, {}, "doi"),
            (UnpaywallClient, {"email": "you@example.org"}, "doi"),
            (DataCiteClient, {}, "doi"),
            (OpenAlexClient, {"enable_ror_enrichment": False}, "doi"),
            (ICiteClient, {}, "pmid"),
            (OrcidClient, {}, "orcid"),
        ],
    )
    def test_alias_reaches_the_request(self, client_cls, kwargs, keyword, monkeypatch):
        monkeypatch.setattr(ICiteClient, "enrich", _REAL_ICITE_ENRICH)
        client = client_cls(rate_limit_delay=0, **kwargs)
        value = {"doi": DOI, "pmid": "39116051", "orcid": "0000-0002-1825-0097"}[keyword]
        with patch.object(client, "_make_request", return_value=None) as request:
            client.enrich(**{keyword: value})  # must not raise ValueError

        assert request.called
        sent = json.dumps([request.call_args.args, request.call_args.kwargs], default=str)
        assert value.split("/")[-1] in sent

    @pytest.mark.parametrize(
        ("client_cls", "kwargs"),
        [
            (CrossRefClient, {}),
            (UnpaywallClient, {"email": "you@example.org"}),
            (DataCiteClient, {}),
        ],
    )
    def test_missing_identifier_still_raises(self, client_cls, kwargs):
        with pytest.raises(ValueError, match="Identifier is required"):
            client_cls(rate_limit_delay=0, **kwargs).enrich()

    def test_semantic_scholar_doi_alias(self):
        pytest.importorskip("semanticscholar")
        from pyeuropepmc.features.enrich.sources.semantic_scholar import SemanticScholarClient

        client = SemanticScholarClient(rate_limit_delay=0)
        client._pro_client = MagicMock()
        client._pro_client.get_paper.return_value = {"title": "T"}

        assert client.enrich(doi=DOI) == {"title": "T"}
        assert client._pro_client.get_paper.call_args.kwargs["paper_id"] == DOI


class TestReportJournal:
    def test_string_journal_does_not_raise(self):
        """Europe PMC supplies the journal as a string in the default configuration."""
        report = EnrichmentReporter().generate_report(
            {
                "identifier": DOI,
                "doi": DOI,
                "sources": ["europepmc"],
                "merged": {"journal": "PLoS One"},
            }
        )
        assert "Journal: PLoS One" in report

    def test_dict_journal(self):
        report = EnrichmentReporter().generate_report(
            {"sources": ["crossref"], "merged": {"journal": {"name": "PLoS One"}}}
        )
        assert "Journal: PLoS One" in report

    def test_enricher_report_with_string_journal(self):
        enricher = _enricher_with({})
        report = enricher.generate_enrichment_report(
            {
                "identifier": DOI,
                "doi": DOI,
                "sources": ["europepmc"],
                "merged": {"journal": "PLoS One"},
            }
        )
        assert "Journal: PLoS One" in report


class TestSaveResponsesWithoutDoi:
    def test_files_are_named_after_the_identifier(self, tmp_path):
        enricher = _enricher_with({})
        results = {
            "identifier": "PMC11308925",
            "doi": None,
            "pmid": "39116051",
            "sources": ["icite"],
            "icite": {"pmid": "39116051", "rcr": 1.2},
            "merged": {"citation_count": 4},
        }

        enricher._save_responses(results, save_dir=tmp_path)

        names = sorted(p.name for p in Path(tmp_path).iterdir())
        assert names == ["merged_PMC11308925.json", "raw_icite_PMC11308925.json"]
        assert json.loads((tmp_path / "merged_PMC11308925.json").read_text())["merged"] == {
            "citation_count": 4
        }

    def test_enrich_paper_saves_when_no_doi_resolved(self, tmp_path):
        icite = MagicMock()
        icite.enrich.return_value = {"pmid": "39116051", "rcr": 1.2}
        enricher = _enricher_with({"icite": icite})

        enricher.enrich_paper("39116051", save_responses=True, save_dir=tmp_path)

        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "merged_39116051.json",
            "raw_icite_39116051.json",
        ]

    def test_doi_filename_is_unchanged(self, tmp_path):
        enricher = _enricher_with({})
        enricher._save_responses(
            {"identifier": DOI, "doi": DOI, "sources": [], "merged": {}}, save_dir=tmp_path
        )
        assert [p.name for p in tmp_path.iterdir()] == ["merged_10_1371_journal_pone_0308090.json"]
