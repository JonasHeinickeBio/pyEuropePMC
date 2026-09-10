"""Unit tests for per-source query translation."""

from __future__ import annotations

import pytest

from pyeuropepmc.features.search.query_translation import translate_query


@pytest.mark.parametrize("source", ["europepmc", "pubmed", "clinicaltrials"])
def test_passthrough_sources_keep_field_syntax(source):
    q = 'TITLE:"gene editing" AND cancer'
    # passthrough sources may reformat via search-query but must not drop terms
    out = translate_query(q, source).lower()
    assert "gene editing" in out or "gene" in out
    assert "cancer" in out


def test_arxiv_wraps_free_text():
    assert translate_query("CRISPR AND cancer", "arxiv") == 'all:"CRISPR cancer"'


def test_arxiv_leaves_field_syntax_alone():
    assert translate_query("ti:transformer AND au:vaswani", "arxiv").startswith("ti:")


def test_freetext_sources_strip_operators_and_tags():
    out = translate_query('TITLE:"gene" AND cancer[tiab] OR tumour', "openalex")
    assert out == "gene cancer tumour"


def test_empty_query_returns_empty():
    assert translate_query("", "pubmed") == ""
    assert translate_query("   ", "openalex") == ""


def test_unknown_source_is_passthrough():
    assert translate_query("anything AND here", "not-a-source") == "anything AND here"
