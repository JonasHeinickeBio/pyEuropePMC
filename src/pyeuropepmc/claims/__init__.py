"""
Claim extraction, verification, and text improvement module.

This module provides a complete pipeline for:
1. Extracting atomic claims from natural language text
2. Verifying claims against Europe PMC literature
3. Reviewing evidence quality
4. Interactive user confirmation
5. Text improvement with citations and bibliography export
"""

# Use lazy imports to avoid circular dependencies during module load
from pyeuropepmc.claims.extractor import ClaimExtractor
from pyeuropepmc.claims.models import (
    Claim,
    ClaimEvidence,
    ClaimReport,
    ClaimSet,
    ClaimType,
    EvidenceQuality,
    Verdict,
)
from pyeuropepmc.claims.reviewer import ClaimReviewer
from pyeuropepmc.claims.verifier import ClaimVerifier
from pyeuropepmc.claims.writer import ClaimWriter


def run_full_workflow(*args, **kwargs):
    """Lazy import and run the full workflow."""
    from pyeuropepmc.claims.cli import run_full_workflow as _run

    return _run(*args, **kwargs)


__all__ = [
    "ClaimExtractor",
    "ClaimVerifier",
    "ClaimReviewer",
    "ClaimWriter",
    "Claim",
    "ClaimEvidence",
    "ClaimSet",
    "ClaimReport",
    "ClaimType",
    "EvidenceQuality",
    "Verdict",
    "run_full_workflow",
]
