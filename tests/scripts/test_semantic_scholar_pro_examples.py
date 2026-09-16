"""Run the examples/11-semantic-scholar-pro scripts against a mocked library.

The scripts imported ProfessionalSemanticScholarClient from a package that does
not export it and read typed attributes (``paper.title``, ``author.i10_index``,
``client.get_venue``) from the dicts the client returns. Each ``main()`` runs
here end to end with the ``semanticscholar`` client replaced by a stub that
returns the library's real ``Paper`` and ``Author`` objects.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("semanticscholar")

from semanticscholar.Author import Author  # noqa: E402
from semanticscholar.Paper import Paper  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "11-semantic-scholar-pro"

PAPER = {
    "paperId": "2b5a3b2c",
    "title": "Nanometre-scale thermometry in a living cell",
    "year": 2013,
    "citationCount": 1500,
    "influentialCitationCount": 40,
    "externalIds": {"DOI": "10.1038/nature12373"},
    "authors": [{"authorId": "1724609", "name": "G. Kucsko"}],
    "journal": {"name": "Nature", "volume": "500", "pages": "54-58"},
    "venue": "Nature",
    "fieldsOfStudy": ["Physics", "Medicine"],
    "openAccessPdf": {"url": "https://example.org/paper.pdf"},
}
AUTHOR = {
    "authorId": "1724609",
    "name": "G. Kucsko",
    "paperCount": 30,
    "citationCount": 4000,
    "hIndex": 20,
}


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"s2pro_example_{name}", EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def stub_library():
    library = MagicMock()
    library.get_paper.return_value = Paper(PAPER)
    library.get_author.return_value = Author(AUTHOR)
    library.search_paper.return_value = [Paper({**PAPER, "paperId": f"p{i}"}) for i in range(5)]
    with (
        patch("semanticscholar.SemanticScholar", return_value=library),
        patch("pyeuropepmc.features.enrich.sources.semanticscholar_pro.time.sleep"),
    ):
        yield library


@pytest.mark.parametrize("name", ["typed_responses", "bulk_search", "rate_limiting"])
def test_example_runs(name, stub_library, capsys):
    _load(name).main()
    out = capsys.readouterr().out
    assert "Traceback" not in out
    assert stub_library.get_paper.called or stub_library.search_paper.called


def test_typed_responses_prints_real_values(stub_library, capsys):
    _load("typed_responses").main()
    out = capsys.readouterr().out
    assert "Title: Nanometre-scale thermometry in a living cell" in out
    assert "DOI: 10.1038/nature12373" in out
    assert "H-index: 20" in out


def test_bulk_search_uses_semantic_scholar_type_names(stub_library):
    _load("bulk_search").main()
    publication_types = [
        call.kwargs.get("publication_types") for call in stub_library.search_paper.call_args_list
    ]
    assert ["JournalArticle"] in publication_types


def test_integration_example_runs(capsys):
    module = _load("integration")
    enricher = MagicMock()
    enricher.__enter__.return_value = enricher
    enricher.enrich_paper.return_value = {
        "identifier": "10.1038/nature12373",
        "doi": "10.1038/nature12373",
        "pmid": None,
        "sources": ["crossref", "semantic_scholar"],
        "crossref": {"title": "Nanometre-scale thermometry", "citation_count": 1400},
        "semantic_scholar": {"title": "Nanometre-scale thermometry", "citation_count": 1500},
        "openalex": None,
        "unpaywall": None,
        "merged": {
            "title": "Nanometre-scale thermometry",
            "authors": [{"name": "G. Kucsko"}],
            "journal": "Nature",
            "publication_year": 2013,
            "citation_count": 1500,
            "oa_status": "green",
            "oa_url": None,
            "fields_of_study": ["Physics"],
        },
    }
    with (
        patch.object(module, "PaperEnricher", return_value=enricher),
        patch.object(module, "EnrichmentConfig"),
    ):
        module.main()

    out = capsys.readouterr().out
    assert "Journal: Nature" in out
    assert "Authors: G. Kucsko" in out
    assert "OA Status: green" in out
