from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.bibliography.bibtex import BibtexManager, is_bibtex_content
from pyeuropepmc.features.bibliography.models import BibEntry, BibLibrary


@pytest.fixture
def sample_bibtex() -> str:
    return "@article{key2024, title = {Hello}, author = {Smith, John}, year = {2024}, doi = {10.1234/test}}"


@pytest.fixture
def entry() -> BibEntry:
    return BibEntry(
        entry_type="article",
        citation_key="key2024",
        fields={"title": "Hello", "author": "Smith, John", "year": "2024", "doi": "10.1234/test"},
    )


@pytest.fixture
def library(entry) -> BibLibrary:
    lib = BibLibrary()
    lib.add(entry)
    return lib


class TestBibtexManagerParse:
    def test_parse_string_v2(self, sample_bibtex):
        mock_lib = BibLibrary()
        mock_lib.add(
            BibEntry(entry_type="article", citation_key="key2024", fields={"title": "{Hello}"})
        )
        mgr = BibtexManager()
        mgr._parse = MagicMock(return_value=mock_lib)
        result = mgr.parse_string(sample_bibtex)
        mgr._parse.assert_called_once_with(sample_bibtex)
        assert len(result) == 1
        assert result["key2024"].fields["title"] == "{Hello}"

    def test_parse_file(self, tmp_path, sample_bibtex):
        bib_file = tmp_path / "test.bib"
        bib_file.write_text(sample_bibtex, encoding="utf-8")
        mock_lib = BibLibrary()
        mock_lib.add(
            BibEntry(entry_type="article", citation_key="key2024", fields={"title": "{Hello}"})
        )
        mock_lib.file_path = str(bib_file.resolve())
        mgr = BibtexManager()
        mgr._parse = MagicMock(return_value=mock_lib)
        result = mgr.parse_file(bib_file)
        assert len(result) == 1
        assert result.file_path == str(bib_file.resolve())

    def test_parse_empty_string(self):
        mgr = BibtexManager()
        mgr._parse = MagicMock(return_value=BibLibrary())
        result = mgr.parse_string("")
        assert len(result) == 0


class TestBibtexManagerWrite:
    def test_write_string(self, library):
        expected = "@article{key2024, title = {Hello}}"
        mgr = BibtexManager()
        mgr._write = MagicMock(return_value=expected)
        result = mgr.write_string(library)
        mgr._write.assert_called_once_with(library)
        assert result == expected

    def test_write_file(self, tmp_path, library):
        out_path = tmp_path / "out.bib"
        mgr = BibtexManager()
        mgr._write = MagicMock(return_value="@article{k,}")
        result = mgr.write_file(library, out_path)
        assert result == out_path
        assert out_path.exists()
        assert out_path.read_text(encoding="utf-8") == "@article{k,}"

    def test_write_roundtrip(self):
        lib = BibLibrary()
        lib.add(BibEntry(entry_type="article", citation_key="r1", fields={"title": "Round"}))
        mgr = BibtexManager()
        mgr._write = MagicMock(return_value="@article{r1, title = {Round}}")
        written = mgr.write_string(lib)
        assert "title" in written


class TestBibtexManagerValidate:
    def test_valid_entry_returns_no_issues(self, library):
        mgr = BibtexManager()
        issues = mgr.validate(library)
        assert len(issues) == 0

    def test_missing_title_warning(self):
        entry = BibEntry(
            entry_type="article", citation_key="k", fields={"author": "A", "year": "2020"}
        )
        lib = BibLibrary()
        lib.add(entry)
        mgr = BibtexManager()
        issues = mgr.validate(lib)
        titles = [i for i in issues if "Missing title" in i["message"]]
        assert len(titles) == 1
        assert titles[0]["severity"] == "warning"

    def test_missing_author_warning(self):
        entry = BibEntry(
            entry_type="article", citation_key="k", fields={"title": "T", "year": "2020"}
        )
        lib = BibLibrary()
        lib.add(entry)
        mgr = BibtexManager()
        issues = mgr.validate(lib)
        authors = [i for i in issues if "Missing author" in i["message"]]
        assert len(authors) == 1

    def test_duplicate_keys_error(self):
        lib = BibLibrary()
        lib.entries = [
            BibEntry(entry_type="article", citation_key="dup", fields={"title": "A"}),
            BibEntry(entry_type="article", citation_key="dup", fields={"title": "B"}),
        ]
        mgr = BibtexManager()
        issues = mgr.validate(lib)
        dups = [i for i in issues if "Duplicate" in i["message"]]
        assert len(dups) == 1
        assert dups[0]["severity"] == "error"


class TestBibtexManagerMerge:
    def test_merge_dedup_by_doi(self):
        e1 = BibEntry(entry_type="article", citation_key="k1", fields={"doi": "10.1234/a"})
        e2 = BibEntry(entry_type="article", citation_key="k2", fields={"doi": "10.1234/a"})
        lib1, lib2 = BibLibrary(), BibLibrary()
        lib1.add(e1)
        lib2.add(e2)
        mgr = BibtexManager()
        merged = mgr.merge([lib1, lib2])
        assert len(merged) == 1

    def test_merge_different_dois(self):
        e1 = BibEntry(entry_type="article", citation_key="k1", fields={"doi": "10.1234/a"})
        e2 = BibEntry(entry_type="article", citation_key="k2", fields={"doi": "10.1234/b"})
        lib1, lib2 = BibLibrary(), BibLibrary()
        lib1.add(e1)
        lib2.add(e2)
        mgr = BibtexManager()
        merged = mgr.merge([lib1, lib2])
        assert len(merged) == 2


class TestBibtexManagerEnrich:
    def test_enrich_entries_with_doi(self):
        entry = BibEntry(entry_type="article", citation_key="k", fields={"doi": "10.1234/test"})
        lib = BibLibrary()
        lib.add(entry)
        mgr = BibtexManager()
        with patch(
            "pyeuropepmc.features.bibliography.reference.ReferenceResolver"
        ) as MockResolver:
            resolver = MockResolver.return_value
            resolver.resolve_doi.return_value = None
            enriched = mgr.enrich_entries(lib)
            assert enriched["k"].fields["doi"] == "10.1234/test"


class TestIsBibtexContent:
    def test_valid_bibtex_detected(self):
        assert is_bibtex_content("@article{key,}") is True
        assert is_bibtex_content("@book{author2020, title = {A}}") is True

    def test_non_bibtex_not_detected(self):
        assert is_bibtex_content("Hello world") is False
        assert is_bibtex_content("") is False
        assert is_bibtex_content("just a { brace") is False
