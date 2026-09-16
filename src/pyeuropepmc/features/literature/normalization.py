"""
Normalization utilities for literature data.

Provides functions for normalizing common bibliographic fields
(DOI, author names, journal titles, etc.) across different sources.

Improvements over v1:
- Multi-word surname detection (von, van, de, da, etc.)
- DOI validation against 10.x/xxxxx pattern
- NFKC unicode normalization throughout
- Abstract normalization (strip section headers, funding statements)
- MeSH term normalization
- Affiliation standardization
"""

from __future__ import annotations

import re
from typing import Any
import unicodedata

# ---------------------------------------------------------------------------
# Known surname prefixes (multi-word family names)
# ---------------------------------------------------------------------------
_SURNAME_PREFIXES: set[str] = {
    "von",
    "van",
    "de",
    "da",
    "del",
    "della",
    "degli",
    "dei",
    "du",
    "des",
    "le",
    "la",
    "las",
    "los",
    "l'",
    "d'",
    "mac",
    "mc",
    "o'",
    "ben",
    "ibn",
    "di",
    "do",
    "das",
    "dos",
}

# ---------------------------------------------------------------------------
# DOI pattern for validation  (e.g. 10.1000/xyz123, 10.1038/s41586-021-1234-5)
# ---------------------------------------------------------------------------
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# PMID pattern for validation  (PubMed IDs are 1-8 digit integers)
# ---------------------------------------------------------------------------
_PMID_PATTERN = re.compile(r"^\d{1,8}$")

# ---------------------------------------------------------------------------
# Abstract section header patterns (common in structured abstracts)
# ---------------------------------------------------------------------------
_ABSTRACT_HEADER_PATTERN = re.compile(
    r"(^|[.:;!?]\s+)(?:background|objective|methods?|results?|conclusions?|"
    r"introduction|discussion|findings?|aims?|purpose|design|setting|"
    r"participants|intervention|main outcome|measurements?|analysis|"
    r"limitations|funding|acknowledgments?|keywords?|trial registration)"
    r"\s*[:.]?\s*",
    re.IGNORECASE,
)

# Replacement: keep the prefix (period/newline) but drop the header label
_ABSTRACT_HEADER_REPLACE = r"\1"

_FUNDING_PATTERN = re.compile(
    r"\b(funded by|supported by|grant[sn]?\s+(no|number)?\s*\d+|"
    r"acknowledg(?:e)?ments?|conflict of interest|disclosure)\b.*",
    re.IGNORECASE,
)

__all__ = [
    "normalize_doi",
    "normalize_pmid",
    "normalize_author_name",
    "normalize_journal_title",
    "normalize_paper_title",
    "normalize_author_list",
    "normalize_abstract",
    "normalize_mesh_terms",
    "normalize_affiliation",
    "is_valid_doi",
    "is_valid_pmid",
    "normalize_to_nfkc",
]


# ===========================================================================
# Unicode normalisation
# ===========================================================================


def normalize_to_nfkc(text: str | None) -> str | None:
    """Normalize string to NFKC (compatibility composed) form.

    NFKC handles:
    - Ligatures (ﬁ → fi, ﬃ → ffi)
    - Super/subscripts (² → 2)
    - Full-width characters (Ａ → A)
    - Fractions (½ → 1/2 composable)

    Parameters
    ----------
    text : str or None
        Input text.

    Returns
    -------
    str or None
        NFKC-normalised text, or None if input was None.
    """
    if text is None:
        return None
    return unicodedata.normalize("NFKC", str(text)).strip() or None


# ===========================================================================
# DOI helpers
# ===========================================================================


def is_valid_doi(doi: str | None) -> bool:
    """Check whether a string is a syntactically valid DOI.

    Valid DOIs match ``10.<registrant-code>/<suffix>`` where the
    registrant code is 4–9 digits.

    Parameters
    ----------
    doi : str or None
        Candidate DOI.

    Returns
    -------
    bool
        ``True`` if the DOI is valid.
    """
    if not doi:
        return False
    return bool(_DOI_PATTERN.match(doi.strip()))


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI by lowercasing and removing URL prefixes.

    Returns ``None`` when the cleaned string is empty **or** fails the
    DOI syntax check.

    Parameters
    ----------
    doi : str or None
        The DOI to normalize.

    Returns
    -------
    str or None
        Normalized DOI, or None if input was None or invalid.

    Examples
    --------
    >>> normalize_doi("10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("https://doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("http://dx.doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi(None)

    >>> normalize_doi("not-a-doi")
    """
    if doi is None:
        return None

    doi = str(doi).strip()

    # Remove common URL prefixes  (case-insensitive)
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^https?://hdl\.handle\.net/", "", doi, flags=re.IGNORECASE)

    # Lowercase
    doi = doi.lower()

    # Validate
    if not doi or not is_valid_doi(doi):
        return None

    return doi


# ===========================================================================
# PMID helpers
# ===========================================================================


def is_valid_pmid(pmid: str | None) -> bool:
    """Check whether a string is a syntactically valid PubMed ID.

    A PMID is a 1-8 digit integer.

    Parameters
    ----------
    pmid : str or None
        Candidate PMID.

    Returns
    -------
    bool
        ``True`` if the PMID is valid.
    """
    if not pmid:
        return False
    return bool(_PMID_PATTERN.match(str(pmid).strip()))


def normalize_pmid(pmid: str | int | None) -> str | None:
    """Normalize a PubMed ID to a bare numeric string.

    Strips common prefixes / URLs (``PMID:``, ``pmid:``,
    ``https://pubmed.ncbi.nlm.nih.gov/``) and validates that the result is a
    1-8 digit integer.

    Parameters
    ----------
    pmid : str, int or None
        The PMID to normalize.

    Returns
    -------
    str or None
        Normalized PMID, or None if input was None/empty or invalid.

    Examples
    --------
    >>> normalize_pmid("PMID: 12345678")
    '12345678'
    >>> normalize_pmid("https://pubmed.ncbi.nlm.nih.gov/12345678/")
    '12345678'
    >>> normalize_pmid(None)

    >>> normalize_pmid("not-a-pmid")
    """
    if pmid is None:
        return None

    text = str(pmid).strip()

    # Remove common prefixes / URL wrappers  (case-insensitive)
    text = re.sub(r"^pmid\s*:?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/", "", text, flags=re.IGNORECASE)
    text = text.strip("/").strip()

    if not is_valid_pmid(text):
        return None

    return text


# ===========================================================================
# Author name helpers
# ===========================================================================


def _is_multi_word_surname(tokens: list[str]) -> tuple[int, str]:
    """Detect multi-word surnames and return ``(split_index, family)``.

    Scans *tokens* from right to left collecting words that look like
    surname prefixes.  Returns the index of the first token that is
    *not* a prefix and the reassembled family name.

    Example::

        tokens = ["John", "von", "Neumann"]
        # returns (1, "von, Neumann")   i.e. split after index 1
    """
    # Find the boundary: first non-prefix token scanning from left
    # after at least one prefix has been seen.
    prefix_count = 0
    boundary = 0
    for i, token in enumerate(tokens):
        if token.lower() in _SURNAME_PREFIXES:
            prefix_count += 1
        else:
            if prefix_count > 0:
                # We've seen prefix(es) followed by a non-prefix → the
                # surname starts at the first prefix.
                break
            boundary = i + 1
    else:
        # All tokens are prefixes or there's exactly one non-prefix at
        # the end – fall back to last-token rule.
        boundary = len(tokens) - 1

    family = " ".join(tokens[boundary:])
    return boundary, family


#: A token made only of capital initials — ``J``, ``JA``, ``J.A.``, ``J.-P.`` —
#: as PubMed and Europe PMC write given names after the surname.
_INITIALS_TOKEN = re.compile(r"^(?:[A-Z]\.?-?){1,4}$")


def _split_trailing_initials(parts: list[str]) -> tuple[str, str] | None:
    """Split ``"Surname INITIALS"`` into ``(family, initials)``.

    PubMed ESummary and Europe PMC ``authorString`` write authors as the
    surname followed by initials (``"Smith J"``, ``"van der Berg JA"``).  Read
    as "First Last", those come out reversed, so recognise the form first.

    Only applies when some earlier token has a lower-case letter: an all-caps
    name such as ``"WANG LI"`` gives no hint which part is the surname and is
    left to the general rule.
    """
    split = len(parts)
    while split > 1 and _INITIALS_TOKEN.match(parts[split - 1]):
        split -= 1
    if split == len(parts) or split == 0:
        return None
    family_tokens = parts[:split]
    if not any(ch.islower() for token in family_tokens for ch in token):
        return None
    return " ".join(family_tokens), " ".join(parts[split:])


def normalize_author_name(name: str | None) -> str | None:
    """Normalize an author name to ``"Last, First"`` format.

    Handles:
    - Multi-word surnames (von Neumann, da Silva, de la Cruz, …)
    - Hyphenated surnames (Taylor-Smith → Taylor-Smith, …)
    - ``"Last, First"`` input (unchanged)
    - ``"Last Initials"`` input as PubMed and Europe PMC write it
      (``"Smith JA"`` → ``"Smith, JA"``)
    - Single names (returned as-is)

    Parameters
    ----------
    name : str or None
        The author name to normalize.

    Returns
    -------
    str or None
        Normalized author name, or None if input was None or empty.
    """
    if name is None:
        return None

    name = normalize_to_nfkc(name)
    if not name:
        return None

    # Already in "Last, First"  (or "Last, First Middle") format → done
    if ", " in name:
        return name

    # Already in "Last, F."  (with comma-space)
    if name.endswith(".") and ", " in name:
        return name

    parts = name.split()
    if not parts:
        return None

    if len(parts) == 1:
        return parts[0]

    # "Smith JA" / "van der Berg JA": surname first, initials last
    surname_first = _split_trailing_initials(parts)
    if surname_first is not None:
        family, initials = surname_first
        return f"{family}, {initials}"

    # Detect multi-word surnames
    boundary, family = _is_multi_word_surname(parts)
    given = " ".join(parts[:boundary])

    if not given:
        # Everything is part of the family name
        return family

    return f"{family}, {given}"


def normalize_author_list(authors: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    """Normalize a list of author dictionaries.

    Normalizes:
    - Author names  (``"Last, First"`` format)
    - ORCID identifiers
    - Affiliation / institution names

    Parameters
    ----------
    authors : list[dict] or None
        List of author dictionaries.

    Returns
    -------
    list[dict] or None
        List of normalized author dictionaries.
    """
    if authors is None:
        return None

    normalized: list[dict[str, Any]] = []
    for author in authors:
        if not isinstance(author, dict):
            continue

        normalized_author: dict[str, Any] = {}

        # --- name ----------------------------------------------------------
        name = author.get("name")
        if name:
            normalized_author["name"] = normalize_author_name(name)
        elif "family_name" in author or "given_name" in author:
            parts = []
            if "family_name" in author:
                parts.append(str(author["family_name"]))
            if "given_name" in author:
                parts.append(str(author["given_name"]))
            if parts:
                normalized_author["name"] = ", ".join(parts)
        elif "last_name" in author or "first_name" in author:
            parts = []
            if "last_name" in author:
                parts.append(str(author["last_name"]))
            if "first_name" in author:
                parts.append(str(author["first_name"]))
            if parts:
                normalized_author["name"] = ", ".join(parts)

        # --- other fields ---------------------------------------------------
        for key in ("orcid", "affiliation", "institute", "institution", "email", "role"):
            if key in author:
                value = author[key]
                if key in ("orcid",):
                    value = _normalize_orcid(value)
                elif key in ("affiliation", "institute", "institution"):
                    value = normalize_affiliation(value)
                if value is not None:
                    normalized_author[key] = value

        if normalized_author:
            normalized.append(normalized_author)

    return normalized or None


def _normalize_orcid(orcid: str | None) -> str | None:
    """Clean an ORCID string to bare digits/X."""
    if orcid is None:
        return None
    cleaned = re.sub(r"[^\dX]", "", str(orcid).upper())
    return cleaned or None


# ===========================================================================
# Journal / title / abstract helpers
# ===========================================================================


def normalize_journal_title(journal: str | None) -> str | None:
    """Normalize a journal title.

    Applies NFKC, strips trailing punctuation, and collapses whitespace.

    Parameters
    ----------
    journal : str or None
        The journal title to normalize.

    Returns
    -------
    str or None
        Normalized journal title, or None if input was None.
    """
    if journal is None:
        return None

    journal = normalize_to_nfkc(journal)
    if not journal:
        return None

    # Remove trailing punctuation (period excluded — it may be part of
    # abbreviated journal names like "J. Am. Chem. Soc.").
    journal = re.sub(r"[;:!?]+$", "", journal)

    # Normalize whitespace
    journal = re.sub(r"\s+", " ", journal)

    return journal.strip() or None


def normalize_paper_title(title: str | None) -> str | None:
    """Normalize a paper title.

    Applies NFKC, removes trailing punctuation, collapses whitespace.

    Parameters
    ----------
    title : str or None
        The paper title to normalize.

    Returns
    -------
    str or None
        Normalized paper title, or None if input was None.
    """
    if title is None:
        return None

    title = normalize_to_nfkc(title)
    if not title:
        return None

    # Remove trailing punctuation
    title = re.sub(r"[.,;:!?]+$", "", title)

    # Normalize whitespace
    title = re.sub(r"\s+", " ", title)

    return title.strip() or None


def normalize_abstract(abstract: str | None, strip_headers: bool = True) -> str | None:
    """Normalize a paper abstract.

    Applies NFKC, optionally removes structured-abstract section headers
    and trailing funding/conflict statements.

    Parameters
    ----------
    abstract : str or None
        The abstract text.
    strip_headers : bool, optional
        Whether to remove ``Background:``, ``Methods:``, etc. labels
        (default: ``True``).

    Returns
    -------
    str or None
        Cleaned abstract, or None if input was None or empty.
    """
    if abstract is None:
        return None

    text = normalize_to_nfkc(abstract)
    if not text:
        return None

    if strip_headers:
        # Remove section headers like "Background: ", "Methods. "
        # while preserving the preceding punctuation (period or line start).
        text = _ABSTRACT_HEADER_PATTERN.sub(_ABSTRACT_HEADER_REPLACE, text)

        # Remove trailing funding / conflict / acknowledgement blocks
        text = _FUNDING_PATTERN.split(text, maxsplit=1)[0]

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip() or None


def normalize_mesh_terms(terms: list[str] | None) -> list[str] | None:
    """Normalize a list of MeSH terms.

    Applies NFKC, lowercases, and deduplicates.

    Parameters
    ----------
    terms : list[str] or None
        Raw MeSH term strings.

    Returns
    -------
    list[str] or None
        Cleaned, deduplicated MeSH terms.
    """
    if not terms:
        return None

    seen: set[str] = set()
    cleaned: list[str] = []
    for term in terms:
        if not term or not isinstance(term, str):
            continue
        norm = normalize_to_nfkc(term)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            cleaned.append(norm)
    return cleaned or None


def normalize_affiliation(affiliation: str | None) -> str | None:
    """Normalize an affiliation / institution string.

    Applies NFKC, collapses whitespace, removes trailing punctuation.

    Parameters
    ----------
    affiliation : str or None
        Raw affiliation string.

    Returns
    -------
    str or None
        Cleaned affiliation, or None if input was None or empty.
    """
    if affiliation is None:
        return None

    text = normalize_to_nfkc(affiliation)
    if not text:
        return None

    # Remove trailing punctuation
    text = re.sub(r"[.,;:!?]+$", "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip() or None
