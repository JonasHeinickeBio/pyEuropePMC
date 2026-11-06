"""PMCID -> DOI lookup (hermetic)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient

ARTICLE = "pyeuropepmc.features.literature.article.ArticleClient"


def _lookup(details):
    article_client = MagicMock()
    article_client.get_article_details.return_value = details
    with patch(ARTICLE, return_value=article_client):
        doi = FullTextClient(enable_cache=False)._lookup_doi_for_pmcid("3525259")
    return doi, article_client


def test_europe_pmc_is_asked_with_the_prefixed_id():
    """Europe PMC's id for a PMC article is ``PMC3525259``; ``3525259`` finds nothing."""
    doi, article_client = _lookup({"result": {"doi": "10.1186/1479-7364-2-2-138"}})
    assert doi == "10.1186/1479-7364-2-2-138"
    assert article_client.get_article_details.call_args[0][:2] == ("PMC", "PMC3525259")
    article_client.close.assert_called_once()


def test_an_article_without_a_doi_gives_none():
    assert _lookup({"result": {}})[0] is None
    assert _lookup({"hitCount": 0, "result": None})[0] is None


def test_a_failed_request_gives_none_not_an_error():
    article_client = MagicMock()
    article_client.get_article_details.side_effect = RuntimeError("down")
    with patch(ARTICLE, return_value=article_client):
        assert FullTextClient(enable_cache=False)._lookup_doi_for_pmcid("1") is None
    article_client.close.assert_called_once()
