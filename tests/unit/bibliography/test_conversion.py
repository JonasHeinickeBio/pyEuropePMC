import pytest
from pyeuropepmc.features.bibliography.conversion import CitationConverter
from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary, Reference, CitationFormat


@pytest.fixture
def converter() -> CitationConverter:
    return CitationConverter()


@pytest.fixture
def entry() -> BibEntry:
    return BibEntry(
        entry_type="article",
        citation_key="test2024",
        fields={
            "title": "{Test Article}",
            "author": "{Smith, John and Doe, Jane}",
            "year": "2024",
            "journal": "{Test Journal}",
            "doi": "10.1234/test",
            "volume": "10",
            "pages": "100-110",
        },
    )


@pytest.fixture
def library(entry) -> BibLibrary:
    lib = BibLibrary()
    lib.add(entry)
    return lib


class TestCitationConverterToRis:
    def test_to_ris_from_bibentry(self, converter, entry):
        ris = converter.to_ris(entry)
        assert ris.startswith("TY  - JOUR")
        assert "TI  - Test Article" in ris
        assert "AU  - Smith, John" in ris
        assert "AU  - Doe, Jane" in ris
        assert "PY  - 2024" in ris
        assert "DO  - 10.1234/test" in ris
        assert "ER  - " in ris

    def test_to_ris_from_reference(self, converter):
        ref = Reference(title="Ref Article", authors=["Lee, K"], year=2023, journal="J", doi="10.1/z")
        ris = converter.to_ris(ref)
        assert "TI  - Ref Article" in ris
        assert "AU  - Lee, K" in ris
        assert "PY  - 2023" in ris

    def test_to_ris_type_mapping(self, converter):
        ref = Reference(entry_type="book", title="A Book")
        ris = converter.to_ris(ref)
        assert ris.startswith("TY  - BOOK")

    def test_to_ris_empty_fields(self, converter):
        ref = Reference()
        ris = converter.to_ris(ref)
        assert ris == "TY  - JOUR\nER  - "


class TestCitationConverterToCsl:
    def test_to_csl_json_from_bibentry(self, converter, entry):
        csl = converter.to_csl_json(entry)
        assert csl["title"] == "Test Article"
        assert csl["type"] == "article-journal"
        assert csl["DOI"] == "10.1234/test"
        assert len(csl["author"]) == 2
        assert csl["author"][0]["family"] == "Smith"
        assert csl["author"][0]["given"] == "John"

    def test_to_csl_json_from_reference(self, converter):
        ref = Reference(title="CSL Paper", authors=["Park, S"], year=2022, journal="Nature")
        csl = converter.to_csl_json(ref)
        assert csl["title"] == "CSL Paper"
        assert csl["issued"]["date-parts"] == [[2022]]
        assert csl["container-title"] == "Nature"

    def test_to_csl_json_bibentry_type_mapping(self, converter):
        entry = BibEntry(entry_type="inproceedings", citation_key="c", fields={"title": "Conf"})
        csl = converter.to_csl_json(entry)
        assert csl["type"] == "paper-conference"


class TestCitationConverterDetectFormat:
    def test_detect_bibtex(self, converter):
        assert converter.detect_format("@article{k,}") == CitationFormat.BIBTEX

    def test_detect_ris(self, converter):
        assert converter.detect_format("TY  - JOUR\nTI  - Test\nER  - ") == CitationFormat.RIS

    def test_detect_csl_json(self, converter):
        assert converter.detect_format('{"title": "Test", "type": "article-journal"}') == CitationFormat.CSL_JSON


class TestCitationConverterConvert:
    def test_bibtex_to_ris(self, converter):
        pytest.importorskip("bibtexparser")
        result = converter.convert("@article{k, title = {Hello}}", target_format="ris")
        assert "TI  - Hello" in result

    def test_bibtex_to_csl(self, converter):
        pytest.importorskip("bibtexparser")
        result = converter.convert("@article{k, title = {Hello}}", target_format="csl-json")
        assert '"Hello"' in result or "Hello" in result

    def test_convert_empty_bibtex(self, converter):
        pytest.importorskip("bibtexparser")
        result = converter.convert("@misc{empty,}", target_format="ris")
        assert result == ""

    def test_convert_unknown_format_raises(self, converter):
        with pytest.raises(ValueError):
            converter.convert("text", target_format="unknown", input_format="unknown")


class TestCitationConverterFromRis:
    def test_from_ris(self, converter):
        ris = "TY  - JOUR\nTI  - My Paper\nAU  - Author, A\nPY  - 2021\nDO  - 10.1/x\nER  - "
        ref = converter.from_ris(ris)
        assert ref.title == "My Paper"
        assert ref.authors == ["Author, A"]
        assert ref.year == 2021
        assert ref.doi == "10.1/x"
