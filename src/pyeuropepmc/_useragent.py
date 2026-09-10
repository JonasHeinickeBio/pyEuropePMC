"""Shared User-Agent helper.

Kept dependency-free (imported by both the low-level ``core`` client and the
``features`` HTTP clients) so it can never introduce an import cycle.
"""

from __future__ import annotations

__all__ = ["get_user_agent", "package_version"]

_PROJECT_URL = "https://github.com/JonasHeinickeBio/pyEuropePMC"


def package_version() -> str:
    """Return the current pyeuropepmc version, falling back gracefully."""
    try:
        from pyeuropepmc import __version__

        return str(__version__)
    except Exception:  # pragma: no cover - defensive against build-time cycles
        pass
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("pyeuropepmc")
        except PackageNotFoundError:
            return "0.0.0"
    except Exception:  # pragma: no cover
        return "0.0.0"


def get_user_agent(email: str | None = None) -> str:
    """Build a polite User-Agent string with the current package version.

    Parameters
    ----------
    email : str, optional
        Contact address appended as ``mailto:`` for API "polite pools"
        (CrossRef, OpenAlex, DataCite, ROR, Unpaywall).
    """
    ua = f"pyeuropepmc/{package_version()} ({_PROJECT_URL}"
    if email:
        ua += f"; mailto:{email}"
    return ua + ")"
