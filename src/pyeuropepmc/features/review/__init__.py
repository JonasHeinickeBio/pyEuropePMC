"""Systematic review support tools.

This slice provides tools for systematic literature reviews,
including MeSH term expansion and PICO element extraction for
evidence-based practice.
"""

from pyeuropepmc.features.review.mesh import (
    MeSHExpander,
    expand_with_mesh,
    lookup_mesh_descriptor,
    suggest_mesh_terms,
    translate_to_mesh,
)
from pyeuropepmc.features.review.pico import (
    PICOElements,
    PICOParser,
    PICOSDecomposer,
    PICOTDecomposer,
    SPIDERDecomposer,
    pico_decompose,
    pico_to_pubmed_query,
    pico_to_query,
)

__all__ = [
    "MeSHExpander",
    "PICOElements",
    "PICOParser",
    "PICOSDecomposer",
    "PICOTDecomposer",
    "SPIDERDecomposer",
    "expand_with_mesh",
    "lookup_mesh_descriptor",
    "pico_decompose",
    "pico_to_pubmed_query",
    "pico_to_query",
    "suggest_mesh_terms",
    "translate_to_mesh",
]
