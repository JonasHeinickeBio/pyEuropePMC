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
        terms = self._tokenize(query)
        mesh_terms: list[str] = []
        term_suggestions: dict[str, list[str]] = {}
        expansion_parts: list[str] = []

        for term in terms:
            suggestions = self._suggest_mesh(term)
            if suggestions:
                term_suggestions[term] = suggestions
                mesh_terms.extend(suggestions)
                expansion_parts.append(f"({term} OR {' OR '.join(suggestions)})")
            else:
                expansion_parts.append(term)

        expanded_query = " ".join(expansion_parts)
        unique_mesh = list(dict.fromkeys(mesh_terms))

        return MeSHExpansionResult(
            original_query=query,
            expanded_query=expanded_query,
            mesh_terms=unique_mesh,
            term_suggestions=term_suggestions,
        )

    def _tokenize(self, query: str) -> list[str]:
        """Split query into individual search terms."""
        # Split on boolean operators and punctuation
        tokens = re.split(r'\s+(?:AND|OR|NOT)\s+|\s*[()"\[\]]\s*', query)
        result = []
        for t in tokens:
            t = t.strip().lower()
            if t and len(t) > 1:
                result.append(t)
        return result

    def _suggest_mesh(self, term: str) -> list[str]:
        """Suggest MeSH terms for a single query term."""
        if not self.use_api:
            return list(_COMMON_TERM_GUIDE.get(term, []))[: self.max_suggestions]

        # Live API lookup (uses NCBI MeSH API)
        try:
            resp = requests.get(
                f"{MESH_BASE_URL}/suggest",
                params={"q": term, "limit": self.max_suggestions},
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
                return data[0]
            return data
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
