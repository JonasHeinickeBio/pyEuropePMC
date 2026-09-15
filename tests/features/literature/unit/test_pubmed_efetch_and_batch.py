"""Coverage for PubMedClient's EFetch XML parsing, batch retrieval, and
ECitMatch citation lookup — the parts test_pubmed_client.py doesn't reach.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.search.sources.pubmed import PubMedClient

pytestmark = pytest.mark.unit

FULL_EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>A Study of CRISPR Editing</ArticleTitle>
        <Journal>
          <Title>Journal of Gene Editing</Title>
          <ISOAbbreviation>J Gene Edit</ISOAbbreviation>
          <JournalIssue>
            <PubDate><Year>2022</Year></PubDate>
          </JournalIssue>
        </Journal>
      </Article>
      <AuthorList>
        <Author><LastName>Smith</LastName><ForeName>Jane</ForeName></Author>
        <Author><LastName>Doe</LastName></Author>
      </AuthorList>
      <Abstract>
        <AbstractText Label="BACKGROUND">CRISPR is powerful.</AbstractText>
        <AbstractText Label="RESULTS">It worked well.</AbstractText>
      </Abstract>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Gene Editing</DescriptorName></MeshHeading>
        <MeshHeading><DescriptorName>CRISPR-Cas Systems</DescriptorName></MeshHeading>
      </MeshHeadingList>
      <PublicationTypeList>
        <PublicationType>Journal Article</PublicationType>
      </PublicationTypeList>
      <KeywordList>
        <Keyword>gene editing</Keyword>
        <Keyword>CRISPR</Keyword>
      </KeywordList>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/CRISPR.2022</ArticleId>
      </ArticleIdList>
      <GrantList>
        <Grant>
          <GrantID>R01-12345</GrantID>
          <Acronym>NIH</Acronym>
          <Agency>National Institutes of Health</Agency>
        </Grant>
      </GrantList>
    </MedlineCitation>
    <ArticleIdList>
      <ArticleId IdType="pmc">PMC1234567</ArticleId>
    </ArticleIdList>
  </PubmedArticle>
</PubmedArticleSet>
"""

MINIMAL_EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Minimal Paper</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

NO_ARTICLE_TITLE_ABSTRACT_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>No label abstract</ArticleTitle>
      </Article>
      <Abstract>
        <AbstractText>Just plain text, no label.</AbstractText>
      </Abstract>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class TestParseEfetchXml:
    def test_full_record(self):
        client = PubMedClient()
        result = client._parse_efetch_xml(FULL_EFETCH_XML, "12345678")
        assert result is not None
        assert result.title == "A Study of CRISPR Editing"
        assert result.journal == "Journal of Gene Editing"
        assert result.publication_year == 2022
        assert result.doi == "10.1234/crispr.2022"
        assert result.pmcid == "PMC1234567"
        assert len(result.authors) == 2
        assert result.authors[0].name == "Smith, Jane"
        assert result.authors[1].name == "Doe"
        assert "BACKGROUND: CRISPR is powerful." in result.abstract
        assert "RESULTS: It worked well." in result.abstract
        assert result.pubmed_data["mesh_terms"] == ["Gene Editing", "CRISPR-Cas Systems"]
        assert result.pubmed_data["publication_types"] == ["Journal Article"]
        assert result.pubmed_data["keywords"] == ["gene editing", "CRISPR"]
        assert result.pubmed_data["grants"] == [
            {"id": "R01-12345", "acronym": "NIH", "agency": "National Institutes of Health"}
        ]
        assert result.source_id == "12345678"

    def test_minimal_record_missing_optional_fields(self):
        client = PubMedClient()
        result = client._parse_efetch_xml(MINIMAL_EFETCH_XML, "1")
        assert result is not None
        assert result.title == "Minimal Paper"
        assert result.authors is None
        assert result.journal is None
        assert result.publication_year is None
        assert result.doi is None
        assert result.pmcid is None

    def test_abstract_without_label(self):
        client = PubMedClient()
        result = client._parse_efetch_xml(NO_ARTICLE_TITLE_ABSTRACT_XML, "2")
        assert result.abstract == "Just plain text, no label."

    def test_no_pubmed_article_returns_none(self):
        client = PubMedClient()
        result = client._parse_efetch_xml("<PubmedArticleSet></PubmedArticleSet>", "1")
        assert result is None

    def test_no_medline_citation_returns_none(self):
        client = PubMedClient()
        xml = "<PubmedArticleSet><PubmedArticle></PubmedArticle></PubmedArticleSet>"
        assert client._parse_efetch_xml(xml, "1") is None

    def test_invalid_xml_returns_none(self):
        client = PubMedClient()
        assert client._parse_efetch_xml("<not valid", "1") is None

    def test_source_id_falls_back_to_doi_when_no_pmid(self):
        client = PubMedClient()
        result = client._parse_efetch_xml(FULL_EFETCH_XML, "")
        assert result.source_id == "10.1234/crispr.2022"


class TestGetPaperEfetch:
    def test_returns_none_when_no_response(self):
        client = PubMedClient()
        with patch.object(client, "_make_request", return_value=None):
            assert client._get_paper_efetch("1") is None

    def test_parses_response(self):
        client = PubMedClient()
        with patch.object(client, "_make_request", return_value=FULL_EFETCH_XML):
            result = client._get_paper_efetch("12345678")
        assert result is not None
        assert result.title == "A Study of CRISPR Editing"


class TestGetPapersBatch:
    def test_empty_identifiers(self):
        client = PubMedClient()
        assert client.get_papers_batch([]) == []

    def test_esummary_batch(self):
        client = PubMedClient()
        response = {
            "result": {
                "1": {"uid": "1", "title": "Paper One"},
                "2": {"uid": "2", "title": "Paper Two"},
            }
        }
        with patch.object(client, "_make_request", return_value=response):
            results = client.get_papers_batch(["1", "2"])
        assert len(results) == 2

    def test_esummary_batch_no_response(self):
        client = PubMedClient()
        with patch.object(client, "_make_request", return_value=None):
            assert client.get_papers_batch(["1"]) == []

    def test_esummary_batch_skips_missing_ids(self):
        client = PubMedClient()
        response = {"result": {"1": {"uid": "1", "title": "Paper One"}}}
        with patch.object(client, "_make_request", return_value=response):
            results = client.get_papers_batch(["1", "999"])
        assert len(results) == 1

    def test_efetch_batch(self):
        client = PubMedClient()
        with patch.object(client, "_get_paper_efetch") as mock_efetch:
            mock_efetch.side_effect = [MagicMock(title="A"), None, MagicMock(title="B")]
            results = client.get_papers_batch(["1", "2", "3"], use_efetch=True)
        assert len(results) == 2


class TestPmidForCitation:
    def _mock_response(self, text, status=200):
        resp = MagicMock()
        resp.text = text
        resp.status_code = status
        resp.raise_for_status = MagicMock()
        return resp

    def test_success(self):
        client = PubMedClient()
        client.session.post = MagicMock(
            return_value=self._mock_response("Smith|2022|J Gene Edit|1|1|Title|12345678")
        )
        pmid = client.pmid_for_citation(author="Smith", year=2022, journal="J Gene Edit")
        assert pmid == "12345678"

    def test_not_found(self):
        client = PubMedClient()
        client.session.post = MagicMock(return_value=self._mock_response("NOT_FOUND"))
        assert client.pmid_for_citation(author="Nobody") is None

    def test_empty_response(self):
        client = PubMedClient()
        client.session.post = MagicMock(return_value=self._mock_response(""))
        assert client.pmid_for_citation(author="Nobody") is None

    def test_no_pipe_in_response(self):
        client = PubMedClient()
        client.session.post = MagicMock(return_value=self._mock_response("garbage"))
        assert client.pmid_for_citation(author="Nobody") is None

    def test_non_digit_last_field(self):
        client = PubMedClient()
        client.session.post = MagicMock(
            return_value=self._mock_response("Smith|2022|J|1|1|Title|AMBIGUOUS")
        )
        assert client.pmid_for_citation(author="Smith") is None

    def test_request_exception_returns_none(self):
        import requests

        client = PubMedClient()
        client.session.post = MagicMock(side_effect=requests.RequestException("down"))
        assert client.pmid_for_citation(author="Smith") is None

    def test_http_error_returns_none(self):
        import requests

        client = PubMedClient()
        resp = self._mock_response("ignored", status=500)
        resp.raise_for_status.side_effect = requests.HTTPError("500")
        client.session.post = MagicMock(return_value=resp)
        assert client.pmid_for_citation(author="Smith") is None

    def test_all_params_default_empty(self):
        client = PubMedClient()
        client.session.post = MagicMock(return_value=self._mock_response("NOT_FOUND"))
        assert client.pmid_for_citation() is None
        _, kwargs = client.session.post.call_args
        assert kwargs["data"]["cit"] == "|||||"
