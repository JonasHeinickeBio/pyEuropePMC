"""
Quality metrics utilities for PyEuropePMC RDF conversion.

This module provides functions for calculating quality scores and confidence levels
for different entity types.
"""

from typing import Any


def calculate_paper_quality_score(paper_entity: Any) -> float:
    """Calculate quality score for paper data."""
    score = 0.5  # Base score

    if hasattr(paper_entity, "doi") and paper_entity.doi:
        score += 0.2
    if hasattr(paper_entity, "pmid") and paper_entity.pmid:
        score += 0.1
    if hasattr(paper_entity, "title") and paper_entity.title:
        score += 0.1
    if (
        hasattr(paper_entity, "cited_by_count")
        and paper_entity.cited_by_count
        and paper_entity.cited_by_count > 0
    ):
        score += 0.1

    return min(score, 1.0)


def calculate_author_quality_score(author_entity: Any) -> float:
    """Calculate quality score for author data."""
    score = 0.5  # Base score

    if hasattr(author_entity, "orcid") and author_entity.orcid:
        score += 0.2
    if hasattr(author_entity, "affiliation_text") and author_entity.affiliation_text:
        score += 0.1
    if hasattr(author_entity, "full_name") and author_entity.full_name:
        score += 0.2

    return min(score, 1.0)


def calculate_institution_quality_score(inst_data: dict[str, Any]) -> float:
    """Calculate quality score for institution data."""
    score = 0.5  # Base score

    if inst_data.get("country"):
        score += 0.1
    if inst_data.get("type"):
        score += 0.1
    if len(inst_data.get("name", "")) > 10:  # Longer names tend to be more complete
        score += 0.1
    if inst_data.get("member_count", 0) > 0:
        score += 0.1

    return min(score, 1.0)


def get_confidence_level(score: float) -> str:
    """Get confidence level string from score."""
    if score >= 0.8:
        return "high"
    elif score >= 0.6:
        return "medium"
    else:
        return "low"
