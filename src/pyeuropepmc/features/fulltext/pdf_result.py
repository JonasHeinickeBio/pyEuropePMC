"""What a PDF download reports about the file: where it came from and under what licence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

# "CC BY-NC-ND", "cc-by-nc-nd", "CCBYNCND", "cc by 4.0" -> ("by", "nc", "nd", "4.0")
_CC = re.compile(r"cc(0|by)(nc)?(nd|sa)?(\d(?:\.\d)?)?")


def normalize_license(value: object) -> str | None:
    """A licence as one stable lowercase string, or ``None`` when none was given.

    The sources spell Creative Commons licences differently (``CC BY-NC-ND`` in PMC,
    ``cc by-nc-nd`` in Europe PMC, ``cc-by-nc-nd`` in Unpaywall and OpenAlex, ``CCBYNCND``
    in Semantic Scholar); all become ``cc-by-nc-nd``, with a version (``-4.0``) when the
    source gave one. Anything else is lowercased with spaces turned into hyphens.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().lower()
    squeezed = re.sub(r"[\s_-]+", "", text)
    match = _CC.fullmatch(squeezed)
    if match:
        if match.group(1) == "0":
            return "cc0"
        parts = ["cc", match.group(1), match.group(2), match.group(3), match.group(4)]
        return "-".join(p for p in parts if p)
    return re.sub(r"\s+", "-", text)


@dataclass(frozen=True)
class PdfResult:
    """A saved PDF and its provenance.

    Attributes
    ----------
    path : Path
        The saved file.
    source : str
        The step or service that supplied it, e.g. ``pmc_open_data``, ``unpaywall``.
    url : str or None
        Where the bytes were fetched from; ``None`` for a file taken from the cache.
    license : str or None
        The licence the source reported, normalized (see :func:`normalize_license`);
        ``None`` when it did not say, which is not the same as "not open".
    md5_verified : bool
        ``True`` when the file's MD5 matched the one the source published.
    from_cache : bool
        ``True`` when the file came from the client's own file cache. ``source``, ``url``
        and ``license`` are then those recorded when it was first downloaded, or just
        ``cache`` and nothing else when that record is missing.
    """

    path: Path
    source: str
    url: str | None = None
    license: str | None = None
    md5_verified: bool = False
    from_cache: bool = False
