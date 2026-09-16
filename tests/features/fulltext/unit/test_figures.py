"""Unit tests for pyeuropepmc.features.fulltext.figures (hermetic)."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from pyeuropepmc.features.fulltext.figures import (
    FigureExtractor,
    FigureFormat,
    FigureInfo,
    extract_figures_from_pmc,
    extract_tables_from_pmc,
)

JATS_BODY = """
  <body>
    <fig id="f1">
      <label>Fig. 1</label>
      <caption><p>The first figure.</p></caption>
      <alt-text>alt description</alt-text>
      <graphic xlink:href="fig1.jpg"/>
    </fig>
    <fig id="f2">
      <label>Fig. 2</label>
      <caption><p>Second figure, no graphic.</p></caption>
    </fig>
    <table-wrap id="t1">
      <label>Table 1</label>
      <caption><p>A table.</p></caption>
    </table-wrap>
    <supplementary-material id="s1">
      <label>Supp 1</label>
      <caption><p>Extra data.</p></caption>
      <media xlink:href="supp1.zip"/>
    </supplementary-material>
  </body>
"""

#: What Europe PMC serves: DTD-based JATS, no namespace.
PLAIN_XML = f"""<?xml version="1.0"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">{JATS_BODY}</article>
"""

#: Schema-based JATS, where every tag carries a default namespace. The
#: extractor searched for one specific namespace - JATS1, which Europe PMC
#: does not use - and so found nothing in either form.
NAMESPACED_XML = f"""<?xml version="1.0"?>
<article xmlns="http://www.ncbi.nlm.nih.gov/JATS1"
         xmlns:xlink="http://www.w3.org/1999/xlink">{JATS_BODY}</article>
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


@pytest.fixture(params=["plain", "namespaced"])
def xml(request):
    return PLAIN_XML if request.param == "plain" else NAMESPACED_XML


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class TestFigureInfo:
    def test_to_dict(self):
        info = FigureInfo(label="Fig. 1", caption="cap", image_url="http://x", pmcid="PMC1")
        d = info.to_dict()
        assert d["label"] == "Fig. 1"
        assert d["pmcid"] == "PMC1"

    def test_to_dict_carries_the_file_and_the_parent(self):
        info = FigureInfo(
            label="Fig. 1—figure supplement 1.",
            caption="cap",
            id="fig1s1",
            file_name="fig1-figsupp1.jpg",
            mime_type="image/jpeg",
            parent_id="fig1",
            parent_label="Fig. 1",
        )
        d = info.to_dict()
        assert d["id"] == "fig1s1"
        assert d["file_name"] == "fig1-figsupp1.jpg"
        assert d["mime_type"] == "image/jpeg"
        assert d["parent_id"] == "fig1"
        assert d["parent_label"] == "Fig. 1"

    def test_repr(self):
        info = FigureInfo(label="Fig. 1", caption="cap")
        assert "Fig. 1" in repr(info)
        assert "figure" in repr(info)


class TestExtractFromXml:
    def test_extracts_all_element_types(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123")
        types = {f.figure_type for f in figures}
        assert types == {"figure", "table", "supplement"}
        assert len(figures) == 4

    def test_figure_with_graphic_gets_a_europe_pmc_url(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123")
        fig1 = next(f for f in figures if f.label == "Fig. 1")
        assert query_of(fig1.image_url) == {
            "pmcId": "PMC123",
            "type": "FILE",
            "fileName": "fig1.jpg",
            "mimeType": "image/jpeg",
            "version": "1",
        }
        assert fig1.file_name == "fig1.jpg"
        assert fig1.id == "f1"
        assert fig1.alt_text == "alt description"

    def test_a_pmcid_is_not_doubled(self, extractor, xml):
        """``PMC{pmcid}`` over a PMCID produced PMCPMC123."""
        figures = extractor.extract_from_xml(xml, pmcid="PMC123")
        assert not any("PMCPMC" in (f.image_url or "") for f in figures)

    def test_figure_without_graphic_has_no_image_url(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123")
        fig2 = next(f for f in figures if f.label == "Fig. 2")
        assert fig2.image_url is None
        assert fig2.file_name is None

    def test_supplementary_file_keeps_its_own_type(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123")
        supp = next(f for f in figures if f.figure_type == "supplement")
        assert supp.file_name == "supp1.zip"
        assert supp.mime_type == "application/zip"

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ('<supplementary-material xlink:href="supp.pdf"/>', "supp.pdf"),
            (
                "<supplementary-material><object-id>supp.pdf</object-id></supplementary-material>",
                "supp.pdf",
            ),
            (
                '<supplementary-material><object-id pub-id-type="doi">10.1/x.pdf</object-id>'
                "</supplementary-material>",
                None,
            ),
        ],
    )
    def test_a_supplement_without_a_media_child(self, extractor, body, expected):
        doc = f'<article xmlns:xlink="http://www.w3.org/1999/xlink"><body>{body}</body></article>'
        (supplement,) = extractor.extract_from_xml(doc, pmcid="PMC1")
        assert supplement.file_name == expected

    def test_without_a_pmcid_there_is_no_url(self, extractor, xml):
        """A URL that cannot resolve is worse than none."""
        figures = extractor.extract_from_xml(xml)
        assert all(f.image_url is None for f in figures)
        assert next(f for f in figures if f.label == "Fig. 1").file_name == "fig1.jpg"

    def test_exclude_tables(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, include_tables=False)
        assert not any(f.figure_type == "table" for f in figures)

    def test_exclude_supplements(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, include_supplements=False)
        assert not any(f.figure_type == "supplement" for f in figures)

    def test_format_filter_excludes_non_matching_file(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123", format="png")
        # fig1's file ends in .jpg, so a "png" filter should exclude it while
        # a figure with no file still passes through
        fig_labels = {f.label for f in figures if f.figure_type == "figure"}
        assert "Fig. 1" not in fig_labels
        assert "Fig. 2" in fig_labels

    def test_format_filter_matches(self, extractor, xml):
        figures = extractor.extract_from_xml(xml, pmcid="PMC123", format="jpg")
        assert "Fig. 1" in {f.label for f in figures}

    @pytest.mark.parametrize(
        ("file_name", "wanted", "expected"),
        [
            ("fig.tif", FigureFormat.TIFF, True),  # .tif and "tiff" are one type
            ("fig.jpeg", FigureFormat.JPEG, True),
            ("fig.png", FigureFormat.JPEG, False),
            ("data.fasta", "fasta", True),
            # An unknown format must not match every unknown file type.
            ("data.fasta", FigureFormat.TIFF, False),
        ],
    )
    def test_format_filter_compares_file_types(self, extractor, file_name, wanted, expected):
        figure = FigureInfo(label="Fig. 1", caption="", file_name=file_name)
        assert extractor._matches_format(figure, wanted) is expected

    def test_an_item_without_a_file_passes_any_filter(self, extractor):
        """A table rendered as markup has no image to judge."""
        assert extractor._matches_format(FigureInfo(label="Table 1", caption=""), "png")

    def test_invalid_xml_returns_empty(self, extractor):
        assert extractor.extract_from_xml("<not valid xml") == []

    def test_no_figures_in_xml(self, extractor):
        empty_doc = '<?xml version="1.0"?><article><body/></article>'
        assert extractor.extract_from_xml(empty_doc) == []


class TestCaptionFormulasAndSupplements:
    """The two shapes a ``.//graphic`` search gets wrong."""

    NESTED_XML = """<?xml version="1.0"?>
    <article xmlns:xlink="http://www.w3.org/1999/xlink"><body>
      <fig id="fig1">
        <label>Figure 1.</label>
        <caption><p>Where
          <inline-formula><alternatives><graphic xlink:href="e012.jpg"/></alternatives></inline-formula>
          holds.</p></caption>
        <graphic xlink:href="fig1.jpg"/>
        <p><fig id="fig1s1">
          <label>Figure 1—figure supplement 1.</label>
          <caption><p>A supplement.</p></caption>
          <graphic xlink:href="fig1-figsupp1.jpg"/>
        </fig></p>
      </fig>
    </body></article>
    """

    def test_the_caption_formula_is_not_the_figure(self, extractor):
        figures = extractor.extract_from_xml(self.NESTED_XML, pmcid="PMC1")
        fig1 = next(f for f in figures if f.id == "fig1")
        assert fig1.file_name == "fig1.jpg"

    def test_the_supplement_is_its_own_figure(self, extractor):
        figures = extractor.extract_from_xml(self.NESTED_XML, pmcid="PMC1")
        supplement = next(f for f in figures if f.id == "fig1s1")
        assert supplement.file_name == "fig1-figsupp1.jpg"
        assert supplement.parent_id == "fig1"
        assert supplement.parent_label == "Figure 1."

    def test_a_parent_figures_caption_excludes_its_supplement(self, extractor):
        figures = extractor.extract_from_xml(self.NESTED_XML, pmcid="PMC1")
        fig1 = next(f for f in figures if f.id == "fig1")
        assert "A supplement" not in fig1.caption


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
        extractor.fulltext_client.get_fulltext_content.return_value = PLAIN_XML
        figures = extractor.extract(pmcid="PMC123")
        assert len(figures) == 4
        extractor.fulltext_client.get_fulltext_content.assert_called_once_with(
            "PMC123", format_type="xml"
        )

    def test_extract_resolves_pmid_first(self, extractor):
        extractor.search_client.search_and_parse.return_value = [{"pmcid": "PMC555"}]
        extractor.fulltext_client.get_fulltext_content.return_value = PLAIN_XML
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
