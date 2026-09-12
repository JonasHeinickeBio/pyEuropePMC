"""Citation graph analysis.

This slice provides citation graph walking and analysis tools,
enabling snowballing literature reviews via forward and backward
citation traversal.
"""

from pyeuropepmc.features.citations.walker import CitationWalker, SnowballingStrategy

__all__ = [
    "CitationWalker",
    "SnowballingStrategy",
]
