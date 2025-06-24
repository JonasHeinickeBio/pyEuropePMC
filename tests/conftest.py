import json
from pathlib import Path

import pytest

# Base directory for fixtures
FIXTURE_DIR = Path(__file__).parent / "fixtures"


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
