"""Unit tests for pyeuropepmc.features.fulltext.index (in-memory SQLite FTS5)."""

from __future__ import annotations

import pytest

from pyeuropepmc.features.fulltext.index import (
    FullTextIndex,
    IndexEntry,
    SearchResult,
    create_index,
    open_index,
)
from pyeuropepmc.models.literature import Author, LiteratureResult


@pytest.fixture
def index():
    idx = FullTextIndex(":memory:")
    yield idx
    idx.close()


def _entry(**overrides):
    defaults = dict(
        title="CRISPR cancer therapy",
        abstract="A study of CRISPR gene editing for cancer treatment.",
        authors="Smith J; Doe A",
        journal="Nature",
        doi="10.1234/crispr",
        pmid="111",
        pmcid="PMC111",
        source="europepmc",
        source_id="111",
        year=2023,
        citation_count=5,
    )
    defaults.update(overrides)
    return IndexEntry(**defaults)


class TestIndexEntry:
    def test_from_literature_result_with_author_objects(self):
        result = LiteratureResult(
            title="T",
            abstract="A",
            authors=[Author(name="Jane Doe")],
            journal="J",
            doi="10.1/x",
            pmid="1",
            pmcid="PMC1",
            source="pubmed",
            source_id="1",
            publication_year=2020,
            citation_count=3,
            extra_metadata={"k": "v"},
        )
        entry = IndexEntry.from_literature_result(result)
        assert entry.title == "T"
        assert "Jane Doe" in entry.authors
        assert entry.metadata == {"k": "v"}

    def test_from_literature_result_with_dict_authors(self):
        result = LiteratureResult(
            title="T",
            authors=None,
            source="pubmed",
            source_id="1",
        )
        entry = IndexEntry.from_literature_result(result)
        assert entry.authors == ""

    def test_from_literature_result_minimal(self):
        result = LiteratureResult(source="arxiv", source_id="2")
        entry = IndexEntry.from_literature_result(result)
        assert entry.title == ""
        assert entry.citation_count == 0


class TestFullTextIndexBasics:
    def test_add_returns_rowid(self, index):
        rowid = index.add(_entry())
        assert rowid == 1

    def test_add_many(self, index):
        n = index.add_many([_entry(pmid="1"), _entry(pmid="2"), _entry(pmid="3")])
        assert n == 3
        assert index.count() == 3

    def test_add_many_skips_failures(self, index, monkeypatch):
        call_count = {"n": 0}
        original_add = index.add

        def flaky_add(entry):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("boom")
            return original_add(entry)

        monkeypatch.setattr(index, "add", flaky_add)
        n = index.add_many([_entry(pmid="1"), _entry(pmid="2"), _entry(pmid="3")])
        assert n == 2

    def test_search_finds_indexed_document(self, index):
        index.add(_entry())
        results = index.search("CRISPR")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "CRISPR cancer therapy"
        assert "title" in results[0].snippets

    def test_search_no_highlight(self, index):
        index.add(_entry())
        results = index.search("CRISPR", highlighted=False)
        assert len(results) == 1
        assert results[0].snippets == {}

    def test_search_no_match_returns_empty(self, index):
        index.add(_entry())
        assert index.search("nonexistentterm12345") == []

    def test_search_invalid_fts5_query_returns_empty(self, index):
        index.add(_entry())
        # unbalanced quote is an FTS5 syntax error
        assert index.search('"unterminated') == []

    def test_search_pagination(self, index):
        for i in range(5):
            index.add(_entry(pmid=str(i), doi=f"10.1234/{i}"))
        page1 = index.search("CRISPR", limit=2, offset=0)
        page2 = index.search("CRISPR", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2

    def test_count_all(self, index):
        index.add(_entry())
        assert index.count() == 1

    def test_count_with_query(self, index):
        index.add(_entry())
        index.add(
            _entry(
                pmid="2",
                doi="10.1234/other",
                title="Unrelated topic",
                abstract="Nothing to do with gene editing.",
            )
        )
        assert index.count("CRISPR") == 1

    def test_get_existing(self, index):
        rowid = index.add(_entry())
        doc = index.get(rowid)
        assert doc["title"] == "CRISPR cancer therapy"
        assert doc["metadata"] == {}

    def test_get_with_metadata_json(self, index):
        rowid = index.add(_entry(metadata={"foo": "bar"}))
        doc = index.get(rowid)
        assert doc["metadata"] == {"foo": "bar"}

    def test_get_missing_returns_none(self, index):
        assert index.get(999) is None

    def test_get_with_corrupt_metadata_json(self, index):
        rowid = index.add(_entry())
        index.conn.execute(
            "UPDATE papers_meta SET metadata_json = 'not json' WHERE id = ?", (rowid,)
        )
        index.conn.commit()
        doc = index.get(rowid)
        assert doc["metadata"] == {}

    def test_get_by_doi(self, index):
        index.add(_entry())
        doc = index.get_by_doi("10.1234/crispr")
        assert doc is not None
        assert doc["doi"] == "10.1234/crispr"

    def test_get_by_doi_missing(self, index):
        assert index.get_by_doi("nope") is None

    def test_get_by_pmid(self, index):
        index.add(_entry())
        doc = index.get_by_pmid("111")
        assert doc is not None

    def test_get_by_pmid_missing(self, index):
        assert index.get_by_pmid("nope") is None

    def test_update_replaces_existing_by_pmid(self, index):
        index.add(_entry())
        updated = index.update(_entry(title="Updated title"))
        assert updated is True
        doc = index.get_by_pmid("111")
        assert doc["title"] == "Updated title"
        assert index.count() == 1

    def test_update_matches_by_doi_when_no_pmid(self, index):
        index.add(_entry(pmid=""))
        updated = index.update(_entry(pmid="", title="New title"))
        assert updated is True

    def test_update_matches_by_source_id_when_no_pmid_or_doi(self, index):
        index.add(_entry(pmid="", doi="", source_id="src-1"))
        updated = index.update(_entry(pmid="", doi="", source_id="src-1", title="New"))
        assert updated is True

    def test_update_inserts_when_no_identifiers(self, index):
        updated = index.update(_entry(pmid="", doi="", source_id=""))
        assert updated is False
        assert index.count() == 1

    def test_update_inserts_when_not_found(self, index):
        updated = index.update(_entry(pmid="does-not-exist"))
        assert updated is False
        assert index.count() == 1

    def test_delete(self, index):
        rowid = index.add(_entry())
        assert index.delete(rowid) is True
        assert index.count() == 0
        # regression: a naive FTS5 external-content delete corrupts the
        # index (raises "database disk image is malformed" on the next
        # query) if it doesn't pass the real old column values.
        assert index.search("CRISPR") == []

    def test_delete_nonexistent_returns_false(self, index):
        assert index.delete(999) is False

    def test_delete_leaves_other_documents_searchable(self, index):
        rowid = index.add(_entry())
        index.add(_entry(pmid="2", doi="10.1234/other", title="Something else entirely"))
        index.delete(rowid)
        assert index.count() == 1
        results = index.search("Something")
        assert len(results) == 1
        assert results[0].title == "Something else entirely"

    def test_clear(self, index):
        index.add(_entry())
        index.add(_entry(pmid="2", doi="10.1234/other"))
        index.clear()
        assert index.count() == 0

    def test_stats(self, index):
        index.add(_entry())
        index.add(_entry(pmid="2", doi="10.1234/other", source="pubmed"))
        stats = index.stats()
        assert stats["total_documents"] == 2
        assert stats["source_distribution"]["europepmc"] == 1
        assert stats["source_distribution"]["pubmed"] == 1
        assert stats["db_path"] == ":memory:"

    def test_context_manager(self):
        with FullTextIndex(":memory:") as idx:
            idx.add(_entry())
            assert idx.count() == 1

    def test_open_without_create_still_works_on_fresh_db(self):
        # ":memory:" always starts schema-less; create=False means no schema
        # is ensured, but we can still exercise the constructor path.
        idx = FullTextIndex(":memory:", create=False)
        try:
            with pytest.raises(Exception):  # noqa: B017
                idx.count()
        finally:
            idx.close()


class TestModuleFunctions:
    def test_create_index(self):
        idx = create_index(":memory:")
        try:
            assert idx.count() == 0
        finally:
            idx.close()

    def test_open_index_on_file(self, tmp_path):
        db_path = str(tmp_path / "idx.db")
        idx1 = create_index(db_path)
        idx1.add(_entry())
        idx1.close()

        idx2 = open_index(db_path)
        try:
            assert idx2.count() == 1
        finally:
            idx2.close()

    def test_default_db_path_directory_created(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        monkeypatch.setattr(
            "pyeuropepmc.features.fulltext.index._DEFAULT_INDEX_PATH",
            str(fake_home / ".pyeuropepmc" / "fts_index.db"),
        )
        idx = FullTextIndex()
        try:
            assert (fake_home / ".pyeuropepmc").exists()
        finally:
            idx.close()


class TestAuthorsSnippet:
    def test_authors_snippet_is_taken_from_the_authors_column(self, index):
        index.add(_entry(authors="Hopper G; Lovelace A", journal="Journal of Hopper Studies"))

        results = index.search("Lovelace")

        assert results
        snippet = results[0].snippets["authors"]
        assert "<b>Lovelace</b>" in snippet
        assert "Journal" not in snippet


class TestAddSkipsDocumentsAlreadyIndexed:
    def test_same_pmid_is_stored_once(self, index):
        first = index.add(_entry())
        second = index.add(_entry(title="A second copy"))

        assert second == first
        assert index.count() == 1
        assert index.get(first)["title"] == "CRISPR cancer therapy"

    def test_same_doi_without_pmid_is_stored_once(self, index):
        first = index.add(_entry(pmid=""))
        # A different source_id, so only the DOI can make it a match.
        assert index.add(_entry(pmid="", source_id="another-source")) == first
        assert index.count() == 1

    def test_same_source_id_without_pmid_or_doi_is_stored_once(self, index):
        first = index.add(_entry(pmid="", doi="", source_id="src-1"))
        assert index.add(_entry(pmid="", doi="", source_id="src-1")) == first
        assert index.count() == 1

    def test_different_pmids_are_both_stored(self, index):
        """The PMID decides when both entries have one, as in update()."""
        index.add(_entry(pmid="1"))
        index.add(_entry(pmid="2"))
        assert index.count() == 2

    def test_entries_without_identifiers_are_always_added(self, index):
        index.add(_entry(pmid="", doi="", source_id=""))
        index.add(_entry(pmid="", doi="", source_id=""))
        assert index.count() == 2

    def test_add_many_counts_only_new_documents(self, index):
        index.add(_entry(pmid="1"))
        added = index.add_many([_entry(pmid="1"), _entry(pmid="2"), _entry(pmid="2")])
        assert added == 1
        assert index.count() == 2

    def test_duplicate_is_searchable_once(self, index):
        index.add(_entry())
        index.add(_entry())
        assert len(index.search("CRISPR")) == 1

    def test_update_replaces_even_when_older_duplicates_exist(self, index):
        """An index written before add() skipped duplicates may hold two copies."""
        index._insert(_entry())
        index._insert(_entry())

        assert index.update(_entry(title="Replacement title")) is True

        titles = [hit.title for hit in index.search("CRISPR OR Replacement")]
        assert "Replacement title" in titles
