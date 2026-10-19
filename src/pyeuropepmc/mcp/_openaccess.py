"""Shaping of Unpaywall records for MCP responses.

Pure functions, no I/O. An Unpaywall record carries the whole bibliographic record and
every repository copy it knows of; an agent asking "where can I read this for free?"
needs the status, the best copy and a few alternatives.
"""

from __future__ import annotations

import re
from typing import Any

# DOIs are "10." + a registrant code + "/" + a suffix with almost no restrictions.
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_MAX_ALTERNATIVES = 5


def clean_doi(value: str) -> str:
    """A DOI without a ``doi:`` prefix or ``https://doi.org/`` URL, or ``""`` if malformed."""
    doi = value.strip()
    doi = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", doi, flags=re.IGNORECASE)
    return doi if _DOI_RE.match(doi) else ""


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def compact_location(location: dict[str, Any]) -> dict[str, Any]:
    """One OA location without Unpaywall's bookkeeping (evidence, endpoint ids, dates)."""
    return {
        "url": _text(location.get("url")),
        "pdf_url": _text(location.get("url_for_pdf")),
        "landing_page_url": _text(location.get("url_for_landing_page")),
        "license": _text(location.get("license")),
        "host_type": _text(location.get("host_type")),
        "version": _text(location.get("version")),
        "repository": _text(location.get("repository_institution")),
    }


def summarize(record: dict[str, Any]) -> dict[str, Any]:
    """The answer to "is there a free copy, and where": status, best copy, alternatives.

    ``alternatives`` leaves out the best location and is capped; ``location_count`` says
    how many copies Unpaywall knows of in total.
    """
    best = record.get("best_oa_location")
    best_summary = compact_location(best) if isinstance(best, dict) else None
    locations = [loc for loc in record.get("oa_locations") or [] if isinstance(loc, dict)]
    others = [
        loc for loc in locations if not (best_summary and loc.get("url") == best_summary["url"])
    ]
    return {
        "is_oa": record.get("is_oa") is True,
        "oa_status": _text(record.get("oa_status")),
        "journal_is_oa": record.get("journal_is_oa") is True,
        "best_location": best_summary,
        "alternatives": [compact_location(loc) for loc in others[:_MAX_ALTERNATIVES]],
        "location_count": len(locations),
        "title": _text(record.get("title")),
        "year": record.get("year") if isinstance(record.get("year"), int) else None,
    }
