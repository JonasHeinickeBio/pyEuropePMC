"""
Local full-text indexing service using SQLite FTS5.

Provides local storage and full-text search of downloaded papers, abstracts,
and metadata using SQLite's FTS5 (Full-Text Search) extension. Supports
searching across title, abstract, and full-text content with ranking.

Requires SQLite 3.9+ (FTS5 is included in Python's sqlite3 module
on most platforms since Python 3.6+).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import sqlite3
import time
from typing import Any

from pyeuropepmc.models.literature import LiteratureResult

logger = logging.getLogger(__name__)

__all__ = [
    "FullTextIndex",
    "IndexEntry",
    "SearchResult",
    "create_index",
    "open_index",
]

_DEFAULT_INDEX_PATH = os.path.expanduser("~/.pyeuropepmc/fts_index.db")

_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    abstract,
    full_text,
    authors,
    journal,
    doi,
    pmid,
    pmcid,
    source,
    content='papers_meta',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS papers_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    abstract TEXT,
    full_text TEXT,
    authors TEXT,
    journal TEXT,
    doi TEXT,
    pmid TEXT,
    pmcid TEXT,
    source TEXT,
    source_id TEXT,
    year INTEGER,
    citation_count INTEGER DEFAULT 0,
    indexed_at REAL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS index_config (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@dataclass
class IndexEntry:
    """
    A document in the full-text index.

    Parameters
    ----------
    title : str
        Paper title.
    abstract : str, optional
        Paper abstract.
    full_text : str, optional
        Full-text content.
    authors : str, optional
        Comma-separated author names.
    journal : str, optional
        Journal name.
    doi : str, optional
        DOI.
    pmid : str, optional
        PubMed ID.
    pmcid : str, optional
        PMCID.
    source : str, optional
        Source database.
    source_id : str, optional
        ID in the source database.
    year : int, optional
        Publication year.
    citation_count : int, optional
        Citation count.
    metadata : dict, optional
        Additional metadata.
    """

    title: str = ""
    abstract: str = ""
    full_text: str = ""
    authors: str = ""
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    source: str = ""
    source_id: str = ""
    year: int | None = None
    citation_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_literature_result(cls, result: LiteratureResult) -> IndexEntry:
        """Create an IndexEntry from a LiteratureResult."""
        authors_str = ""
        if result.authors:
            authors_str = "; ".join(
                a.name
                if hasattr(a, "name")
                else (a.get("name", "") if isinstance(a, dict) else str(a))
                for a in result.authors
            )

        metadata = {}
        if result.extra_metadata:
            metadata = result.extra_metadata

        return cls(
            title=result.title or "",
            abstract=result.abstract or "",
            authors=authors_str,
            journal=result.journal or "",
            doi=result.doi or "",
            pmid=result.pmid or "",
            pmcid=result.pmcid or "",
            source=result.source,
            source_id=result.source_id,
            year=result.publication_year,
            citation_count=result.citation_count or 0,
            metadata=metadata,
        )


@dataclass
class SearchResult:
    """
    A search result from the full-text index.

    Attributes
    ----------
    rank : float
        FTS5 rank score (lower is more relevant).
    title : str
    abstract : str
    authors : str
    journal : str
    doi : str
    pmid : str
    pmcid : str
    source : str
    year : int or None
    citation_count : int
    snippets : dict[str, str]
        Highlighted snippets from matched fields.
    rowid : int
        Internal row ID.
    """

    rank: float = 0.0
    title: str = ""
    abstract: str = ""
    authors: str = ""
    journal: str = ""
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    source: str = ""
    year: int | None = None
    citation_count: int = 0
    snippets: dict[str, str] = field(default_factory=dict)
    rowid: int = 0


class FullTextIndex:
    """
    Local full-text search index for academic papers using SQLite FTS5.

    Provides persistent storage, full-text search, and retrieval of
    paper content with BM25-style ranking.

    Examples
    --------
    >>> index = FullTextIndex(":memory:")
    >>> index.add(IndexEntry(title="CRISPR cancer therapy", abstract="..."))
    >>> results = index.search("CRISPR cancer")
    >>> for r in results:
    ...     print(r.title, r.rank)
    """

    def __init__(
        self,
        db_path: str | None = None,
        create: bool = True,
    ) -> None:
        """
        Parameters
        ----------
        db_path : str, optional
            Path to SQLite database file. Defaults to ``~/.pyeuropepmc/fts_index.db``.
            Use ``:memory:`` for a temporary in-memory index.
        create : bool, optional
            Whether to create tables if they don't exist.
        """
        self.db_path = db_path or _DEFAULT_INDEX_PATH

        # Ensure directory exists
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        if create:
            self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        for statement in _SCHEMA_SQL.split(";"):
            stmt = statement.strip()
            if stmt:
                self.conn.execute(stmt)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    def add(self, entry: IndexEntry) -> int:
        """
        Add a document to the index.

        If a document with the same DOI or PMID already exists, it will
        be skipped (no duplicate detection by default — use ``update()``
        to replace).

        Parameters
        ----------
        entry : IndexEntry
            Document to index.

        Returns
        -------
        int
            Row ID of the inserted document.
        """
        meta_json = json.dumps(entry.metadata, default=str) if entry.metadata else "{}"
        cursor = self.conn.execute(
            """INSERT INTO papers_meta
               (title, abstract, full_text, authors, journal,
                doi, pmid, pmcid, source, source_id,
                year, citation_count, indexed_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.title,
                entry.abstract,
                entry.full_text,
                entry.authors,
                entry.journal,
                entry.doi,
                entry.pmid,
                entry.pmcid,
                entry.source,
                entry.source_id,
                entry.year,
                entry.citation_count,
                time.time(),
                meta_json,
            ),
        )
        rowid = cursor.lastrowid
        if rowid is None:
            raise RuntimeError("Failed to insert document into index (no rowid)")

        # Update FTS index
        self.conn.execute(
            """INSERT INTO papers_fts
               (rowid, title, abstract, full_text, authors, journal, doi, pmid, pmcid, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rowid,
                entry.title,
                entry.abstract or "",
                entry.full_text or "",
                entry.authors or "",
                entry.journal or "",
                entry.doi or "",
                entry.pmid or "",
                entry.pmcid or "",
                entry.source or "",
            ),
        )
        self.conn.commit()
        return rowid

    def add_many(self, entries: list[IndexEntry]) -> int:
        """
        Bulk-add documents to the index.

        Parameters
        ----------
        entries : list[IndexEntry]
            Documents to index.

        Returns
        -------
        int
            Number of documents added.
        """
        count = 0
        for entry in entries:
            try:
                self.add(entry)
                count += 1
            except Exception as e:
                logger.warning("Failed to index document: %s", e)
        return count

    def update(self, entry: IndexEntry) -> bool:
        """
        Update an existing document in the index, or insert if not found.

        Matches by PMID, DOI, or source_id (in that order).

        Parameters
        ----------
        entry : IndexEntry
            Updated document.

        Returns
        -------
        bool
            True if an existing document was updated.
        """
        where_clause = None
        where_value = None
        if entry.pmid:
            where_clause = "pmid = ?"
            where_value = entry.pmid
        elif entry.doi:
            where_clause = "doi = ?"
            where_value = entry.doi
        elif entry.source_id:
            where_clause = "source_id = ?"
            where_value = entry.source_id

        if where_clause and where_value:
            cursor = self.conn.execute(
                f"SELECT id FROM papers_meta WHERE {where_clause} LIMIT 1",
                (where_value,),
            )
            row = cursor.fetchone()
            if row:
                # Delete and re-insert
                self.delete(row["id"])
                self.add(entry)
                return True

        # Insert as new
        self.add(entry)
        return False

    def delete(self, rowid: int) -> bool:
        """
        Delete a document from the index.

        Parameters
        ----------
        rowid : int
            Row ID of the document.

        Returns
        -------
        bool
            True if a document with this row ID existed and was deleted.
        """
        row = self.conn.execute(
            "SELECT title, abstract, full_text, authors, journal, doi, pmid, pmcid, source"
            " FROM papers_meta WHERE id = ?",
            (rowid,),
        ).fetchone()
        if row is None:
            return False

        # FTS5's external-content "special delete" command must be given the
        # exact old column values (they identify what to remove from the FTS
        # shadow tables) — passing empty placeholders instead of the real
        # content corrupts the index (subsequent searches raise
        # "database disk image is malformed").
        self.conn.execute(
            "INSERT INTO papers_fts"
            " (papers_fts, rowid, title, abstract, full_text, authors,"
            " journal, doi, pmid, pmcid, source)"
            " VALUES ('delete', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rowid, *row),
        )
        self.conn.execute("DELETE FROM papers_meta WHERE id = ?", (rowid,))
        self.conn.commit()
        return True

    def clear(self) -> None:
        """Clear all documents from the index."""
        self.conn.execute("DELETE FROM papers_meta")
        self.conn.execute("INSERT INTO papers_fts (papers_fts) VALUES ('rebuild')")
        self.conn.commit()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 25,
        offset: int = 0,
        highlighted: bool = True,
    ) -> list[SearchResult]:
        """
        Search the full-text index.

        Supports FTS5 query syntax: AND, OR, NOT, NEAR, *, "phrase".

        Parameters
        ----------
        query : str
            Search query (FTS5 syntax supported).
        limit : int, optional
            Maximum results (default: 25).
        offset : int, optional
            Results offset for pagination.
        highlighted : bool, optional
            Whether to include highlighted snippets.

        Returns
        -------
        list[SearchResult]
            Ranked search results.
        """
        if highlighted:
            sql = """
                SELECT
                    p.rowid,
                    rank,
                    p.title,
                    p.abstract,
                    p.authors,
                    p.journal,
                    p.doi,
                    p.pmid,
                    p.pmcid,
                    p.source,
                    m.year,
                    m.citation_count,
                    snippet(papers_fts, 1, '<b>', '</b>', '...', 40) AS abstract_snippet,
                    snippet(papers_fts, 0, '<b>', '</b>', '...', 40) AS title_snippet,
                    snippet(papers_fts, 4, '<b>', '</b>', '...', 40) AS authors_snippet
                FROM papers_fts p
                JOIN papers_meta m ON p.rowid = m.id
                WHERE papers_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT
                    p.rowid, rank,
                    m.title, m.abstract, m.authors, m.journal,
                    m.doi, m.pmid, m.pmcid, m.source,
                    m.year, m.citation_count
                FROM papers_fts p
                JOIN papers_meta m ON p.rowid = m.id
                WHERE papers_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """

        try:
            cursor = self.conn.execute(sql, (query, limit, offset))
        except sqlite3.OperationalError as e:
            logger.error("FTS5 query error: %s (query: %s)", e, query)
            return []

        results: list[SearchResult] = []
        for row in cursor.fetchall():
            sr = SearchResult(
                rank=row["rank"],
                title=row["title"] or "",
                abstract=row["abstract"] or "",
                authors=row["authors"] or "",
                journal=row["journal"] or "",
                doi=row["doi"] or "",
                pmid=row["pmid"] or "",
                pmcid=row["pmcid"] or "",
                source=row["source"] or "",
                year=row["year"],
                citation_count=row["citation_count"] or 0,
                rowid=row["rowid"],
            )
            if highlighted:
                # Safe access with dict expansion for sqlite3.Row objects
                row_dict = dict(row)
                sr.snippets = {
                    "title": row_dict.get("title_snippet", ""),
                    "abstract": row_dict.get("abstract_snippet", ""),
                    "authors": row_dict.get("authors_snippet", ""),
                }
            results.append(sr)

        return results

    def count(self, query: str | None = None) -> int:
        """Count documents in the index, optionally matching a query."""
        if query:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM papers_fts WHERE papers_fts MATCH ?",
                (query,),
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM papers_meta")
        count: int = cursor.fetchone()[0]
        return count

    def get(self, rowid: int) -> dict[str, Any] | None:
        """Get a document by row ID."""
        cursor = self.conn.execute(
            "SELECT * FROM papers_meta WHERE id = ?",
            (rowid,),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get("metadata_json"):
                try:
                    result["metadata"] = json.loads(result["metadata_json"])
                except json.JSONDecodeError:
                    result["metadata"] = {}
            return result
        return None

    def get_by_doi(self, doi: str) -> dict[str, Any] | None:
        """Look up a document by DOI."""
        cursor = self.conn.execute(
            "SELECT id FROM papers_meta WHERE doi = ? LIMIT 1",
            (doi,),
        )
        row = cursor.fetchone()
        if row:
            return self.get(row["id"])
        return None

    def get_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        """Look up a document by PMID."""
        cursor = self.conn.execute(
            "SELECT id FROM papers_meta WHERE pmid = ? LIMIT 1",
            (pmid,),
        )
        row = cursor.fetchone()
        if row:
            return self.get(row["id"])
        return None

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Get index statistics."""
        total = self.count()
        source_dist: dict[str, int] = {}
        cursor = self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM papers_meta GROUP BY source"
        )
        for row in cursor.fetchall():
            source_dist[row["source"]] = row["cnt"]

        return {
            "total_documents": total,
            "source_distribution": source_dist,
            "db_path": self.db_path,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> FullTextIndex:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------


def create_index(db_path: str | None = None) -> FullTextIndex:
    """
    Create and return a new full-text index.

    Parameters
    ----------
    db_path : str, optional
        Path to SQLite database file.

    Returns
    -------
    FullTextIndex
    """
    return FullTextIndex(db_path=db_path, create=True)


def open_index(db_path: str | None = None) -> FullTextIndex:
    """
    Open an existing full-text index.

    Parameters
    ----------
    db_path : str, optional
        Path to SQLite database file.

    Returns
    -------
    FullTextIndex
    """
    return FullTextIndex(db_path=db_path, create=False)
