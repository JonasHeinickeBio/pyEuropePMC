from pyeuropepmc.features.bibliography.models import (
    BibEntry,
    BibLibrary,
    CitationFormat,
    VerificationStatus,
)


class TestBibEntry:
    def test_creation(self):
        entry = BibEntry(entry_type="article", citation_key="smith2024", fields={"title": "Test"})
        assert entry.entry_type == "article"
        assert entry.citation_key == "smith2024"
        assert entry.fields["title"] == "Test"
        assert entry.tags == []
        assert entry.source is None

    def test_to_dict(self):
        entry = BibEntry(
            entry_type="article",
            citation_key="key1",
            fields={"title": "A"},
            tags=["ml"],
            source="manual",
        )
        d = entry.to_dict()
        assert d == {
            "entry_type": "article",
            "citation_key": "key1",
            "fields": {"title": "A"},
            "tags": ["ml"],
            "source": "manual",
        }

    def test_from_dict_roundtrip(self):
        original = BibEntry(
            entry_type="inproceedings",
            citation_key="johnson2023",
            fields={"title": "B"},
            tags=["nlp"],
        )
        d = original.to_dict()
        restored = BibEntry.from_dict(d)
        assert restored.entry_type == original.entry_type
        assert restored.citation_key == original.citation_key
        assert restored.fields == original.fields
        assert restored.tags == original.tags

    def test_repr(self):
        entry = BibEntry(entry_type="book", citation_key="key", fields={"title": "T"})
        assert "BibEntry" in repr(entry)


class TestBibLibrary:
    def test_add_and_lookup(self):
        lib = BibLibrary()
        e1 = BibEntry(entry_type="article", citation_key="k1", fields={"title": "T1"})
        e2 = BibEntry(entry_type="article", citation_key="k2", fields={"title": "T2"})
        lib.add(e1)
        lib.add(e2)
        assert len(lib) == 2
        assert lib["k1"] is e1
        assert lib["k2"] is e2

    def test_add_replaces_duplicate_key(self):
        lib = BibLibrary()
        e1 = BibEntry(entry_type="article", citation_key="k1", fields={"title": "T1"})
        e2 = BibEntry(entry_type="article", citation_key="k1", fields={"title": "T2"})
        lib.add(e1)
        lib.add(e2)
        assert len(lib) == 1
        assert lib["k1"].fields["title"] == "T2"

    def test_remove(self):
        lib = BibLibrary()
        e = BibEntry(entry_type="article", citation_key="to_remove")
        lib.add(e)
        assert lib.remove("to_remove") is True
        assert lib.remove("nonexistent") is False
        assert len(lib) == 0

    def test_filter(self):
        lib = BibLibrary()
        lib.add(BibEntry(entry_type="article", citation_key="a1", fields={"year": "2020"}))
        lib.add(BibEntry(entry_type="article", citation_key="a2", fields={"year": "2021"}))
        lib.add(BibEntry(entry_type="book", citation_key="b1", fields={"year": "2020"}))
        assert len(lib.filter(entry_type="article")) == 2
        assert len(lib.filter(entry_type="book")) == 1
        assert len(lib.filter(year="2020")) == 2
        assert len(lib.filter(entry_type="article", year="2020")) == 1

    def test_to_dict_from_dict_roundtrip(self):
        lib = BibLibrary()
        lib.add(
            BibEntry(
                entry_type="article",
                citation_key="k1",
                fields={"title": "T"},
                tags=["a"],
                source="x",
            )
        )
        lib.add(BibEntry(entry_type="book", citation_key="k2", fields={"author": "A"}, source="y"))
        data = lib.to_dict()
        assert len(data) == 2
        restored = BibLibrary.from_dict(data)
        assert len(restored) == 2
        assert restored["k1"].fields["title"] == "T"
        assert restored["k2"].fields["author"] == "A"

    def test_missing_key_returns_none(self):
        lib = BibLibrary()
        assert lib["nonexistent"] is None


class TestEnums:
    def test_citation_format_values(self):
        assert CitationFormat.BIBTEX.value == "bibtex"
        assert CitationFormat.RIS.value == "ris"
        assert CitationFormat.CSL_JSON.value == "csl-json"

    def test_verification_status_values(self):
        assert VerificationStatus.VERIFIED.value == "verified"
        assert VerificationStatus.NOT_FOUND.value == "not_found"
