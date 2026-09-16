"""Figures and their files, measured against real Europe PMC documents.

Each defect below was found by comparing the extractors' output with the
article as Europe PMC renders it, and none of them shows up in hand-written
JATS: the shapes that break them - a caption full of inline formulas, a figure
supplement nested inside its parent - are what publishers actually deposit.

No network: the Europe PMC file URLs are asserted by their shape, which was
checked against the live service when they were written (see
``pyeuropepmc.features.fulltext.utils.asset_urls``).
"""

from __future__ import annotations

import pathlib
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.image_fetcher import AssetType, ImageFetcher
from pyeuropepmc.features.fulltext.figures import FigureExtractor
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

DOWNLOADS = pathlib.Path(__file__).resolve().parents[3] / "fixtures" / "fulltext_downloads"

#: Every real document in the fixture corpus.
DOCUMENTS = sorted(DOWNLOADS.glob("PMC*.xml"))
DOCUMENT_IDS = [p.stem for p in DOCUMENTS]


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def tree(path: pathlib.Path) -> ET.Element:
    return DefusedET.fromstring(read(path).encode("utf-8"))


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


@pytest.fixture(scope="module")
def extractor() -> FigureExtractor:
    """A ``FigureExtractor`` whose clients are stubs.

    ``extract_from_xml`` touches neither of them, but ``__init__`` builds a
    FullTextClient that makes a cache directory, and these tests read from
    disk only.
    """
    with (
        patch("pyeuropepmc.features.fulltext.fulltext_client.FullTextClient"),
        patch("pyeuropepmc.features.literature.search.SearchClient"),
    ):
        return FigureExtractor()


@pytest.fixture(scope="module")
def assets_of():
    cache: dict[str, list] = {}

    def load(path: pathlib.Path):
        if path.stem not in cache:
            parser = FullTextXMLParser(read(path))
            cache[path.stem] = ImageFetcher(parser.root, article_id=path.stem).extract_asset_refs()
        return cache[path.stem]

    return load


@pytest.mark.parametrize("path", DOCUMENTS, ids=DOCUMENT_IDS)
class TestEveryBlockIsFound:
    """The namespace bug returned nothing at all for every Europe PMC article."""

    def test_every_figure_table_and_supplement_is_returned(self, path, extractor):
        root = tree(path)
        found = extractor.extract_from_xml(read(path), pmcid=path.stem)
        counts = {
            "figure": len(root.findall(".//fig")),
            "table": len(root.findall(".//table-wrap")),
            "supplement": len(root.findall(".//supplementary-material")),
        }
        for kind, expected in counts.items():
            assert len([f for f in found if f.figure_type == kind]) == expected, kind

    def test_a_figure_with_a_graphic_gets_a_europe_pmc_url(self, path, extractor):
        figures = extractor.extract_from_xml(read(path), pmcid=path.stem)
        with_files = [f for f in figures if f.file_name]
        if not with_files:
            pytest.skip(f"{path.stem} references no files")
        for figure in with_files:
            assert figure.image_url is not None, figure.label
            assert query_of(figure.image_url)["pmcId"] == path.stem
            assert query_of(figure.image_url)["mimeType"], figure.label

    def test_no_file_is_reported_twice(self, path, assets_of):
        """Every graphic inside a figure used to be added again, unlabelled."""
        names = [asset.metadata["file_name"] for asset in assets_of(path)]
        assert len(names) == len(set(names))

    def test_every_asset_has_a_mime_type(self, path, assets_of):
        assert all(asset.mime_type for asset in assets_of(path))

    def test_every_figure_asset_carries_its_label(self, path, assets_of):
        figures = [a for a in assets_of(path) if a.asset_type is AssetType.FIGURE]
        unlabelled = [a for a in figures if not a.label]
        # A <graphic> no figure claims (a graphical abstract) legitimately has
        # none; one that a <fig> owns must carry that figure's label.
        assert [a.metadata["file_name"] for a in unlabelled if a.id] == []


class TestCaptionFormulasAreNotTheFigure:
    """PMC10775981 Fig 3: three inline formulas precede the figure's graphic."""

    PATH = DOWNLOADS / "PMC10775981.xml"

    def test_figure_extractor_picks_the_figure_not_the_equation(self, extractor):
        figures = extractor.extract_from_xml(read(self.PATH), pmcid="PMC10775981")
        fig3 = next(f for f in figures if f.id == "pcbi.1011761.g003")
        assert fig3.file_name == "pcbi.1011761.g003.jpg"
        assert query_of(fig3.image_url)["fileName"] == "pcbi.1011761.g003.jpg"

    def test_parser_extract_figures_picks_the_figure(self):
        parser = FullTextXMLParser(read(self.PATH))
        fig3 = next(f for f in parser.extract_figures() if f["id"] == "pcbi.1011761.g003")
        assert fig3["graphic_uri"] == "pcbi.1011761.g003.jpg"

    def test_structured_figure_block_picks_the_figure(self):
        parser = FullTextXMLParser(read(self.PATH))
        blocks = [
            block
            for section in parser.get_full_text_sections_structured()
            for block in section["content"]
            if block.get("type") == "figure"
        ]
        uris = [block["uri"] for block in blocks if block["uri"]]
        assert "pcbi.1011761.g003.jpg" in uris
        assert not any(uri.startswith("pcbi.1011761.e") for uri in uris)

    def test_formula_images_are_not_figures(self, assets_of):
        formulas = [a for a in assets_of(self.PATH) if a.asset_type is AssetType.FORMULA]
        assert len(formulas) == 21
        figure_files = {
            a.metadata["file_name"]
            for a in assets_of(self.PATH)
            if a.asset_type is AssetType.FIGURE
        }
        assert figure_files == {f"pcbi.1011761.g00{n}.jpg" for n in (1, 2, 3, 4)}

    def test_supplementary_files_keep_their_own_type(self, assets_of):
        supplements = {
            a.metadata["file_name"]: a.mime_type
            for a in assets_of(self.PATH)
            if a.asset_type is AssetType.SUPPLEMENTARY
        }
        assert supplements == {
            "pcbi.1011761.s001.yaml": "text/yaml",
            "pcbi.1011761.s002.m": "text/plain",
            "pcbi.1011761.s003.pdf": "application/pdf",
        }


class TestFigureSupplementsBelongToTheirParent:
    """PMC11687933: five eLife supplements nested in their parent's <p>."""

    PATH = DOWNLOADS / "PMC11687933.xml"
    SUPPLEMENTS = {
        "fig1s1": "fig1",
        "fig2s1": "fig2",
        "fig3s1": "fig3",
        "fig5s1": "fig5",
        "fig6s1": "fig6",
    }

    def test_figure_extractor_links_each_supplement(self, extractor):
        figures = extractor.extract_from_xml(read(self.PATH), pmcid="PMC11687933")
        linked = {f.id: f.parent_id for f in figures if f.parent_id}
        assert linked == self.SUPPLEMENTS

    def test_a_parent_figure_has_no_parent(self, extractor):
        figures = extractor.extract_from_xml(read(self.PATH), pmcid="PMC11687933")
        fig1 = next(f for f in figures if f.id == "fig1")
        assert fig1.parent_id is None
        assert fig1.file_name == "elife-99323-fig1.jpg"

    def test_parser_extract_figures_links_each_supplement(self):
        parser = FullTextXMLParser(read(self.PATH))
        figures = {f["id"]: f for f in parser.extract_figures()}
        assert {i: f["parent_id"] for i, f in figures.items() if f.get("parent_id")} == (
            self.SUPPLEMENTS
        )
        assert figures["fig1s1"]["parent_label"] == "Figure 1."
        assert figures["fig1"]["graphic_uri"] == "elife-99323-fig1.jpg"

    def test_a_supplement_asset_carries_its_own_label(self, assets_of):
        by_file = {a.metadata["file_name"]: a for a in assets_of(self.PATH)}
        supplement = by_file["elife-99323-fig1-figsupp1.jpg"]
        assert supplement.label == "Figure 1—figure supplement 1."
        assert supplement.metadata["parent_label"] == "Figure 1."
        assert by_file["elife-99323-fig1.jpg"].label == "Figure 1."

    def test_source_data_keeps_its_spreadsheet_mime_type(self, assets_of):
        by_file = {a.metadata["file_name"]: a for a in assets_of(self.PATH)}
        source_data = by_file["elife-99323-fig1-data1.xlsx"]
        assert source_data.asset_type is AssetType.SUPPLEMENTARY
        assert source_data.mime_type == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


class TestAlternativeRepresentations:
    """PMC12738713 deposits each figure as a JPEG and a GIF."""

    PATH = DOWNLOADS / "PMC12738713.xml"

    def test_both_formats_are_reported_once_each(self, assets_of):
        fig1 = [a for a in assets_of(self.PATH) if a.id == "Fig1"]
        assert [a.metadata["file_name"] for a in fig1] == [
            "41467_2025_66220_Fig1_HTML.jpg",
            "41467_2025_66220_Fig1_HTML.gif",
        ]
        assert [a.metadata.get("alternative") for a in fig1] == [None, True]

    def test_the_figure_takes_the_first_representation(self, extractor):
        figures = extractor.extract_from_xml(read(self.PATH), pmcid="PMC12738713")
        fig1 = next(f for f in figures if f.id == "Fig1")
        assert fig1.file_name == "41467_2025_66220_Fig1_HTML.jpg"

    def test_a_file_declared_twice_is_reported_once(self, assets_of):
        """Nature lists each supplementary file in the body and again in back matter."""
        supplements = [a for a in assets_of(self.PATH) if a.asset_type is AssetType.SUPPLEMENTARY]
        assert len(supplements) == 4
        assert supplements[0].caption == "Supplementary Information"


class TestExtensionlessGraphics:
    """Springer Nature and OUP write graphic references without a file type."""

    def test_springer_figure_resolves_to_a_jpeg(self, extractor):
        path = DOWNLOADS / "PMC12311175.xml"
        figures = extractor.extract_from_xml(read(path), pmcid="PMC12311175")
        fig1 = next(f for f in figures if f.id == "Fig1")
        assert fig1.file_name == "41392_2025_2280_Fig1_HTML.jpg"
        assert query_of(fig1.image_url)["mimeType"] == "image/jpeg"

    def test_oup_figure_resolves_to_a_jpeg(self, extractor):
        path = DOWNLOADS / "PMC3258128.xml"
        figures = extractor.extract_from_xml(read(path), pmcid="PMC3258128")
        fig1 = next(f for f in figures if f.id == "gkr715-F1")
        assert fig1.file_name == "gkr715f1.jpg"


class TestTablesAndStrayGraphics:
    def test_a_table_image_is_typed_as_a_table(self, assets_of):
        path = DOWNLOADS / "PMC12018715.xml"
        tables = [a for a in assets_of(path) if a.asset_type is AssetType.TABLE]
        assert [a.label for a in tables] == ["Table 1.", "Table 2."]
        assert tables[0].metadata["file_name"] == "10.1177_10775587241304145-table1.jpg"

    def test_an_inline_graphic_in_running_text_is_not_a_figure(self, assets_of):
        """The ORCID icon beside an author's name is not a figure."""
        path = DOWNLOADS / "PMC12018715.xml"
        inline = [a for a in assets_of(path) if a.metadata["jats_tag"] == "inline-graphic"]
        assert [a.asset_type for a in inline] == [AssetType.UNKNOWN]
