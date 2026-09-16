"""
MeSH (Medical Subject Headings) expansion utility.

Provides tools for expanding search queries with MeSH terms, finding
related MeSH terms, and converting between MeSH headings and UI codes.

Uses the NCBI MeSH API (free) for term lookup and suggests synonyms,
broader/narrower terms, and related concepts.

References:
    - MeSH Browser: https://meshb.nlm.nih.gov/
    - NCBI MeSH API: https://id.nlm.nih.gov/mesh/
"""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

__all__ = [
    "MeSHExpander",
    "expand_with_mesh",
    "suggest_mesh_terms",
    "lookup_mesh_descriptor",
    "translate_to_mesh",
]

MESH_BASE_URL = "https://id.nlm.nih.gov/mesh/lookup"
MESH_SPARQL_URL = "https://id.nlm.nih.gov/mesh/sparql"

# Common biomedical terms that map to MeSH
_COMMON_TERM_GUIDE: dict[str, list[str]] = {
    "cancer": ["Neoplasms", "Neoplasm", "Tumor", "Malignancy"],
    "covid": ["COVID-19", "SARS-CoV-2", "Coronavirus Infections"],
    "covid-19": ["COVID-19", "SARS-CoV-2", "Pandemics"],
    "diabetes": ["Diabetes Mellitus", "Diabetes Mellitus, Type 1", "Diabetes Mellitus, Type 2"],
    "heart attack": ["Myocardial Infarction", "Myocardial Ischemia"],
    "high blood pressure": ["Hypertension", "Blood Pressure"],
    "alzheimers": ["Alzheimer Disease", "Cognitive Dysfunction", "Dementia"],
    "parkinsons": ["Parkinson Disease", "Neurodegenerative Diseases"],
    "depression": ["Depressive Disorder", "Depression", "Major Depressive Disorder"],
    "brain": ["Brain", "Central Nervous System"],
    "gene therapy": ["Genetic Therapy", "Gene Transfer Techniques"],
    "stem cell": ["Stem Cells", "Stem Cell Research", "Cell- and Tissue-Based Therapy"],
    "machine learning": ["Machine Learning", "Deep Learning", "Artificial Intelligence"],
    "ai": ["Artificial Intelligence", "Machine Learning", "Natural Language Processing"],
    "mri": ["Magnetic Resonance Imaging", "Neuroimaging"],
    "genome": ["Genome", "Genomics", "Whole Genome Sequencing"],
    "inflammation": ["Inflammation", "Inflammatory Response"],
    "obesity": ["Obesity", "Overweight", "Body Mass Index"],
    "pain": ["Pain", "Chronic Pain", "Pain Management"],
    "surgery": ["Surgical Procedures, Operative", "General Surgery"],
}

# One token of a Boolean query: a quoted phrase (the closing quote may be
# missing), a parenthesis, or a run of anything else up to whitespace.
_QUERY_TOKEN = re.compile(r'"[^"]*"?|[()]|[^\s()"]+')
_OPERATORS = frozenset({"AND", "OR", "NOT"})
_PLAIN_WORD = re.compile(r"\w+")


def _quote(text: str) -> str:
    """Quote a term or heading unless it is a single plain word.

    ``Diabetes Mellitus, Type 2`` must stay one phrase: unquoted, Europe PMC
    reads its words as separate terms and the comma as syntax.
    """
    if _PLAIN_WORD.fullmatch(text):
        return text
    return '"' + text.replace('"', "") + '"'


class MeSHExpander:
    """
    Query expansion engine using MeSH vocabulary.

    Takes a natural-language search query and expands it with relevant
    MeSH terms, synonyms, narrower terms, and related concepts.

    Examples
    --------
    >>> expander = MeSHExpander()
    >>> expanded = expander.expand("cancer gene therapy")
    >>> print(expanded.query)
    >>> print(expanded.mesh_terms)
    """

    def __init__(
        self,
        use_api: bool = False,
        max_suggestions: int = 5,
    ) -> None:
        """
        Parameters
        ----------
        use_api : bool, optional
            Whether to query the NCBI MeSH API for live lookups.
            If False, uses the embedded common-term guide only.
        max_suggestions : int, optional
            Maximum number of MeSH term suggestions per input term.
        """
        self.use_api = use_api
        self.max_suggestions = max_suggestions

    def expand(self, query: str) -> MeSHExpansionResult:
        """
        Expand a search query with MeSH terms.

        Parameters
        ----------
        query : str
            Search query string.

        Returns
        -------
        MeSHExpansionResult
            Contains the expanded query, discovered MeSH terms,
            and per-term suggestions.
        """
        mesh_terms: list[str] = []
        term_suggestions: dict[str, list[str]] = {}
        parts: list[str] = []

        for kind, text in self._segments(query):
            suggestions = self._suggest_mesh(text.lower()) if kind != "syntax" else []
            if not suggestions:
                # Unchanged, as written: a quoted phrase stays a phrase and bare
                # words stay separate words.
                parts.append(f'"{text}"' if kind == "phrase" else text)
                continue

            term_suggestions[text.lower()] = suggestions
            mesh_terms.extend(suggestions)
            alternatives: dict[str, str] = {}  # lower-cased -> quoted, first wins
            for candidate in (text, *suggestions):
                alternatives.setdefault(candidate.lower(), _quote(candidate))
            parts.append("(" + " OR ".join(alternatives.values()) + ")")

        return MeSHExpansionResult(
            original_query=query,
            expanded_query=self._join(parts),
            mesh_terms=list(dict.fromkeys(mesh_terms)),
            term_suggestions=term_suggestions,
        )

    @staticmethod
    def _segments(query: str) -> list[tuple[str, str]]:
        """Split *query* into ``(kind, text)`` pieces.

        ``kind`` is ``"words"`` for a run of adjacent bare words (looked up as
        one term, so ``heart attack`` is found), ``"phrase"`` for a quoted
        phrase (``text`` without the quotes), or ``"syntax"`` for what is kept
        exactly as written: ``AND``/``OR``/``NOT``, parentheses,
        field-qualified tokens such as ``TITLE:cancer`` or ``PUB_YEAR:[2020``,
        and the token a bare ``FIELD:`` applies to.
        """
        segments: list[tuple[str, str]] = []
        words: list[str] = []
        bound_to_field = False

        def flush() -> None:
            if words:
                segments.append(("words", " ".join(words)))
                words.clear()

        for piece in _QUERY_TOKEN.findall(query):
            if (bound_to_field and piece != "(") or piece in _OPERATORS or piece in ("(", ")"):
                flush()
                segments.append(("syntax", piece))
                bound_to_field = False
            elif piece.startswith('"'):
                flush()
                phrase = " ".join(piece.strip('"').split())
                if phrase:
                    segments.append(("phrase", phrase))
            elif ":" in piece or "[" in piece or "]" in piece:
                flush()
                segments.append(("syntax", piece))
                bound_to_field = piece.endswith(":")
            else:
                words.append(piece)
        flush()
        return segments

    @staticmethod
    def _join(parts: list[str]) -> str:
        """Join query parts with spaces, but not inside ``( … )`` or after ``FIELD:``."""
        out = ""
        for part in parts:
            if out and not (out.endswith(("(", ":")) or part == ")"):
                out += " "
            out += part
        return out

    def _tokenize(self, query: str) -> list[str]:
        """The search terms of *query*, lower-cased, without operators or syntax."""
        return [
            text.lower()
            for kind, text in self._segments(query)
            if kind != "syntax" and len(text) > 1
        ]

    def _suggest_mesh(self, term: str) -> list[str]:
        """Suggest MeSH terms for a single query term."""
        if not self.use_api:
            return list(_COMMON_TERM_GUIDE.get(term, []))[: self.max_suggestions]

        # Live API lookup (uses NCBI MeSH API)
        try:
            params: dict[str, str | int] = {"q": term, "limit": self.max_suggestions}
            resp = requests.get(
                f"{MESH_BASE_URL}/suggest",
                params=params,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
        except Exception:
            logger.warning("MeSH API lookup failed for term: %s", term, exc_info=True)

        return list(_COMMON_TERM_GUIDE.get(term, []))[: self.max_suggestions]


class MeSHExpansionResult:
    """Result of a MeSH query expansion."""

    def __init__(
        self,
        original_query: str,
        expanded_query: str,
        mesh_terms: list[str],
        term_suggestions: dict[str, list[str]],
    ) -> None:
        self.original_query = original_query
        self.expanded_query = expanded_query
        self.mesh_terms = mesh_terms
        self.term_suggestions = term_suggestions

    def __repr__(self) -> str:
        return (
            f"MeSHExpansionResult(\n"
            f"  original: {self.original_query}\n"
            f"  expanded: {self.expanded_query}\n"
            f"  mesh_terms: {self.mesh_terms}\n"
            f")"
        )


# ------------------------------------------------------------------
# Module-level convenience functions
# ------------------------------------------------------------------


def expand_with_mesh(query: str, use_api: bool = False) -> MeSHExpansionResult:
    """
    Convenience function to expand a query with MeSH terms.

    Parameters
    ----------
    query : str
        Search query string.
    use_api : bool, optional
        Whether to use the live MeSH API.

    Returns
    -------
    MeSHExpansionResult
    """
    expander = MeSHExpander(use_api=use_api)
    return expander.expand(query)


def suggest_mesh_terms(term: str, max_suggestions: int = 5, use_api: bool = False) -> list[str]:
    """
    Suggest MeSH terms for a single search term.

    Parameters
    ----------
    term : str
        A single search term.
    max_suggestions : int, optional
        Maximum number of suggestions.
    use_api : bool, optional
        Whether to use the live MeSH API.

    Returns
    -------
    list[str]
        Suggested MeSH headings.
    """
    expander = MeSHExpander(use_api=use_api, max_suggestions=max_suggestions)
    result = expander.expand(term)
    return result.mesh_terms


def lookup_mesh_descriptor(mesh_heading: str) -> dict[str, Any] | None:
    """
    Look up a MeSH descriptor by heading name.

    Parameters
    ----------
    mesh_heading : str
        MeSH heading text (e.g., "Neoplasms").

    Returns
    -------
    dict or None
        Descriptor information including UI, tree numbers, etc.
    """
    try:
        resp = requests.get(
            f"{MESH_BASE_URL}/descriptor",
            params={"label": mesh_heading, "format": "json"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                first: dict[str, Any] = data[0]
                return first
            if isinstance(data, dict):
                return data
            return None
    except Exception:
        logger.warning("MeSH descriptor lookup failed for: %s", mesh_heading, exc_info=True)
    return None


def translate_to_mesh(terms: list[str], use_api: bool = False) -> dict[str, list[str]]:
    """
    Translate a list of natural-language terms to MeSH headings.

    Parameters
    ----------
    terms : list[str]
        List of natural-language terms.
    use_api : bool, optional
        Whether to use the live MeSH API.

    Returns
    -------
    dict[str, list[str]]
        Mapping of original term -> list of suggested MeSH headings.
    """
    expander = MeSHExpander(use_api=use_api)
    result: dict[str, list[str]] = {}
    for term in terms:
        suggestions = expander._suggest_mesh(term.lower().strip())
        if suggestions:
            result[term] = suggestions
    return result
