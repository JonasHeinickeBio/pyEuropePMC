"""Unit tests for pyeuropepmc.features.fulltext.figures (hermetic)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from pyeuropepmc.features.fulltext.figures import (
    FigureExtractor,
    FigureFormat,
    FigureInfo,
    extract_figures_from_pmc,
    extract_tables_from_pmc,
)

JATS_XML = """<?xml version="1.0"?>
<article xmlns="http://www.ncbi.nlm.nih.gov/JATS1"
         xmlns:xlink="http://www.w3.org/1999/xlink">
  <body>
    <fig>
      <label>Fig. 1</label>
      <caption><p>The first figure.</p></caption>
      <alt-text>alt description</alt-text>
      <graphic xlink:href="fig1.jpg"/>
    </fig>
    <fig>
      <label>Fig. 2</label>
      <caption><p>Second figure, no graphic.</p></caption>
    </fig>
    <table-wrap>
      <label>Table 1</label>
      <caption><p>A table.</p></caption>
    </table-wrap>
    <supplementary-material>
      <label>Supp 1</label>
      <caption><p>Extra data.</p></caption>
    </supplementary-material>
  </body>
</article>
"""


@pytest.fixture
def extractor():
    with (
        patch("pyeuropepmc.features.fulltext.fulltext_client.FullTextClient") as MockFT,
        patch("pyeuropepmc.features.literature.search.SearchClient") as MockSC,
    ):
        instance = FigureExtractor()
        instance.fulltext_client = MockFT.return_value
        instance.search_client = MockSC.return_value
        yield instance


class TestFigureInfo:
    def test_to_dict(self):
        info = FigureInfo(label="Fig. 1", caption="cap", image_url="http://x", pmcid="PMC1")
        d = info.to_dict()
        assert d["label"] == "Fig. 1"
        assert d["pmcid"] == "PMC1"

    def test_repr(self):
        info = FigureInfo(label="Fig. 1", caption="cap")
        assert "Fig. 1" in repr(info)
        assert "figure" in repr(info)


class TestExtractFromXml:
    def test_extracts_all_element_types(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, pmcid="PMC123")
        types = {f.figure_type for f in figures}
        assert types == {"figure", "table", "supplement"}
        assert len(figures) == 4

    def test_figure_with_graphic_gets_image_url(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, pmcid="PMC123")
        fig1 = next(f for f in figures if f.label == "Fig. 1")
        assert fig1.image_url is not None
        assert "PMC123" in fig1.image_url
        assert "fig1.jpg" in fig1.image_url

    def test_figure_without_graphic_has_no_image_url(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, pmcid="PMC123")
        fig2 = next(f for f in figures if f.label == "Fig. 2")
        assert fig2.image_url is None

    def test_exclude_tables(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, include_tables=False)
        assert not any(f.figure_type == "table" for f in figures)

    def test_exclude_supplements(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, include_supplements=False)
        assert not any(f.figure_type == "supplement" for f in figures)

    def test_format_filter_excludes_non_matching_url(self, extractor):
        figures = extractor.extract_from_xml(JATS_XML, pmcid="PMC123", format="png")
        # fig1's URL ends in .jpg, so a "png" filter should exclude it while
        # a figure with no image_url still passes through
        fig_labels = {f.label for f in figures if f.figure_type == "figure"}
        assert "Fig. 1" not in fig_labels
        assert "Fig. 2" in fig_labels

    def test_invalid_xml_returns_empty(self, extractor):
        assert extractor.extract_from_xml("<not valid xml") == []

    def test_no_figures_in_xml(self, extractor):
        empty_doc = '<?xml version="1.0"?><article xmlns="http://www.ncbi.nlm.nih.gov/JATS1"><body/></article>'
        assert extractor.extract_from_xml(empty_doc) == []


class TestResolvePmcid:
    def test_resolve_by_pmid(self, extractor):
        extractor.search_client.search_and_parse.return_value = [{"pmcid": "PMC999"}]
        assert extractor._resolve_pmcid(pmid="123") == "PMC999"
        args, kwargs = extractor.search_client.search_and_parse.call_args
        assert "EXT_ID:123" in args[0]

    def test_resolve_by_doi(self, extractor):
        extractor.search_client.search_and_parse.return_value = [{"pmcid": "PMC999"}]
        assert extractor._resolve_pmcid(doi="10.1234/x") == "PMC999"
        args, _ = extractor.search_client.search_and_parse.call_args
        assert 'DOI:"10.1234/x"' in args[0]

    def test_resolve_no_identifier_returns_none(self, extractor):
        assert extractor._resolve_pmcid() is None

    def test_resolve_no_results_returns_none(self, extractor):
        extractor.search_client.search_and_parse.return_value = []
        assert extractor._resolve_pmcid(pmid="123") is None

    def test_resolve_result_without_pmcid_returns_none(self, extractor):
        extractor.search_client.search_and_parse.return_value = [{"doi": "10.1/x"}]
        assert extractor._resolve_pmcid(pmid="123") is None

    def test_resolve_exception_returns_none(self, extractor):
        extractor.search_client.search_and_parse.side_effect = RuntimeError("boom")
        assert extractor._resolve_pmcid(pmid="123") is None


class TestExtract:
    def test_extract_with_pmcid(self, extractor):
        extractor.fulltext_client.get_fulltext_content.return_value = JATS_XML
        figures = extractor.extract(pmcid="PMC123")
        assert len(figures) == 4
        extractor.fulltext_client.get_fulltext_content.assert_called_once_with(
            "PMC123", format_type="xml"
        )

    def test_extract_resolves_pmid_first(self, extractor):
        extractor.search_client.search_and_parse.return_value = [{"pmcid": "PMC555"}]
        extractor.fulltext_client.get_fulltext_content.return_value = JATS_XML
        figures = extractor.extract(pmid="123")
        assert len(figures) == 4
        extractor.fulltext_client.get_fulltext_content.assert_called_once_with(
            "PMC555", format_type="xml"
        )

    def test_extract_unresolvable_identifier_returns_empty(self, extractor):
        figures = extractor.extract()
        assert figures == []

    def test_extract_fulltext_error_returns_empty(self, extractor):
        extractor.fulltext_client.get_fulltext_content.side_effect = RuntimeError("no xml")
        assert extractor.extract(pmcid="PMC123") == []

    def test_extract_empty_xml_returns_empty(self, extractor):
        extractor.fulltext_client.get_fulltext_content.return_value = ""
        assert extractor.extract(pmcid="PMC123") == []


class TestModuleFunctions:
    def test_extract_figures_from_pmc(self):
        with patch("pyeuropepmc.features.fulltext.figures.FigureExtractor") as MockExtractor:
            instance = MockExtractor.return_value
            instance.extract.return_value = [FigureInfo(label="Fig. 1", caption="c")]
            result = extract_figures_from_pmc(pmcid="PMC1")
            assert len(result) == 1
            instance.extract.assert_called_once_with(
                pmcid="PMC1", pmid=None, doi=None, include_tables=True, include_supplements=True
            )

    def test_extract_tables_from_pmc(self):
        with patch("pyeuropepmc.features.fulltext.figures.FigureExtractor") as MockExtractor:
            instance = MockExtractor.return_value
            instance.extract.return_value = []
            extract_tables_from_pmc(pmcid="PMC1")
            instance.extract.assert_called_once_with(
                pmcid="PMC1", pmid=None, doi=None, include_tables=True, include_supplements=False
            )


def test_figure_format_constants():
    assert FigureFormat.PNG == "png"
    assert FigureFormat.ALL == "all"
