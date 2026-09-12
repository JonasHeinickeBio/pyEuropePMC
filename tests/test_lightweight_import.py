"""Guard rails for a lightweight ``import pyeuropepmc``.

The top-level package must not pull in heavy / optional third-party
dependencies at import time.  Everything beyond the light core (requests,
cache, exceptions) is loaded lazily via :mod:`pyeuropepmc._lazy` on first
attribute access.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

# Optional dependencies that must NOT be imported just by ``import pyeuropepmc``.
_FORBIDDEN_ON_BARE_IMPORT = [
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "openai",
    "langgraph",
    "flask",
    "semanticscholar",
    "sentence_transformers",
    "pyzotero",
    "bibtexparser",
]


def test_bare_import_does_not_load_heavy_dependencies() -> None:
    """A fresh interpreter importing only pyeuropepmc keeps sys.modules clean."""
    code = textwrap.dedent(
        f"""
        import sys
        import pyeuropepmc  # noqa: F401
        forbidden = {_FORBIDDEN_ON_BARE_IMPORT!r}
        leaked = sorted(m for m in forbidden if m in sys.modules)
        if leaked:
            raise SystemExit("import pyeuropepmc leaked: " + ", ".join(leaked))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_attributes_still_resolve() -> None:
    """Lazy attribute access returns the same objects as a direct import."""
    import pyeuropepmc

    from pyeuropepmc.features.literature.search import SearchClient
    from pyeuropepmc.features.literature.search_parser import EuropePMCParser

    assert pyeuropepmc.SearchClient is SearchClient
    assert pyeuropepmc.Client is SearchClient
    assert pyeuropepmc.Parser is EuropePMCParser
    # names present in dir() for tab-completion / introspection
    assert "UnifiedSearch" in dir(pyeuropepmc)
    assert "SmartCitationAnalysis" in dir(pyeuropepmc)


def test_unknown_attribute_raises_attribute_error() -> None:
    import pyeuropepmc

    try:
        pyeuropepmc.DefinitelyNotAThing  # noqa: B018
    except AttributeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected AttributeError for unknown attribute")
