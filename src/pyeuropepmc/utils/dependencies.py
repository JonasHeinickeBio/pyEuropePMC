"""
Dependency utilities for optional dependency management.

This module provides utilities to check for optional dependencies
and handle import errors gracefully throughout the package.

Usage:
    from pyeuropepmc.utils.dependencies import (
        is_dependency_available,
        require_dependency,
        skip_if_dependency_missing,
    )

    # Check if a dependency is available
    if not is_dependency_available("pandas"):
        print("pandas is not installed")

    # Require a dependency with informative error
    require_dependency("matplotlib", "plotting")

    # Skip test if dependency is missing
    @skip_if_dependency_missing("pandas", "data operations")
    def test_data_processing():
        # test code here
"""

from functools import wraps
import importlib


def is_dependency_available(package: str) -> bool:
    """
    Check if a package is installed without importing it.

    Parameters
    ----------
    package : str
        Package name to check (e.g., "pandas", "matplotlib")

    Returns
    -------
    bool
        True if package is available, False otherwise

    Examples
    --------
    >>> is_dependency_available("requests")
    True
    >>> is_dependency_available("nonexistent_package_123")
    False
    """
    try:
        # Replace underscores with dots for module name conversion
        module_name = package.replace("-", "_").replace(".", "_")
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def require_dependency(
    package: str,
    feature: str,
    install_group: str | None = None,
) -> None:
    """
    Require a dependency and raise informative error if missing.

    Parameters
    ----------
    package : str
        Package name to require
    feature : str
        Description of the feature that requires this package
    install_group : Optional[str]
        Optional dependency group name for installation command

    Raises
    ------
    ImportError
        If the package is not installed with informative message

    Examples
    --------
    >>> require_dependency("pandas", "data processing")
    >>> require_dependency("matplotlib", "plotting", install_group="standard")
    """
    if not is_dependency_available(package):
        install_cmd = (
            f"pip install pyeuropepmc[{install_group}]"
            if install_group
            else f"pip install {package}"
        )
        raise ImportError(
            f"The '{package}' package is required for {feature}.\nInstall it with: {install_cmd}"
        )


def skip_if_dependency_missing(
    package: str,
    feature: str,
    install_group: str | None = None,
):
    """
    Decorator to skip a test function if a dependency is missing.

    Parameters
    ----------
    package : str
        Package name to check
    feature : str
        Description of the feature
    install_group : Optional[str]
        Optional dependency group name

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @skip_if_dependency_missing("pandas", "data operations")
    ... def test_pandas_function():
    ...     pass
    """
    import pytest

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_dependency_available(package):
                install_cmd = (
                    f"pip install pyeuropepmc[{install_group}]"
                    if install_group
                    else f"pip install {package}"
                )
                pytest.skip(
                    f"Skipping {func.__name__}: '{package}' not available for {feature}. "
                    f"Install with: {install_cmd}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def skip_if_dependencies_missing(
    packages: list[str],
    feature: str,
    install_group: str | None = None,
):
    """
    Decorator to skip a test function if any of the dependencies are missing.

    Parameters
    ----------
    packages : List[str]
        List of package names to check
    feature : str
        Description of the feature
    install_group : Optional[str]
        Optional dependency group name

    Returns
    -------
    Callable
        Decorator function

    Examples
    --------
    >>> @skip_if_dependencies_missing(["pandas", "matplotlib"], "visualization")
    ... def test_visualization():
    ...     pass
    """
    import pytest

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            missing = [pkg for pkg in packages if not is_dependency_available(pkg)]
            if missing:
                install_cmd = (
                    f"pip install pyeuropepmc[{install_group}]"
                    if install_group
                    else f"pip install {' '.join(missing)}"
                )
                pytest.skip(
                    f"Skipping {func.__name__}: missing packages {missing} for {feature}. "
                    f"Install with: {install_cmd}"
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Predefined dependency groups for easy reference
DEPENDENCY_GROUPS = {
    "standard": [
        "pandas",
        "matplotlib",
        "seaborn",
        "xlsxwriter",
        "typer",
        "rich",
        "requests_cache",
        "ipython",
        "ipykernel",
        "jupyterlab",
        "notebook",
    ],
    "rdf": [
        "rdflib",
        "rdflib_jsonld",  # rdflib-jsonld imports as rdflib_jsonld
        "rdfizer",
    ],
    "agentic": [
        "langchain",
        "langchain_openai",  # langchain-openai imports as langchain_openai
        "openai",
        "rapidfuzz",
    ],
    "enrichment": [
        "semanticscholar",
        "cryptography",
        "search_query",  # search-query imports as search_query
        "tornado",
        "flask",
    ],
    "visualization": ["matplotlib", "seaborn"],
    "analytics": ["pandas"],
    "export": ["xlsxwriter"],
}

# Feature to group mapping
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
    "cli": "standard",
    "jupyter": "standard",
}
