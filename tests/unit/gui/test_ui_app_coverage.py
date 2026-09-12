"""Additional coverage for pyeuropepmc.ui.app: RIS/JSON bibliography export,
_bib_to_ris directly, and the review page's error-status branch.
"""

from __future__ import annotations

import json

import pytest

from pyeuropepmc.ui.app import _bib_to_ris, _workflows, _workflows_lock, create_app

pytestmark = pytest.mark.gui


def _check_flask() -> bool:
    try:
        import flask  # noqa: F401

        return True
    except ImportError:
        return False


FLASK_AVAILABLE = _check_flask()


class TestBibToRis:
    def test_full_entry(self):
        bib = [
            {
                "author": "Smith J and Doe A",
                "title": "A Great Paper",
                "journal": "J Test",
                "year": "2024",
                "doi": "10.1/x",
                "url": "http://example.org",
            }
        ]
        text = _bib_to_ris(bib)
        assert "TY  - JOUR" in text
        assert "AU  - Smith J" in text
        assert "AU  - Doe A" in text
        assert "TI  - A Great Paper" in text
        assert "JO  - J Test" in text
        assert "PY  - 2024" in text
        assert "DO  - 10.1/x" in text
        assert "UR  - http://example.org" in text
        assert "ER  -" in text

    def test_minimal_entry(self):
        text = _bib_to_ris([{}])
        assert text.startswith("TY  - JOUR")
        assert "AU  -" not in text

    def test_empty_bibliography(self):
        assert _bib_to_ris([]) == "TY  - JOUR"


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestBibliographyDownloadFormats:
    def _seed_workflow(self, wf_id: str, bib_format: str) -> None:
        with _workflows_lock:
            _workflows[wf_id] = {
                "bibliography": [
                    {"cite_key": "ref1", "title": "T", "author": "Smith J", "year": "2024"}
                ],
                "bibliography_format": bib_format,
            }

    def test_ris_format(self):
        app = create_app(testing=True)
        self._seed_workflow("wf-ris", "ris")
        with app.test_client() as client:
            resp = client.get("/api/workflow/wf-ris/bibliography")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["filename"].endswith(".ris")
        assert "TY  - JOUR" in data["content"]

    def test_json_format(self):
        app = create_app(testing=True)
        self._seed_workflow("wf-json", "json")
        with app.test_client() as client:
            resp = client.get("/api/workflow/wf-json/bibliography")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["filename"].endswith(".json")
        parsed = json.loads(data["content"])
        assert parsed[0]["cite_key"] == "ref1"

    def test_default_bibtex_format(self):
        app = create_app(testing=True)
        with _workflows_lock:
            _workflows["wf-default"] = {
                "bibliography": [{"cite_key": "ref1", "type": "article", "title": "T"}]
            }
        with app.test_client() as client:
            resp = client.get("/api/workflow/wf-default/bibliography")
        assert resp.status_code == 200
        assert resp.get_json()["filename"].endswith(".bib")


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestReviewPageErrorStatus:
    def test_review_page_returns_500_when_workflow_errored(self):
        app = create_app(testing=True)
        with _workflows_lock:
            _workflows["wf-err"] = {"status": "error", "error": "boom"}
        with app.test_client() as client:
            resp = client.get("/workflow/wf-err/review")
        assert resp.status_code == 500
