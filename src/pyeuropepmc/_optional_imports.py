"""
Optional import helpers for graceful dependency management.

This module provides utility functions to check for optional dependencies
and raise informative errors when features require missing packages.

Usage:
    from pyeuropepmc._optional_imports import check_dependencies, OptionalDependency

    # Check multiple dependencies at once
    check_dependencies(["pandas", "matplotlib"], "visualization", "plotting")

    # Check with custom error message
    try:
        import pandas as pd
    except ImportError:
        raise OptionalDependency("pandas", "data operations", "pip install pyeuropepmc[standard]")
"""

import importlib
from typing import Any


class OptionalDependencyError(ImportError):
    """Raised when an optional dependency is missing."""

    def __init__(self, package: str, feature: str, install_command: str | None = None):
        self.package = package
        self.feature = feature
        self.install_command = install_command
        msg = (
            f"The '{package}' package is required for {feature}.\n"
            f"Install it with: {install_command or f'pip install {package}'}"
        )
        super().__init__(msg)


def check_dependencies(
    packages: list[str],
    feature: str,
    install_group: str | None = None,
    extra_message: str | None = None,
) -> bool:
    """
    Check if all required optional dependencies are installed.

    Parameters
    ----------
    packages : List[str]
        List of package names to check
    feature : str
        Description of the feature that requires these packages
    install_group : Optional[str]
        Optional dependency group name for installation command
    extra_message : Optional[str]
        Additional context to include in error message

    Returns
    -------
    bool
        True if all packages are available

    Raises
    ------
    OptionalDependencyError
        If any required package is missing
    """
    missing = []
    for pkg in packages:
        try:
            importlib.import_module(pkg.split("[")[0])  # Handle extras like "package[extra]"
        except ImportError:
            missing.append(pkg)

    if missing:
        install_cmd = (
            f"pip install pyeuropepmc[{install_group}]"
            if install_group
            else f"pip install {' '.join(missing)}"
        )
        msg = (
            f"Missing required packages for {feature}: {', '.join(missing)}\n"
            f"Install with: {install_cmd}"
        )
        if extra_message:
            msg += f"\n{extra_message}"
        raise OptionalDependencyError(missing[0], feature, install_cmd)

    return True


def is_package_available(package: str) -> bool:
    """
    Check if a package is installed without importing it.

    Parameters
    ----------
    package : str
        Package name to check

    Returns
    -------
    bool
        True if package is available
    """
    try:
        importlib.import_module(package.split("[")[0])
        return True
    except ImportError:
        return False


def import_optional(package: str, feature: str, install_group: str | None = None) -> Any:
    """
    Import a package with graceful error handling for missing dependencies.

    Parameters
    ----------
    package : str
        Package name to import
    feature : str
        Description of the feature that requires this package
    install_group : Optional[str]
        Optional dependency group name for installation command

    Returns
    -------
    module
        The imported module

    Raises
    ------
    OptionalDependencyError
        If the package is not installed
    """
    try:
        return importlib.import_module(package)
    except ImportError:
        install_cmd = (
            f"pip install pyeuropepmc[{install_group}]"
            if install_group
            else f"pip install {package}"
        )
        raise OptionalDependencyError(package, feature, install_cmd) from None


# Optional-dependency groups. Keys mirror ``[project.optional-dependencies]``
# in pyproject.toml; values are *import* names (not distribution names) so they
# can be fed straight to ``importlib.import_module`` / ``is_package_available``.
#
# Single source of truth: ``pyeuropepmc.utils.dependencies`` re-exports these.
DEPENDENCY_GROUPS = {
    "analytics": ["pandas", "numpy"],
    "visualization": ["matplotlib", "seaborn", "pandas", "numpy"],
    "export": ["xlsxwriter", "tabulate", "pandas"],
    "rdf": [
        "rdflib_jsonld",  # rdflib-jsonld imports as rdflib_jsonld
        "rdfizer",
    ],
    "ui": ["flask", "tornado"],
    "signing": ["cryptography"],
    "bibliography": ["bibtexparser"],
    "zotero": ["pyzotero"],
    "agentic": [
        "langchain",
        "langchain_openai",  # langchain-openai imports as langchain_openai
        "openai",
        "langgraph",
    ],
    "semanticscholar": ["semanticscholar"],
    # Enrichment bundle: what the enrichment clients can optionally use.
    "enrichment": ["semanticscholar", "cryptography"],
    "ml": ["sentence_transformers"],  # sentence-transformers imports as sentence_transformers
    "standard": [
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "xlsxwriter",
        "tabulate",
        "requests_cache",  # requests-cache imports as requests_cache
        "rich",
        "IPython",  # ipython imports as IPython
        "ipykernel",
        "ipywidgets",
        "jupyterlab",
        "notebook",
    ],
}

# Feature name -> extra. ``import_optional(pkg, feature)`` uses this to turn a
# human feature label into the right ``pip install pyeuropepmc[<extra>]`` hint.
FEATURE_TO_GROUP = {
    "visualization": "visualization",
    "plotting": "visualization",
    "analytics": "analytics",
    "data_export": "export",
    "rdf": "rdf",
    "semantic_web": "rdf",
    "llm": "agentic",
    "ai": "agentic",
    "citation_analysis": "agentic",
    "enrichment": "enrichment",
    "semantic_scholar": "semanticscholar",
    "bibliography": "bibliography",
    "bibtex": "bibliography",
    "citation_management": "bibliography",
    "zotero": "zotero",
    "ui": "ui",
    "web_ui": "ui",
    "signing": "signing",
    "semantic_matching": "ml",
    "embeddings": "ml",
    "cli": "standard",
    "jupyter": "standard",
}
