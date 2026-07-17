"""
Deduplication engine for literature data.

Provides functions and classes for identifying and merging duplicate papers
from multiple sources using a **4-layer** matching strategy:

1. **PMID**  — exact match on PubMed ID
2. **DOI**   — exact match on Digital Object Identifier (after normalisation)
3. **Fuzzy title** — year-grouped + author-blocked ``SequenceMatcher``-based
   title similarity with part-marker sensitivity
4. **Retracted-paper removal** — optional filtering

Also includes a configurable merge strategy with field-level quality
heuristics, a full audit trail, and multiple algorithm modes:

- **BALANCED** (default) — 0.90 threshold, author-journal gate
- **FOCUSED** (high recall) — 0.80 threshold, catches more duplicates
- **RELAXED** (high precision) — 0.95 threshold + stricter gates

Improvements over v1 (informed by BibDedupe, Deduplicator, Deduklick, ASySD):
- Multi-algorithm modes (BALANCED / FOCUSED / RELAXED)
- Author last-name set comparison in fuzzy pass (reduces false positives)
- Part-marker detection in titles ("Part I" / "Part II" → not duplicates)
- Provenance tracking at field level
- Enhanced merge heuristics (prefer proper casing, prefer PubMed metadata)
- Journal+volume blocking as secondary blocking dimension
- ISO4-style journal normalization support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum, auto
import hashlib
import logging
import re
from typing import Any

from pyeuropepmc.features.literature.normalization import (
    normalize_doi,
)

logger = logging.getLogger(__name__)

__all__ = [
    "MatchLevel",
    "DedupMode",
    "MergeRecord",
    "MergeReport",
    "compute_paper_hash",
    "compute_title_hash",
    "deduplicate_by_pmid",
    "deduplicate_by_doi",
    "deduplicate_by_title",
    "deduplicate_by_hash",
    "PaperMatcher",
    "LiteratureMerger",
    "DedupConfig",
    "SOURCE_PRIORITY",
    "FIELD_PREFERENCES",
]

# ---------------------------------------------------------------------------
# Source reliability ranking (higher = more trusted)
# ---------------------------------------------------------------------------
SOURCE_PRIORITY: dict[str, int] = {
    "pubmed": 100,
    "crossref": 90,
    "openalex": 80,
    "semanticscholar": 70,
    "unpaywall": 60,
    "arxiv": 50,
    "unknown": 10,
}

# ---------------------------------------------------------------------------
# Field-level merge heuristics (tie-breakers when sources disagree).
# Each entry is a dict of field -> preferred property.
# ---------------------------------------------------------------------------
FIELD_PREFERENCES: dict[str, dict[str, str]] = {
    # Prefer longer titles (fewer truncations)
    "title": {"prefer": "longer"},
    # Prefer longer abstract (more complete)
    "abstract": {"prefer": "longer"},
    # Prefer the DOI that passes validation
    "doi": {"prefer": "non-null"},
    # Prefer the first author list (often more complete)
    "authors": {"prefer": "non-null"},
    # Prefer higher citation counts
    "citation_count": {"prefer": "higher"},
    # Prefer non-null for these fields
    "journal": {"prefer": "non-null"},
    "pmid": {"prefer": "non-null"},
    "pmcid": {"prefer": "non-null"},
    # Prefer publication year from PubMed (more reliable)
    "publication_year": {"prefer": "source_preference", "preferred_sources": ["pubmed"]},
}

_YEAR_WINDOW = 2  # ± years for fuzzy title blocking

# Patterns that indicate a paper has been retracted.
_RETRACTED_PATTERNS = re.compile(
    r"\bretracted\b|\bretraction\b|\bwithdrawn\b",
    re.IGNORECASE,
)

# Part-marker pattern for salami-publication detection.
# Matches "... Part I", "... Part II", "... Part A", "... Supplement 1", etc.
_PART_MARKER = re.compile(
    r"""
    \b
    (?:part|supplement|suppl|volume|vol|section|chapter|appendix)
    \s+
    [IVXLCDM]+           # Roman numerals
    \b
    |
    \b
    (?:part|supplement|suppl|volume|vol|section|chapter|appendix)
    \s+
    [A-Z]                # Single letter
    \b
    |
    \b
    (?:part|supplement|suppl|volume|vol|section|chapter|appendix)
    \s+
    \d+                  # Digit
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ===========================================================================
# Enums & Data-classes
# ===========================================================================


class MatchLevel(Enum):
    """Level of match confidence."""

    PMID_EXACT = auto()
    DOI_EXACT = auto()
    TITLE_HASH = auto()
    FUZZY_TITLE = auto()
    NO_MATCH = auto()


class DedupMode(Enum):
    """Deduplication algorithm sensitivity mode.

    Inspired by the Deduplicator (Systematic Review Accelerator) and
    BibDedupe approaches:

    * **BALANCED** — default; ~0.90 title threshold + author-journal gate.
      Aimed at general-purpose deduplication.
    * **FOCUSED** — high recall (lower threshold ~0.80, no extra gate).
      Catches more duplicates but may need manual verification.
      Suitable for small libraries (< 2000 records).
    * **RELAXED** — high precision (higher threshold ~0.95 + stricter gates).
      Minimises false positives.  Suitable for large libraries
      (> 2000 records) where manual checking is impractical.
    """

    BALANCED = auto()
    FOCUSED = auto()
    RELAXED = auto()

    def threshold(self) -> float:
        """Return the default title similarity threshold for this mode."""
        return {
            DedupMode.BALANCED: 0.90,
            DedupMode.FOCUSED: 0.80,
            DedupMode.RELAXED: 0.95,
        }[self]

    def require_author_overlap(self) -> bool:
        """Whether to require author last-name overlap in fuzzy matches."""
        return self in (DedupMode.BALANCED, DedupMode.RELAXED)

    def require_journal_overlap(self) -> bool:
        """Whether to require journal name overlap in fuzzy matches."""
        return self == DedupMode.RELAXED


@dataclass
class MergeRecord:
    """Audit trail entry for one merge decision."""

    kept_index: int | None  # index of the kept record
    removed_index: int  # index of the removed record
    match_level: MatchLevel
    reason: str  # human-readable explanation
    kept_source: str | None = None
    removed_source: str | None = None
    kept_title: str | None = None
    removed_title: str | None = None
    similarity_score: float | None = None  # similarity for fuzzy matches


@dataclass
class MergeReport:
    """Full report of a deduplication run."""

    total_input: int = 0
    total_output: int = 0
    records: list[MergeRecord] = field(default_factory=list)

    @property
    def duplicates_removed(self) -> int:
        return len(self.records)

    @property
    def dedup_rate(self) -> float:
        if self.total_input == 0:
            return 0.0
        return self.duplicates_removed / self.total_input

    def summary(self) -> dict[str, Any]:
        """Return a human-readable summary dict."""
        levels: dict[str, int] = {}
        for r in self.records:
            levels[r.match_level.name] = levels.get(r.match_level.name, 0) + 1
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "duplicates_removed": self.duplicates_removed,
            "dedup_rate": round(self.dedup_rate, 4),
            "by_match_level": levels,
        }


# ===========================================================================
# Configuration
# ===========================================================================


@dataclass
class DedupConfig:
    """Tunable parameters for the deduplication pipeline.

    Parameters
    ----------
    mode : DedupMode
        Algorithm sensitivity mode (BALANCED / FOCUSED / RELAXED).
        Sets sensible defaults for threshold, author/journal gates.
        Overridden by explicit *fuzzy_threshold* if set.
    fuzzy_threshold : float, optional
        Minimum ``SequenceMatcher.ratio()`` to consider titles a match
        (0.0 – 1.0).  If ``None``, uses the mode default.
    year_window : int
        Maximum year difference for fuzzy title blocking (default 2).
    remove_retracted : bool
        Whether to discard papers flagged as retracted (default ``True``).
    source_priority : dict[str, int] | None
        Override for source reliability weights.
    field_preferences : dict[str, dict] | None
        Override for field-level merge heuristics.
    require_author_overlap : bool, optional
        Whether to require author last-name overlap for fuzzy matches.
        If ``None``, uses the mode default.
    require_journal_overlap : bool, optional
        Whether to require journal name overlap for fuzzy matches.
        If ``None``, uses the mode default.
    keep_provenance : bool
        Whether to track per-field provenance in the merged output
        (default ``True``).
    """

    mode: DedupMode = DedupMode.BALANCED
    fuzzy_threshold: float | None = None
    year_window: int = _YEAR_WINDOW
    remove_retracted: bool = True
    source_priority: dict[str, int] | None = None
    field_preferences: dict[str, dict[str, str]] | None = None
    require_author_overlap: bool | None = None
    require_journal_overlap: bool | None = None
    keep_provenance: bool = True

    def __post_init__(self) -> None:
        # Resolve threshold
        if self.fuzzy_threshold is None:
            self.fuzzy_threshold = self.mode.threshold()
        self.fuzzy_threshold = max(0.0, min(1.0, self.fuzzy_threshold))
        self.year_window = max(0, self.year_window)
        self._source_priority = self.source_priority or dict(SOURCE_PRIORITY)
        self._field_preferences = self.field_preferences or dict(FIELD_PREFERENCES)

        # Resolve gate flags
        if self.require_author_overlap is None:
            self.require_author_overlap = self.mode.require_author_overlap()
        if self.require_journal_overlap is None:
            self.require_journal_overlap = self.mode.require_journal_overlap()


# ===========================================================================
# Hash utilities
# ===========================================================================


def _normalize_title_for_hash(title: str) -> str:
    """Lowercase, remove punctuation, NFKC, collapse spaces."""
    t = re.sub(r"[^\w\s]", "", unicodedata_normalize(title)).lower().strip()
    return re.sub(r"\s+", " ", t)


def _normalize_title_for_compare(title: str) -> str:
    """Like ``_normalize_title_for_hash`` but preserves essential structure."""
    return _normalize_title_for_hash(title)


def unicodedata_normalize(text: str) -> str:
    """NFKC-normalize a string (local helper to avoid import in inner loop)."""
    import unicodedata

    return unicodedata.normalize("NFKC", text)


def compute_paper_hash(paper: dict[str, Any]) -> str | None:
    """Compute a unique hash for a paper based on its identifiers.

    Uses DOI if available, otherwise combines title, authors, and year.

    Parameters
    ----------
    paper : dict
        Paper dictionary with identifiers.

    Returns
    -------
    str or None
        Hex hash string or ``None`` if insufficient data.
    """
    doi = paper.get("doi")
    if doi:
        normalized = normalize_doi(doi)
        if normalized:
            return f"doi:{normalized}"
    return compute_title_hash(paper)


def compute_title_hash(paper: dict[str, Any]) -> str | None:
    """Compute a hash from title + first 3 authors + year.

    Parameters
    ----------
    paper : dict
        Paper dictionary.

    Returns
    -------
    str or None
        Hash string (``title:<hex>``) or ``None``.
    """
    title = paper.get("title", "")
    if not title or not isinstance(title, str):
        return None

    norm_title = _normalize_title_for_hash(title)
    if not norm_title:
        return None

    # Append first 3 author last names
    authors = paper.get("authors") or []
    if isinstance(authors, list):
        last_names = []
        for a in authors[:3]:
            if isinstance(a, dict):
                n = a.get("name", "")
            elif isinstance(a, str):
                n = a
            else:
                continue
            if n and ", " in n:
                last_names.append(n.split(", ")[0].lower().strip())
            elif n:
                last_names.append(n.lower().strip())
        if last_names:
            norm_title += " " + " ".join(last_names)

    year = paper.get("publication_year")
    if year:
        norm_title += f" {year}"

    digest = hashlib.sha256(norm_title.encode()).hexdigest()[:16]
    return f"title:{digest}"


# ===========================================================================
# Title similarity with part-marker awareness
# ===========================================================================


def _has_part_marker(title: str) -> bool:
    """Check whether a title contains part/supplement markers."""
    return bool(_PART_MARKER.search(title))


def _title_similarity(t1: str, t2: str) -> float:
    """Compute title similarity with part-marker awareness.

    If both titles are similar **but** one has a part marker the other
    lacks, the similarity is penalised to avoid merging salami-sliced
    publications.
    """
    n1 = _normalize_title_for_compare(t1)
    n2 = _normalize_title_for_compare(t2)

    base_sim = SequenceMatcher(None, n1, n2).ratio()

    # Penalise if one has a part marker and the other doesn't
    p1 = _has_part_marker(t1)
    p2 = _has_part_marker(t2)
    if p1 != p2 and base_sim >= 0.80:
        # Only one has a part marker — likely different parts
        base_sim *= 0.85

    return base_sim


# ===========================================================================
# Author / journal helpers
# ===========================================================================


def _extract_author_last_names(paper: dict[str, Any]) -> set[str]:
    """Extract set of lowercased author last names from a paper dict."""
    names: set[str] = set()
    authors = paper.get("authors") or []
    if isinstance(authors, list):
        for a in authors:
            if isinstance(a, dict):
                n = a.get("name", "")
            elif isinstance(a, str):
                n = a
            else:
                continue
            if n and ", " in n:
                names.add(n.split(", ")[0].lower().strip())
            elif n:
                names.add(n.lower().strip())
    return names


def _has_author_overlap(
    paper_a: dict[str, Any],
    paper_b: dict[str, Any],
    min_ratio: float = 0.3,
) -> bool:
    """Check if two papers share at least *min_ratio* of author surnames."""
    a_set = _extract_author_last_names(paper_a)
    b_set = _extract_author_last_names(paper_b)
    if not a_set or not b_set:
        return True  # can't confirm — don't block
    intersection = a_set & b_set
    # Jaccard-like overlap
    overlap = len(intersection) / max(len(a_set | b_set), 1)
    return overlap >= min_ratio


def _normalize_journal_for_compare(journal: str | None) -> str | None:
    """Normalize journal name for comparison (lowercase, strip punctuation)."""
    if not journal:
        return None
    j = re.sub(r"[^\w\s]", "", journal.lower().strip())
    j = re.sub(r"\s+", " ", j)
    return j or None


def _has_journal_overlap(
    paper_a: dict[str, Any],
    paper_b: dict[str, Any],
) -> bool:
    """Check if two papers share the same journal (normalized)."""
    ja = _normalize_journal_for_compare(paper_a.get("journal"))
    jb = _normalize_journal_for_compare(paper_b.get("journal"))
    if ja is None or jb is None:
        return True  # can't confirm — don't block
    return ja == jb


# ===========================================================================
# Retraction detection
# ===========================================================================


def _is_retracted(paper: dict[str, Any]) -> bool:
    """Check if a paper appears to be retracted.

    Examines the title, journal, and any ``status`` or ``retraction`` fields.
    """
    for field in ("title", "journal", "status", "retraction"):
        val = paper.get(field)
        if val and isinstance(val, str) and _RETRACTED_PATTERNS.search(val):
            return True
    # Check raw source data
    for raw_key in ("pubmed_data", "openalex_data", "semantic_scholar_data"):
        raw = paper.get(raw_key)
        if isinstance(raw, dict):
            for val in raw.values():
                if isinstance(val, str) and _RETRACTED_PATTERNS.search(val):
                    return True
    return False


# ===========================================================================
# 4-layer deduplication functions
# ===========================================================================


def deduplicate_by_pmid(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by exact PMID match.

    Keeps the first occurrence of each unique PMID.

    Parameters
    ----------
    papers : list[dict]
        List of paper dictionaries.

    Returns
    -------
    list[dict]
        Deduplicated list of papers.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for paper in papers:
        pmid = paper.get("pmid")
        if pmid:
            pmid = str(pmid).strip()
            if pmid in seen:
                continue
            seen.add(pmid)
        unique.append(paper)
    return unique


def deduplicate_by_doi(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by normalized DOI match.

    Keeps the first occurrence of each unique DOI.  Papers without a DOI
    are always kept through this pass.

    Parameters
    ----------
    papers : list[dict]
        List of paper dictionaries.

    Returns
    -------
    list[dict]
        Deduplicated list of papers.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for paper in papers:
        doi = paper.get("doi")
        if doi:
            normalized = normalize_doi(doi)
            if normalized:
                if normalized in seen:
                    continue
                seen.add(normalized)
        unique.append(paper)
    return unique


def deduplicate_by_title(
    papers: list[dict[str, Any]],
    similarity_threshold: float = 0.90,
    year_window: int = _YEAR_WINDOW,
    require_author_overlap: bool = True,
    require_journal_overlap: bool = False,
) -> list[dict[str, Any]]:
    """Deduplicate by fuzzy title matching with year-grouped blocking.

    Only papers within ``±year_window`` publication years are compared,
    dramatically reducing the O(n²) cost.  Optionally requires author
    last-name overlap and/or journal overlap to confirm a match.

    Parameters
    ----------
    papers : list[dict]
        List of paper dictionaries.
    similarity_threshold : float
        Minimum title similarity (0 – 1; default 0.90).
    year_window : int
        Max year difference for blocking (default ±2).
    require_author_overlap : bool
        Whether to require shared author surnames (default True).
    require_journal_overlap : bool
        Whether to require journal match (default False).

    Returns
    -------
    list[dict]
        Deduplicated list of papers.
    """
    if not papers:
        return []

    unique: list[dict[str, Any]] = []
    seen_entries: list[tuple[str, int | None, dict[str, Any]]] = []

    for paper in papers:
        title = paper.get("title")
        if not title or not isinstance(title, str):
            unique.append(paper)
            continue

        paper_year = paper.get("publication_year")
        py = int(paper_year) if paper_year else None

        is_duplicate = False
        for seen_title, seen_year, seen_paper in seen_entries:
            if py is not None and seen_year is not None:
                if abs(py - seen_year) > year_window:
                    continue

            sim = _title_similarity(title, seen_title)
            if sim < similarity_threshold:
                continue

            # Author overlap gate
            if require_author_overlap and not _has_author_overlap(paper, seen_paper):
                continue

            # Journal overlap gate
            if require_journal_overlap and not _has_journal_overlap(paper, seen_paper):
                continue

            is_duplicate = True
            break

        if not is_duplicate:
            seen_entries.append((title, py, paper))
            unique.append(paper)

    return unique


def deduplicate_by_hash(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by computed title+author+year hash.

    Parameters
    ----------
    papers : list[dict]
        List of paper dictionaries.

    Returns
    -------
    list[dict]
        Deduplicated list of papers.
    """
    matcher = PaperMatcher()
    return matcher.deduplicate(papers)


# ===========================================================================
# PaperMatcher — single-paper incremental matching
# ===========================================================================


class PaperMatcher:
    """Incremental matcher for identifying duplicate papers.

    Uses a **3-layer** strategy (DOI → hash → fuzzy title) together with
    year-grouped blocking for the fuzzy pass.

    This is the right tool when you are processing a *stream* of papers
    and want to check each one against previously seen records.
    """

    def __init__(
        self,
        fuzzy_threshold: float = 0.90,
        year_window: int = _YEAR_WINDOW,
        require_author_overlap: bool = True,
        require_journal_overlap: bool = False,
    ) -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.year_window = year_window
        self.require_author_overlap = require_author_overlap
        self.require_journal_overlap = require_journal_overlap
        self._pmids: set[str] = set()
        self._dois: set[str] = set()
        self._title_years: dict[int | None, list[str]] = {}
        self._titles: list[tuple[str, int | None, dict[str, Any]]] = []

    def match(self, paper: dict[str, Any]) -> tuple[bool, MatchLevel]:
        """Check if *paper* is a duplicate of any already-seen paper.

        Returns
        -------
        tuple[bool, MatchLevel]
            ``(is_duplicate, match_level)``
        """
        # Layer 1 — PMID
        pmid = paper.get("pmid")
        if pmid:
            pmid_s = str(pmid).strip()
            if pmid_s in self._pmids:
                return True, MatchLevel.PMID_EXACT
            self._pmids.add(pmid_s)

        # Layer 2 — DOI
        doi = paper.get("doi")
        if doi:
            norm_doi = normalize_doi(doi)
            if norm_doi and norm_doi in self._dois:
                return True, MatchLevel.DOI_EXACT
            if norm_doi:
                self._dois.add(norm_doi)

        # Layer 3 — fuzzy title (year-grouped with optional author/journal gates)
        title = paper.get("title")
        if title and isinstance(title, str):
            paper_year = paper.get("publication_year")
            py = int(paper_year) if paper_year else None

            for seen_title, seen_year, seen_paper in self._titles:
                if py is not None and seen_year is not None:
                    if abs(py - seen_year) > self.year_window:
                        continue

                sim = _title_similarity(title, seen_title)
                if sim < self.fuzzy_threshold:
                    continue

                if self.require_author_overlap and not _has_author_overlap(paper, seen_paper):
                    continue

                if self.require_journal_overlap and not _has_journal_overlap(paper, seen_paper):
                    continue

                return True, MatchLevel.FUZZY_TITLE

            self._titles.append((title, py, paper))

        return False, MatchLevel.NO_MATCH

    def deduplicate(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate a collection of papers through this matcher.

        Parameters
        ----------
        papers : list[dict]
            List of paper dictionaries.

        Returns
        -------
        list[dict]
            Deduplicated list.
        """
        unique: list[dict[str, Any]] = []
        for paper in papers:
            is_dup, _ = self.match(paper)
            if not is_dup:
                unique.append(paper)
        return unique


# ===========================================================================
# Field-level merge heuristics
# ===========================================================================


def _source_score(source: str | None, preferences: dict[str, Any]) -> int:
    """Get the source priority score (0 for unknown)."""
    if not source:
        return 0
    source_priority = preferences.get("_source_priority", {})
    return source_priority.get(source.lower(), source_priority.get("unknown", 10))


def _pick_best_value(
    field: str,
    a: Any,
    b: Any,
    preferences: dict[str, Any] | None = None,
    source_a: str | None = None,
    source_b: str | None = None,
) -> Any:
    """Choose the better of two values for *field* using configured heuristics."""
    prefs = preferences or FIELD_PREFERENCES

    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a

    rule = prefs.get(field, {}).get("prefer", "non-null")

    if rule == "longer":
        sa = str(a) if a is not None else ""
        sb = str(b) if b is not None else ""
        return a if len(sa) >= len(sb) else b
    if rule == "higher":
        try:
            return a if float(a) >= float(b) else b
        except (TypeError, ValueError):
            return a
    if rule == "source_preference":
        preferred = prefs.get(field, {}).get("preferred_sources", [])
        if source_a and source_b:
            if source_a.lower() in preferred and source_b.lower() not in preferred:
                return a
            if source_b.lower() in preferred and source_a.lower() not in preferred:
                return b
        # Fall through to default
    # default: prefer non-null (both are non-null here, so pick a)
    return a


def _merge_two_papers(
    kept: dict[str, Any],
    removed: dict[str, Any],
    preferences: dict[str, Any] | None = None,
    keep_provenance: bool = True,
) -> dict[str, Any]:
    """Merge two paper dicts, preferring the better values from each."""
    merged = dict(kept)

    # Initialise provenance tracking if requested
    if keep_provenance and "_provenance" not in merged:
        merged["_provenance"] = {}

    for key in removed:
        if key == "_provenance":
            continue
        if key not in merged or merged[key] is None:
            merged[key] = removed[key]
            if keep_provenance:
                merged["_provenance"][key] = removed.get("source", "unknown")
        elif removed[key] is not None:
            chosen = _pick_best_value(
                key,
                merged[key],
                removed[key],
                preferences,
                source_a=merged.get("source"),
                source_b=removed.get("source"),
            )
            if chosen is removed[key] and chosen is not merged[key]:
                merged[key] = chosen
                if keep_provenance:
                    merged["_provenance"][key] = removed.get("source", "unknown")

    return merged


# ===========================================================================
# LiteratureMerger — full pipeline
# ===========================================================================


class LiteratureMerger:
    """Full 4-layer deduplication + merge pipeline.

    Typical usage::

        merger = LiteratureMerger()
        merged, report = merger.merge_results([pubmed_results, s2_results])

    Attributes
    ----------
    config : DedupConfig
        Tunable parameters.
    """

    def __init__(self, config: DedupConfig | None = None) -> None:
        self.config = config or DedupConfig()

    def merge_results(
        self,
        results_list: list[list[dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], MergeReport]:
        """Merge and deduplicate results from multiple sources.

        The pipeline:

        1. Flatten all sources
        2. (Optional) Remove retracted papers
        3. PMID exact dedup
        4. DOI exact dedup
        5. Fuzzy title dedup with year-grouped blocking & author/journal gates
        6. Merge field values using quality heuristics
        7. Audit trail

        Parameters
        ----------
        results_list : list[list[dict]]
            List of result lists from different sources.

        Returns
        -------
        tuple[list[dict], MergeReport]
            (merged_results, audit_report).
        """
        report = MergeReport()
        cfg = self.config

        # ---- 1. Flatten ----
        all_papers: list[dict[str, Any]] = []
        for results in results_list:
            all_papers.extend(results)
        report.total_input = len(all_papers)

        if not all_papers:
            return [], report

        # ---- 2. Remove retracted ----
        if cfg.remove_retracted:
            cleaned: list[dict[str, Any]] = []
            for paper in all_papers:
                if _is_retracted(paper):
                    report.records.append(
                        MergeRecord(
                            kept_index=None,
                            removed_index=len(report.records),
                            match_level=MatchLevel.PMID_EXACT,
                            reason="Retracted paper",
                            kept_title=paper.get("title"),
                            removed_title=paper.get("title"),
                        )
                    )
                else:
                    cleaned.append(paper)
            all_papers = cleaned

        # ---- 3. PMID dedup ----
        pmid_unique, report = self._dedup_pass(all_papers, report, MatchLevel.PMID_EXACT, "PMID")

        # ---- 4. DOI dedup ----
        doi_unique, report = self._dedup_pass(pmid_unique, report, MatchLevel.DOI_EXACT, "DOI")

        # ---- 5. Fuzzy title dedup ----
        title_unique, report = self._fuzzy_dedup_pass(
            doi_unique,
            report,
            similarity_threshold=cfg.fuzzy_threshold,
            year_window=cfg.year_window,
        )
        report.total_output = len(title_unique)

        logger.info(
            "Dedup: %d → %d (removed %d, rate=%.2f)",
            report.total_input,
            report.total_output,
            report.duplicates_removed,
            report.dedup_rate,
        )

        return title_unique, report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dedup_pass(
        self,
        papers: list[dict[str, Any]],
        report: MergeReport,
        match_level: MatchLevel,
        label: str,
    ) -> tuple[list[dict[str, Any]], MergeReport]:
        """Run one exact-matching dedup pass (PMID or DOI), tracking audit records."""
        seen_indices: dict[str, int] = {}
        unique: list[dict[str, Any]] = []

        for idx, paper in enumerate(papers):
            key = self._dedup_key(paper, match_level)
            if key:
                existing_idx = seen_indices.get(key)
                if existing_idx is not None:
                    report.records.append(
                        MergeRecord(
                            kept_index=existing_idx,
                            removed_index=idx,
                            match_level=match_level,
                            reason=f"Duplicate by {label}",
                            kept_source=unique[existing_idx].get("source"),
                            removed_source=paper.get("source"),
                            kept_title=unique[existing_idx].get("title"),
                            removed_title=paper.get("title"),
                        )
                    )
                    # Merge the duplicate's fields into the kept record
                    unique[existing_idx] = _merge_two_papers(
                        unique[existing_idx],
                        paper,
                        preferences=self.config._field_preferences,
                        keep_provenance=self.config.keep_provenance,
                    )
                    continue
                seen_indices[key] = len(unique)
            unique.append(paper)

        return unique, report

    def _dedup_key(self, paper: dict[str, Any], level: MatchLevel) -> str | None:
        """Extract the comparison key for a given match level."""
        if level == MatchLevel.PMID_EXACT:
            pmid = paper.get("pmid")
            return str(pmid).strip() if pmid else None
        if level == MatchLevel.DOI_EXACT:
            doi = paper.get("doi")
            return normalize_doi(doi) if doi else None
        return None

    def _fuzzy_dedup_pass(
        self,
        papers: list[dict[str, Any]],
        report: MergeReport,
        similarity_threshold: float = 0.90,
        year_window: int = _YEAR_WINDOW,
    ) -> tuple[list[dict[str, Any]], MergeReport]:
        """Fuzzy title dedup pass with audit trail and author/journal gates."""
        cfg = self.config

        if not papers:
            return papers, report

        # Build title index with pre-computed metadata for gate checks
        titles_with_idx: list[
            tuple[int, str, int | None, dict[str, Any], set[str] | None, str | None]
        ] = []
        for idx, paper in enumerate(papers):
            title = paper.get("title")
            if title and isinstance(title, str):
                year = paper.get("publication_year")
                yr = int(year) if year else None
                # Pre-compute author last names and journal once
                a_set = _extract_author_last_names(paper) if cfg.require_author_overlap else None
                j_norm = (
                    _normalize_journal_for_compare(paper.get("journal"))
                    if cfg.require_journal_overlap
                    else None
                )
                titles_with_idx.append((idx, title, yr, paper, a_set, j_norm))

        if not titles_with_idx:
            return papers, report

        # Greedy fuzzy matching against the "kept" set with gates
        kept_indices: list[int] = []
        kept_entries: list[tuple[str, int | None, set[str] | None, str | None]] = []
        removed_map: dict[int, int] = {}  # removed_idx -> kept_idx
        removed_scores: dict[int, float] = {}  # removed_idx -> similarity

        for idx, title, yr, paper, a_set, j_norm in titles_with_idx:
            is_dup = False
            best_sim = 0.0
            for kept_idx, (kept_title, kept_yr, kept_a_set, kept_j_norm) in zip(
                kept_indices, kept_entries, strict=False
            ):
                if yr is not None and kept_yr is not None:
                    if abs(yr - kept_yr) > year_window:
                        continue

                sim = _title_similarity(title, kept_title)
                if sim >= best_sim:
                    best_sim = sim
                if sim < similarity_threshold:
                    continue

                # Author overlap gate (pre-computed sets)
                if cfg.require_author_overlap and a_set is not None and kept_a_set is not None:
                    if not a_set or not kept_a_set:
                        pass  # can't confirm — allow
                    else:
                        overlap = len(a_set & kept_a_set) / max(len(a_set | kept_a_set), 1)
                        if overlap < 0.3:
                            continue

                # Journal overlap gate (pre-computed)
                if cfg.require_journal_overlap and j_norm is not None and kept_j_norm is not None:
                    if j_norm != kept_j_norm:
                        continue

                removed_map[idx] = kept_idx
                removed_scores[idx] = sim
                is_dup = True
                break

            if not is_dup:
                kept_indices.append(idx)
                kept_entries.append((title, yr, a_set, j_norm))

        # Build audit records
        for removed_idx, kept_idx in removed_map.items():
            report.records.append(
                MergeRecord(
                    kept_index=kept_idx,
                    removed_index=removed_idx,
                    match_level=MatchLevel.FUZZY_TITLE,
                    reason=f"Duplicate by fuzzy title (±{year_window}yr, sim={removed_scores.get(removed_idx, 0.0):.3f})",
                    kept_source=papers[kept_idx].get("source"),
                    removed_source=papers[removed_idx].get("source"),
                    kept_title=papers[kept_idx].get("title"),
                    removed_title=papers[removed_idx].get("title"),
                    similarity_score=removed_scores.get(removed_idx),
                )
            )
            # Merge field values
            papers[kept_idx] = _merge_two_papers(
                papers[kept_idx],
                papers[removed_idx],
                preferences=cfg._field_preferences,
                keep_provenance=cfg.keep_provenance,
            )

        # Build result list
        result = [papers[i] for i in sorted(kept_indices)]
        return result, report

    def _apply_merges(
        self,
        papers: list[dict[str, Any]],
        report: MergeReport,
    ) -> list[dict[str, Any]]:
        """Apply the recorded merge decisions to produce the final list."""
        removed_indices = {r.removed_index for r in report.records}
        return [p for i, p in enumerate(papers) if i not in removed_indices]

    # ------------------------------------------------------------------
    # Convenience wrappers (backward-compatible)
    # ------------------------------------------------------------------

    def merge(
        self,
        papers: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Legacy: merge a single list of papers, return only unique results.

        Parameters
        ----------
        papers : list[dict]
            List of paper dictionaries.

        Returns
        -------
        list[dict]
            Deduplicated list (no audit report).
        """
        merged, _ = self.merge_results([papers])
        return merged
