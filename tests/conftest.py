import contextlib
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


# ---------------------------------------------------------------------------
# Test taxonomy: path-based auto-marking + network guard
#
# The default test run (see ``addopts`` in pyproject.toml) is
# ``-m 'not slow and not functional and not network and not benchmark and not e2e'``
# and ``--disable-socket`` (via pytest-socket).  That only works if slow /
# network-dependent tests are actually *marked*.  Historically many were not
# (whole ``functional/`` directories carried no marker), so the "unit" run
# would hang on real API calls and grow unbounded in memory while accumulating
# HTTP responses and Hugging Face dataset downloads.
#
# Rather than annotate hundreds of files, we infer the markers from the test's
# location here, and re-enable the socket for the categories that legitimately
# need the network so they still work when selected explicitly
# (``-m functional``, ``--run-real``, ``--run-integration``).
# ---------------------------------------------------------------------------

# Marker -> one-line description (registered so ``--strict-markers`` is happy).
_EXTRA_MARKERS = {
    "functional": "exercises real services / full pipelines; excluded by default",
    "network": "needs outbound network access; excluded by default",
    "benchmark": "pytest-benchmark performance test; excluded by default",
    "gui": "exercises the Flask web UI",
    "e2e": "end-to-end scenario; excluded by default",
    "model": "needs ML model dependencies (sentence-transformers, torch, ...)",
}

# Categories whose tests may talk to the network when run on purpose.
_NETWORK_CATEGORIES = {"functional", "integration", "network", "e2e"}


def pytest_addoption(parser):
    import importlib.util

    group = parser.getgroup("pyeuropepmc")
    with contextlib.suppress(ValueError):
        group.addoption(
            "--run-real",
            action="store_true",
            default=False,
            help="Run functional/network tests that call real external APIs.",
        )

    # ``addopts`` (pyproject.toml) passes --disable-socket / --timeout for the
    # hermetic default run. If pytest-socket / pytest-timeout aren't installed,
    # register inert placeholders so those flags don't crash pytest (the suite
    # then just runs without the guard rails).
    if importlib.util.find_spec("pytest_socket") is None:
        with contextlib.suppress(ValueError):
            group.addoption("--disable-socket", action="store_true", help="(no-op)")
            group.addoption("--allow-unix-socket", action="store_true", help="(no-op)")
            group.addoption("--force-enable-socket", action="store_true", help="(no-op)")
    if importlib.util.find_spec("pytest_timeout") is None:
        with contextlib.suppress(ValueError):
            group.addoption("--timeout", default=None, help="(no-op)")


def pytest_configure(config):
    for name, desc in _EXTRA_MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {desc}")

    if config.getoption("--run-real", default=False):
        # ``--run-real`` == "only the tests that hit real services": select them
        # and undo the default ``--disable-socket`` (set in addopts) so they can
        # actually reach the network.
        config.option.markexpr = "functional or network or e2e"
        with contextlib.suppress(Exception):
            config.option.disable_socket = False
            from pytest_socket import enable_socket

            enable_socket()


def _infer_markers(item) -> set[str]:
    """Markers implied by a test's file path / name / fixtures."""
    path = str(item.fspath).replace("\\", "/")
    name = item.fspath.basename
    inferred: set[str] = set()
    if "/functional/" in path:
        inferred.add("functional")
    if "/integration/" in path:
        inferred.add("integration")
    if name.startswith("interactive_") or name.endswith("_interactive_test.py"):
        inferred.add("functional")
    if "/gui/" in path:
        inferred.add("gui")
    # Actual pytest-benchmark tests (they request the ``benchmark`` fixture) or
    # the dedicated top-level benchmark scripts.
    if "benchmark" in getattr(item, "fixturenames", ()) or name.startswith("benchmark_"):
        inferred |= {"benchmark", "slow"}
    return inferred


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Report a third-party outage as a skip, not a failure.

    The functional suite calls live services (Europe PMC, Zenodo, DOAJ, DBLP,
    HAL, CORE, iCite). When one of them is slow or down, the client correctly
    raises NET001/NET002 - that is the client behaving as designed, and says
    nothing about whether the code under test is correct. Failing the build for
    it turns someone else's uptime into our red CI: `zenodo.org ... Read timed
    out. (read timeout=3)` did exactly that.

    Only ``functional`` tests are affected, and only network error codes - an
    assertion failure or any other exception still fails normally.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return
    if "functional" not in {m.name for m in item.iter_markers()}:
        return

    exc = getattr(call, "excinfo", None)
    if exc is None:
        return

    text = str(exc.value)
    network = (
        "NET001" in text
        or "NET002" in text
        or "Read timed out" in text
        or "Max retries exceeded" in text
        or "Connection refused" in text
        or "Temporary failure in name resolution" in text
    )
    if not network:
        return

    report.outcome = "skipped"
    report.longrepr = (__file__, 0, f"third-party service unreachable: {text.splitlines()[0][:160]}")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests by location and wire up the network guard."""
    # Safety check: core deps present?
    core_deps = ["requests", "backoff", "defusedxml", "tqdm"]
    missing_core = [d for d in core_deps if not is_dependency_available(d)]
    if missing_core:
        import warnings

        warnings.warn(
            f"Core dependencies missing: {missing_core}. Many tests will be skipped.",
            stacklevel=1,
        )

    # pytest-socket registers itself under the short name "socket".
    socket_plugin = config.pluginmanager.hasplugin("socket")

    for item in items:
        categories = {m.name for m in item.iter_markers()}
        for mark_name in _infer_markers(item):
            if mark_name not in categories:
                item.add_marker(getattr(pytest.mark, mark_name))
                categories.add(mark_name)

        # Tests that may use the network: let the socket through so they work
        # when the user asks for them explicitly.
        if socket_plugin and categories & _NETWORK_CATEGORIES:
            item.add_marker(pytest.mark.enable_socket)
