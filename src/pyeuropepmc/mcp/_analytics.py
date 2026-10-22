"""Aggregates over a Europe PMC search, labelled by how they were obtained.

Europe PMC can count the records that match a query without returning them, and a count is
exact however large the result set is. Everything it cannot count (which journals, which
authors, which countries) has to be read off records, and at most ``limit`` records are
fetched. So every metric here carries a ``basis``:

``exact``
    Counted by Europe PMC over the whole result set (``by_year``, ``open_access`` and the
    citation thresholds), or computed from records when the fetched records are the whole
    result set.
``sample``
    Computed from the first ``limit`` records of the search, in the order the search gave
    them. It describes those records and says so; it is never offered as the complete result.

The counting helpers take the ``count`` function they are given (query in, hit count out), so
this module makes no request itself and is tested with a fake. The sample summaries need
``pandas`` and ``numpy`` (the ``analytics`` extra); the counts do not.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import re
from typing import Any

METRICS = (
    "by_year",
    "citations",
    "journals",
    "authors",
    "types",
    "countries",
    "open_access",
    "funders",
)
#: Metrics Europe PMC counts itself, whatever the size of the result set.
COUNTED = frozenset({"by_year", "open_access"})
#: Metrics read off fetched records: these need the ``analytics`` extra.
FROM_RECORDS = frozenset({"citations", "journals", "authors", "types", "countries", "funders"})
#: Metrics whose records need the ``core`` result type (``lite`` has no affiliations or grants).
NEEDS_CORE = frozenset({"countries", "funders"})

CITATION_THRESHOLDS = (1, 10, 100, 1000)
#: Years counted one by one; a longer span is counted for its latest years plus one bucket
#: for everything earlier, so that the total is still exact.
MAX_YEARS = 60
WORKERS = 6
DEFAULT_TOP = 10

Count = Callable[[str], int]
#: ``edge(query, "asc" | "desc")``: the first publication year of the oldest/newest record.
Edge = Callable[[str, str], int | None]


def check_metrics(requested: list[str] | None) -> list[str]:
    """The metrics to compute, in the order asked for and without repeats; all when none given."""
    if not requested:
        return list(METRICS)
    unknown = [m for m in requested if m not in METRICS]
    if unknown:
        raise ValueError(f"unknown metric {', '.join(map(repr, unknown))}; use {list(METRICS)}")
    return list(dict.fromkeys(requested))


def _count_all(queries: list[str], count: Count) -> list[int]:
    """The hit count of every query, a few at a time (each request waits out the client's
    politeness delay, which would otherwise be paid once per year)."""
    if len(queries) < 2:
        return [count(q) for q in queries]
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(queries))) as pool:
        return list(pool.map(count, queries))


def _within(base: str, clause: str) -> str:
    return f"({base}) AND {clause}"


# ---------------------------------------------------------------------------
# Exact: counted by Europe PMC
# ---------------------------------------------------------------------------


def year_counts(base: str, total: int, count: Count, edge: Edge) -> dict[str, Any]:
    """Records per first-publication year, one count request per year.

    ``years`` lists the years counted; when the result set spans more than ``MAX_YEARS`` the
    older ones are one ``before`` bucket. ``undated`` is whatever the years do not account for
    (records without a first publication date), so ``sum(years) + before + undated == total``.
    """
    first, last = edge(base, "asc"), edge(base, "desc")
    out: dict[str, Any] = {"basis": "exact", "years": [], "before": None, "undated": total}
    if first is None or last is None or total == 0:
        return out
    start = max(first, last - MAX_YEARS + 1)
    years = list(range(start, last + 1))
    queries = [_within(base, f"FIRST_PDATE:[{y} TO {y}]") for y in years]
    older = start > first
    if older:
        queries.append(_within(base, f"FIRST_PDATE:[* TO {start - 1}]"))
    counts = _count_all(queries, count)
    if older:
        out["before"] = {"year": start - 1, "count": counts.pop()}
    out["years"] = [{"year": y, "count": n} for y, n in zip(years, counts, strict=True) if n]
    counted = sum(counts) + (out["before"]["count"] if older else 0)
    out["undated"] = max(0, total - counted)
    out["counted"] = counted
    out["first_year"], out["last_year"] = first, last
    return out


def open_access_counts(base: str, total: int, count: Count) -> dict[str, Any]:
    """Open-access and not open-access records, and the share, from two counts."""
    (open_n,) = _count_all([_within(base, "OPEN_ACCESS:y")], count)
    return {
        "basis": "exact",
        "open_access": open_n,
        "not_open_access": max(0, total - open_n),
        "share_open_access": round(open_n / total, 4) if total else 0.0,
    }


def citation_thresholds(base: str, total: int, count: Count) -> dict[str, Any]:
    """How many records are cited at least 1, 10, 100 and 1000 times (``CITED:[n TO *]``)."""
    counts = _count_all([_within(base, f"CITED:[{n} TO *]") for n in CITATION_THRESHOLDS], count)
    return {
        "basis": "exact",
        "at_least": {str(n): c for n, c in zip(CITATION_THRESHOLDS, counts, strict=True)},
        "never_cited": max(0, total - counts[0]),
    }


# ---------------------------------------------------------------------------
# Sample: read off fetched records
# ---------------------------------------------------------------------------


def plain(value: Any, top: int | None = None) -> Any:
    """JSON-safe form of an analytics result: a pandas ``Series`` becomes a list of
    ``{"name", "count"}`` (largest first), numpy scalars become Python numbers and NaN null."""
    import pandas as pd

    if isinstance(value, pd.Series):
        ranked = value.sort_values(ascending=False, kind="stable")
        if top is not None:
            ranked = ranked.head(top)
        return [{"name": _key(k), "count": int(v)} for k, v in ranked.items()]
    if isinstance(value, dict):
        return {str(_key(k)): plain(v, top) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [plain(v, top) for v in value]
    if hasattr(value, "item") and not isinstance(value, str | bytes):
        value = value.item()
    if isinstance(value, float):
        return None if value != value else round(value, 4)
    return value


def _key(key: Any) -> Any:
    return key.item() if hasattr(key, "item") else key


def _keep(result: dict[str, Any], keys: tuple[str, ...], top: int) -> dict[str, Any]:
    return {k: plain(result[k], top) for k in keys if k in result}


def summarise(
    metric: str, records: list[dict[str, Any]], top: int = DEFAULT_TOP
) -> dict[str, Any]:
    """One metric computed from ``records`` with the library's analytics functions."""
    from pyeuropepmc.features.analytics import analytics as lib

    if metric == "citations":
        return {"statistics": plain(lib.citation_statistics(records))}
    if metric == "journals":
        return {"top_journals": plain(lib.journal_distribution(records, top_n=top), top)}
    if metric == "authors":
        stats = lib.author_statistics(records, top_n=top)
        return _keep(
            stats,
            (
                "total_authors",
                "total_author_mentions",
                "avg_authors_per_paper",
                "max_authors_per_paper",
                "single_author_papers",
                "multi_author_papers",
                "top_authors",
            ),
            top,
        )
    if metric == "types":
        return {"types": plain(lib.publication_type_distribution(records), top)}
    if metric == "countries":
        # No institutions: the library takes the first part of an affiliation for one, which
        # is usually a department ("Public Health"), not an institution.
        # Only records with an affiliation: the library counts "" as one, which would make
        # `papers_with_affiliation` and the collaboration percentage describe the wrong set.
        geo = lib.geographic_analysis(
            [r for r in records if str(r.get("affiliation") or "").strip()], top_n=top
        )
        return {
            **_keep(geo, ("top_countries", "papers_with_affiliation"), top),
            "international_collaboration_percent": plain(geo["international_collaboration_rate"]),
            "method": "The country is the last comma-separated part of each affiliation.",
        }
    if metric == "funders":
        funding = lib.funding_source_analysis(records, top_n=top)
        return _keep(
            funding,
            ("total_funded_papers", "top_funders", "concentration_index", "multi_funder_papers"),
            top,
        )
    raise ValueError(f"{metric!r} is not computed from records")


def sample_note(fetched: int, hit_count: int, sort: str) -> str:
    """One sentence on what the records behind the ``sample`` metrics are."""
    order = f"sorted by {sort}" if sort else "in relevance order"
    return (
        f"The first {fetched} of {hit_count} matching records, {order}: not a random sample, "
        "so it describes these records and not the whole result set."
    )


def year_of(record: dict[str, Any]) -> int | None:
    """The first publication year of a search record, else its publication year."""
    for key in ("firstPublicationDate", "pubYear"):
        match = re.match(r"\d{4}", str(record.get(key) or ""))
        if match:
            return int(match.group())
    return None
