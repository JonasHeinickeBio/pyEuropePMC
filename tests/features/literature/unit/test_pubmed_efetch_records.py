"""EFetch parsing checked against real PubMed records.

Every expectation is read from the record itself, in the places NCBI puts
the values:

* the record's identifiers are in <PubmedData><ArticleIdList>, a sibling of
  <MedlineCitation>. The DOI was looked for inside <MedlineCitation> and never
  found - 5 of 5 records came back without one - while the PMCID was looked
  for across the whole <PubmedArticle>, whose <ReferenceList> gives each
  cited work an <ArticleIdList> too. PMID 33093664, which has no PMCID,
  reported a reference's.
* <AbstractText> and <ArticleTitle> keep inline <i>, <b>, <sup> and <sub>,
  and reading `.text` stopped at the first of them.
* each <Author> can carry an ORCID <Identifier> and any number of
  <AffiliationInfo>; both were dropped.

The records are in tests/fixtures/pubmed_efetch; see the README there.
"""

from __future__ import annotations

import pathlib

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.literature.normalization import normalize_paper_title
from pyeuropepmc.features.search.sources.pubmed import PubMedClient

pytestmark = pytest.mark.unit

FIXTURES = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "pubmed_efetch"
RECORDS = sorted(FIXTURES.glob("PMID*.xml"))


def _text(element) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


@pytest.fixture(params=RECORDS, ids=[p.stem for p in RECORDS], scope="module")
def record(request):
    xml = request.param.read_text(encoding="utf-8")
    pmid = request.param.stem.removeprefix("PMID")
    article = DefusedET.fromstring(xml.encode("utf-8")).find("PubmedArticle")
    return article, PubMedClient()._parse_efetch_xml(xml, pmid)


def test_the_fixtures_are_there():
    """An empty glob would parametrize every test below away without a failure."""
    assert RECORDS, f"no EFetch records in {FIXTURES}"


class TestIdentifiers:
    def test_doi_is_the_records_own(self, record):
        article, result = record
        own = [
            e.text
            for e in article.findall("PubmedData/ArticleIdList/ArticleId")
            if e.get("IdType") == "doi"
        ]
        assert own, "every fixture has a DOI"
        assert result.doi == own[0].strip().lower()

    def test_pmcid_is_the_records_own_or_none(self, record):
        article, result = record
        own = [
            e.text
            for e in article.findall("PubmedData/ArticleIdList/ArticleId")
            if e.get("IdType") == "pmc"
        ]
        assert result.pmcid == (own[0].strip() if own else None)

    def test_a_references_pmcid_is_never_taken(self, record):
        article, result = record
        cited = {
            (e.text or "").strip()
            for e in article.findall("PubmedData/ReferenceList//ArticleId")
            if e.get("IdType") == "pmc"
        }
        own = {
            (e.text or "").strip()
            for e in article.findall("PubmedData/ArticleIdList/ArticleId")
            if e.get("IdType") == "pmc"
        }
        if not cited - own:
            pytest.skip("no cited PMCID that differs from the record's")
        assert result.pmcid not in cited - own


class TestText:
    def test_abstract_keeps_the_text_after_inline_markup(self, record):
        article, result = record
        for section in article.findall("MedlineCitation/Article/Abstract/AbstractText"):
            assert _text(section) in result.abstract

    def test_title_keeps_the_text_after_inline_markup(self, record):
        article, result = record
        title = _text(article.find("MedlineCitation/Article/ArticleTitle"))
        assert result.title == normalize_paper_title(title)


class TestAuthors:
    def test_orcids_are_kept(self, record):
        article, result = record
        authors = article.findall("MedlineCitation/Article/AuthorList/Author")
        expected = [_text(a.find("Identifier[@Source='ORCID']")) or None for a in authors]
        if not any(expected):
            pytest.skip("no ORCID in this record")
        got = [a.orcid for a in result.authors]
        assert [o.rsplit("/", 1)[-1] if o else None for o in expected] == got

    def test_every_affiliation_is_kept(self, record):
        article, result = record
        authors = article.findall("MedlineCitation/Article/AuthorList/Author")
        assert len(result.authors) == len(authors)
        for elem, author in zip(authors, result.authors, strict=True):
            for affiliation in elem.findall("AffiliationInfo/Affiliation"):
                assert _text(affiliation).rstrip(".") in (author.affiliation or "")


INLINE = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle>
  <MedlineCitation><Article>
    <ArticleTitle>Structure of the <i>Escherichia coli</i> LolCDE complex</ArticleTitle>
    <Abstract>
      <AbstractText Label="BACKGROUND">Levels of CO<sub>2</sub> rose.</AbstractText>
    </Abstract>
    <AuthorList>
      <Author><LastName>Lu</LastName><ForeName>Guangwen</ForeName>
        <Identifier Source="ORCID">not an orcid!</Identifier></Author>
    </AuthorList>
  </Article></MedlineCitation>
</PubmedArticle></PubmedArticleSet>"""


class TestEdgeCases:
    @pytest.fixture
    def result(self):
        return PubMedClient()._parse_efetch_xml(INLINE, "1")

    def test_inline_markup_in_the_title(self, result):
        assert result.title == "Structure of the Escherichia coli LolCDE complex"

    def test_inline_markup_in_a_labelled_section(self, result):
        assert result.abstract == "BACKGROUND: Levels of CO2 rose."

    def test_an_invalid_orcid_does_not_cost_the_author(self, result):
        assert [(a.name, a.orcid) for a in result.authors] == [("Lu, Guangwen", None)]
