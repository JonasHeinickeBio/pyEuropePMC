import json
from pathlib import Path

import pytest
from pyeuropepmc.utils.dependencies import is_dependency_available

# Base directory for fixtures
FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _looks_like_lfs_pointer(b: bytes) -> bool:
    """Return True if the given bytes look like a Git LFS pointer file.

    Common LFS pointer contents include lines like:
      version https://git-lfs.github.com/spec/v1
      oid sha256:...
      size 12345
    """
    if not b:
        return False
    head = b.lower()
    return b"version https://git-lfs" in head or b"oid sha256:" in head


def pytest_sessionstart(session):
    """Ensure large binary fixtures are present (not Git LFS pointer files).

    If pointer files are detected we'll attempt to run `git lfs pull` once. If
    git-lfs is not available or pointers remain after the pull, the test run
    will exit with an actionable error message so CI can be configured to fetch
    LFS objects.
    """
    # Only check the fulltext_downloads fixtures which are known to contain
    # binary PDF/XML test fixtures that may be stored with Git LFS.
    downloads = FIXTURE_DIR / "fulltext_downloads"
    try:
        candidates = list(downloads.iterdir())
    except Exception:
        # No fixtures dir — nothing to check
        return

    pointers = []
    for p in candidates:
        if not p.is_file():
            continue
        try:
            with p.open("rb") as fh:
                head = fh.read(256)
        except Exception:
            continue
        if _looks_like_lfs_pointer(head):
            pointers.append(p)

    if not pointers:
        return

    # Try to run `git lfs pull` to fetch real objects.
    import subprocess

    try:
        proc = subprocess.run(["git", "lfs", "pull"], capture_output=True, text=True)
    except FileNotFoundError:
        pytest.exit(
            "\nDetected Git LFS pointer files in tests/fixtures/fulltext_downloads/ but `git` or `git-lfs` is not available in PATH.\n"
            "Install Git LFS locally and run `git lfs pull` (or configure your CI to fetch LFS objects).\n"
        )

    # Re-check whether pointers remain
    remaining = []
    for p in pointers:
        try:
            with p.open("rb") as fh:
                head = fh.read(256)
        except Exception:
            continue
        if _looks_like_lfs_pointer(head):
            remaining.append(p)

    if not remaining:
        # Successfully fetched objects — continue with the test run.
        return

    # Still have pointer files — fail early with an actionable message.
    names = ", ".join(str(p.relative_to(Path.cwd())) for p in remaining[:10])
    pytest.exit(
        f"\nFound Git LFS pointer files in fixtures (examples: {names}).\n"
        "Please run `git lfs pull` locally or ensure your CI checkout fetches LFS objects.\n"
    )


@pytest.fixture
def search_cancer_json():
    with (FIXTURE_DIR / "search_cancer.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_cancer_xml():
    with (FIXTURE_DIR / "search_cancer.xml").open() as f:
        return f.read()


@pytest.fixture
def search_cancer_dc_xml():
    with (FIXTURE_DIR / "search_cancer_dc.xml").open() as f:
        return f.read()


@pytest.fixture
def search_cancer_core_json():
    with (FIXTURE_DIR / "search_cancer_core.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_cancer_idlist_json():
    with (FIXTURE_DIR / "search_cancer_idlist.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_post_cancer_json():
    with (FIXTURE_DIR / "search_post_cancer.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_cancer_page2_json():
    with (FIXTURE_DIR / "search_cancer_page2.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_1000results_cancer_json():
    with (FIXTURE_DIR / "search_1000results_cancer.json").open() as f:
        return json.load(f)


@pytest.fixture
def fetch_all_1000results_cancer_json():
    with (FIXTURE_DIR / "fetch_all_1000results_cancer.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_no_results_json():
    with (FIXTURE_DIR / "search_no_results.json").open() as f:
        return json.load(f)


@pytest.fixture
def search_cancer_sorted_cited_json():
    with (FIXTURE_DIR / "search_cancer_sorted_cited.json").open() as f:
        return json.load(f)


@pytest.fixture
def fetch_10pages_cancer_json():
    with (FIXTURE_DIR / "fetch_10pages_cancer.json").open() as f:
        return json.load(f)


# Dependency utilities for test skipping
MARKER_TO_PACKAGE = {
    "visualization": ["matplotlib", "seaborn"],
    "pandas": ["pandas"],
    "rdflib": ["rdflib", "rdflib_jsonld"],
    "rdf": ["rdflib", "rdflib_jsonld"],
    "agentic": ["langchain", "langchain_openai", "openai"],
    "llm": ["langchain", "langchain_openai", "openai"],
    "enrichment": ["semanticscholar", "cryptography", "search_query"],
    "cli": ["typer", "rich"],
    "jupyter": ["ipython", "ipykernel"],
    "analytics": ["pandas"],
    "export": ["xlsxwriter"],
}


def pytest_runtest_setup(item):
    """
    Hook to skip tests based on markers and missing dependencies.

    This function is called before each test to check if it should be skipped
    due to missing optional dependencies.
    """
    # Check test markers for dependency requirements
    for marker in item.iter_markers():
        if marker.name in MARKER_TO_PACKAGE:
            packages = MARKER_TO_PACKAGE[marker.name]
            missing = [pkg for pkg in packages if not is_dependency_available(pkg)]
            if missing:
                pytest.skip(
                    f"Skipping {item.nodeid}: missing dependencies {missing} "
                    f"required by '{marker.name}' marker"
                )
            break  # Only process first matching marker


def pytest_collection_modifyitems(config, items):
    """
    Hook to modify collected tests based on available dependencies.

    This can be used to reorder tests or add skips based on overall
    dependency availability.
    """
    # Check if core dependencies are available
    core_deps = ["requests", "backoff", "defusedxml", "tqdm"]
    missing_core = [dep for dep in core_deps if not is_dependency_available(dep)]

    if missing_core:
        # If core dependencies are missing, we can't run most tests
        # This shouldn't happen in normal usage but is a safety check
        config.warn(
            code="MISSING_CORE_DEPS",
            message=f"Core dependencies missing: {missing_core}. "
            "Many tests will be skipped.",
        )
