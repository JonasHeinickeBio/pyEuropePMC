"""Shaping of ``PaperEnricher`` results for MCP responses.

Pure functions, no I/O. The enricher returns the raw answer of every source (OpenAlex alone
is 36 KB for one paper) next to a merged record; an agent asking "who funded this, is it
retracted, how much is it cited" needs a few hundred bytes of the merged record, grouped by
question, and an honest account of which source answered.
"""

from __future__ import annotations

from typing import Any

#: Field groups of the answer, in output order.
GROUPS = ("impact", "funding", "affiliations", "oa", "updates")

#: Sources a caller may ask for. Europe PMC is the base record and always queried.
SOURCES = ("crossref", "openalex", "semantic_scholar", "icite", "unpaywall")

MAX_AUTHORS = 30
MAX_PER_AUTHOR = 3
MAX_FUNDING = 20
MAX_AWARDS = 5
MAX_TOPICS = 5
MAX_FIELDS = 8
MAX_URLS = 5
MAX_UPDATES = 20


def validate_choice(
    values: list[str] | None, valid: tuple[str, ...], label: str
) -> tuple[str, ...]:
    """The chosen names in the order of ``valid``; an unknown name is an error naming the rest."""
    if not values:
        return valid
    chosen = {v.strip().lower().replace("-", "_") for v in values if v.strip()}
    unknown = sorted(chosen - set(valid))
    if unknown:
        raise ValueError(f"unknown {label} {unknown}; valid: {list(valid)}")
    return tuple(name for name in valid if name in chosen) or valid


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clip(value: Any, limit: int) -> list[Any]:
    return list(value)[:limit] if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _identity(results: dict[str, Any], merged: dict[str, Any]) -> dict[str, Any]:
    ids = _obj(merged.get("external_ids"))
    epmc = _obj(results.get("europepmc"))
    types = merged.get("publication_type")
    return {
        "doi": results.get("doi") or ids.get("doi"),
        "pmid": results.get("pmid") or ids.get("pmid"),
        "pmcid": ids.get("pmcid") or epmc.get("pmcid"),
        "title": merged.get("title"),
        "journal": merged.get("journal"),
        "year": merged.get("publication_year"),
        "publication_type": types if isinstance(types, list) else None,
    }


def _impact(merged: dict[str, Any]) -> dict[str, Any]:
    icite = _obj(merged.get("icite"))
    references = _obj(merged.get("references"))
    topics = [
        {"name": t.get("display_name"), "score": t.get("score")}
        for t in _clip(merged.get("topics"), MAX_TOPICS)
        if isinstance(t, dict)
    ]
    return {
        "citation_count": merged.get("citation_count"),
        "citation_counts": merged.get("citation_counts") or [],
        "influential_citation_count": merged.get("influential_citation_count"),
        "relative_citation_ratio": icite.get("rcr"),
        "percentile": icite.get("percentile"),
        "nih_percentile": icite.get("nih_percentile"),
        "reference_count": references.get("count"),
        "fields_of_study": _clip(merged.get("fields_of_study"), MAX_FIELDS),
        "topics": topics,
    }


def _funding(merged: dict[str, Any]) -> dict[str, Any]:
    funders = [
        {
            "name": f.get("name"),
            "doi": f.get("doi"),
            "awards": _clip(f.get("award"), MAX_AWARDS),
        }
        for f in _clip(merged.get("funding"), MAX_FUNDING)
        if isinstance(f, dict)
    ]
    grants = [g for g in _clip(merged.get("grants"), MAX_FUNDING) if isinstance(g, dict)]
    return {
        "funders": funders,
        "grants": [{"agency": g.get("agency"), "grant_id": g.get("grant_id")} for g in grants],
    }


def _author(author: dict[str, Any]) -> dict[str, Any]:
    institutions = [
        {
            "name": i.get("display_name"),
            "country": i.get("country"),
            "ror": i.get("ror_id"),
        }
        for i in _clip(author.get("institutions"), MAX_PER_AUTHOR)
        if isinstance(i, dict)
    ]
    return {
        "name": author.get("name"),
        "orcid": author.get("orcid"),
        "affiliations": [
            a if isinstance(a, str) else (a.get("name") if isinstance(a, dict) else None)
            for a in _clip(author.get("affiliations"), MAX_PER_AUTHOR)
        ],
        "institutions": institutions,
    }


def _affiliations(merged: dict[str, Any]) -> dict[str, Any]:
    authors = [a for a in merged.get("authors") or [] if isinstance(a, dict)]
    return {
        "author_count": len(authors),
        "authors": [_author(a) for a in authors[:MAX_AUTHORS]],
        "authors_truncated": len(authors) > MAX_AUTHORS,
    }


def _open_access(merged: dict[str, Any]) -> dict[str, Any]:
    return {
        "is_oa": merged.get("is_oa"),
        "oa_status": merged.get("oa_status"),
        "oa_url": merged.get("oa_url"),
        "license": merged.get("license"),
        "full_text_urls": _clip(merged.get("full_text_urls"), MAX_URLS),
    }


def _updates(merged: dict[str, Any]) -> dict[str, Any]:
    updates = [u for u in merged.get("updates") or [] if isinstance(u, dict)]
    return {
        "is_retracted": merged.get("is_retracted"),
        "updates": updates[:MAX_UPDATES],
        "updates_truncated": len(updates) > MAX_UPDATES,
    }


def shape(results: dict[str, Any], include: tuple[str, ...] = GROUPS) -> dict[str, Any]:
    """The compact record: the article's identity plus the requested field groups."""
    merged = _obj(results.get("merged"))
    builders = {
        "impact": _impact,
        "funding": _funding,
        "affiliations": _affiliations,
        "oa": _open_access,
        "updates": _updates,
    }
    record: dict[str, Any] = {"article": _identity(results, merged)}
    for group in GROUPS:
        if group in include:
            record[group] = builders[group](merged)
    return record


def source_report(
    results: dict[str, Any], requested: tuple[str, ...], available: set[str]
) -> dict[str, dict[str, Any]]:
    """``source -> {status, seconds?, error?, reason?}`` for Europe PMC and every requested source.

    ``status`` is ``ok`` (data), ``empty`` (the source answered without data for this paper),
    ``error``, ``timeout`` (still running when the time budget ended), ``unavailable`` (the
    server cannot use the source: a missing extra or e-mail address) or ``skipped``.
    """
    reported = _obj(results.get("source_status"))
    out: dict[str, dict[str, Any]] = {}
    for name in ("europepmc", *requested):
        if name not in available:
            out[name] = {"status": "unavailable", "reason": unavailable_reason(name)}
        elif isinstance(reported.get(name), dict):
            out[name] = {k: v for k, v in reported[name].items() if v is not None}
        else:
            out[name] = {"status": "skipped", "reason": "no usable identifier"}
    return out


def unavailable_reason(name: str) -> str:
    return {
        "unpaywall": "set UNPAYWALL_EMAIL in the server's environment",
        "semantic_scholar": (
            "install the semanticscholar extra: pip install pyeuropepmc[semanticscholar]"
        ),
    }.get(name, "the source client could not be started")


def completeness(report: dict[str, dict[str, Any]]) -> bool:
    """True when every source answered (with data or an honest empty answer)."""
    return all(entry.get("status") in ("ok", "empty") for entry in report.values())
