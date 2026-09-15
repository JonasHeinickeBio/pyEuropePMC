"""Tests for the Flask web UI (pyeuropepmc/ui/app.py)."""

import json

import pytest

# Mark all tests in this module
pytestmark = pytest.mark.gui


def _check_flask():
    """Check if Flask is available."""
    try:
        import flask  # noqa: F401

        return True
    except ImportError:
        return False


FLASK_AVAILABLE = _check_flask()


# ======================================================================= #
# App creation tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestAppCreation:
    def test_create_app(self):
        """create_app should return a Flask app."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        assert app is not None
        assert app.testing is True

    def test_app_has_secret_key(self):
        """App should have a secret key configured."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        assert app.config.get("SECRET_KEY") is not None

    def test_app_routes_exist(self):
        """App should have the expected routes registered."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        rules = [r.rule for r in app.url_map.iter_rules()]
        expected_routes = [
            "/",
            "/api/workflow/start",
            "/api/workflow/<workflow_id>/status",
            "/api/workflow/<workflow_id>/decisions",
            "/api/workflow/<workflow_id>/bibliography",
            "/api/workflow/<workflow_id>/claims",
            "/workflow/<workflow_id>/review",
            "/workflow/<workflow_id>/results",
        ]
        for route in expected_routes:
            assert route in rules, f"Missing route: {route}"


# ======================================================================= #
# Page route tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestPageRoutes:
    def test_index_page_returns_200(self):
        """GET / should return the index page."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/")
            assert resp.status_code == 200
            assert resp.mimetype == "text/html"

    def test_workflow_review_404_for_unknown(self):
        """GET /workflow/{id}/review for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/workflow/unknown123/review")
            assert resp.status_code == 404

    def test_workflow_results_404_for_unknown(self):
        """GET /workflow/{id}/results for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/workflow/unknown123/results")
            assert resp.status_code == 404


# ======================================================================= #
# API: start workflow tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiStartWorkflow:
    def test_start_with_valid_text_auto_accept(self, monkeypatch):
        """POST /api/workflow/start with text and auto_accept should succeed."""
        from pyeuropepmc.ui.app import create_app

        # Mock build_supervisor_graph to return a mock graph
        mock_result = {
            "source_text": "Test claim.",
            "claims_raw": [{"id": "c1", "text": "Test claim"}],
            "extraction_complete": True,
            "verified_claims": [{"id": "c1", "text": "Test claim", "evidence": []}],
            "verification_complete": True,
            "verification_summary": {"total": 1, "supported": 1},
            "review": {"overall_quality": "high", "suggestions": []},
            "review_complete": True,
            "user_decisions": {"c1": True},
            "decisions_complete": True,
            "improved_text": "Improved text with citation.",
            "bibliography": [{"cite_key": "ref1", "title": "Test"}],
            "output_complete": True,
            "errors": [],
            "warnings": [],
            "agent_messages": [],
            "supervisor_phase": "done",
            "workflow_progress": 1.0,
            "retry_count": 0,
            "max_retries": 2,
            "llm_enabled": True,
            "auto_accept": True,
            "bibliography_format": "bibtex",
            "workflow_id": "mock123",
            "current_node": "__end__",
        }

        class MockGraph:
            def invoke(self, **kwargs):
                r = dict(mock_result)
                r["workflow_id"] = (
                    kwargs.get("config", {}).get("configurable", {}).get("thread_id", "mock123")
                )
                return r

            def compile(self):
                return self

        def mock_build(*args, **kwargs):
            return MockGraph()

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            mock_build,
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Test claim.", "auto_accept": True}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert data["status"] == "complete"
            assert "redirect" in data
            assert "/workflow/" in data["redirect"]

    def test_start_without_text_returns_400(self):
        """POST /api/workflow/start without text should return 400."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/start",
                data=json.dumps({}),
                content_type="application/json",
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data is not None
            assert "error" in data

    def test_start_with_empty_text_returns_400(self):
        """POST /api/workflow/start with empty text should return 400."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": ""}),
                content_type="application/json",
            )
            assert resp.status_code == 400

    def test_start_with_auto_accept_false(self, monkeypatch):
        """POST with auto_accept=False should return status needs_review."""
        from pyeuropepmc.ui.app import create_app

        mock_result = {
            "source_text": "Claim text.",
            "claims_raw": [{"id": "c1", "text": "Claim text"}],
            "extraction_complete": True,
            "verified_claims": [{"id": "c1", "text": "Claim text", "evidence": []}],
            "verification_complete": True,
            "verification_summary": {"total": 1, "supported": 1},
            "review": {"overall_quality": "medium", "suggestions": []},
            "review_complete": True,
            "user_decisions": {},
            "decisions_complete": False,
            "improved_text": "",
            "bibliography": [],
            "output_complete": False,
            "errors": [],
            "warnings": [],
            "agent_messages": [],
            "supervisor_phase": "review",
            "workflow_progress": 0.55,
            "retry_count": 0,
            "max_retries": 2,
            "llm_enabled": True,
            "auto_accept": False,
            "bibliography_format": "bibtex",
            "workflow_id": "mock456",
            "current_node": "supervisor",
        }

        class MockGraphNeedsReview:
            def invoke(self, **kwargs):
                return dict(mock_result)

            def compile(self):
                return self

        def mock_build(*args, **kwargs):
            return MockGraphNeedsReview()

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            mock_build,
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Claim text.", "auto_accept": False}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert data["status"] == "needs_review"
            assert "redirect" in data
            assert "/review" in data["redirect"]


# ======================================================================= #
# API: workflow status tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiWorkflowStatus:
    def test_status_404_for_unknown(self):
        """GET /api/workflow/{id}/status for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/api/workflow/unknown123/status")
            assert resp.status_code == 404

    def test_status_after_start(self, monkeypatch):
        """GET /api/workflow/{id}/status should return workflow info."""
        from pyeuropepmc.ui.app import create_app

        mock_result = {
            "source_text": "Status test.",
            "claims_raw": [],
            "extraction_complete": True,
            "verified_claims": [],
            "verification_complete": True,
            "verification_summary": {},
            "review": {},
            "review_complete": True,
            "user_decisions": {},
            "decisions_complete": True,
            "improved_text": "Improved.",
            "bibliography": [],
            "output_complete": True,
            "errors": [],
            "warnings": [],
            "agent_messages": [],
            "supervisor_phase": "done",
            "workflow_progress": 1.0,
            "retry_count": 0,
            "max_retries": 2,
            "llm_enabled": True,
            "auto_accept": True,
            "bibliography_format": "bibtex",
            "workflow_id": "status123",
            "current_node": "__end__",
        }

        class MockGraph:
            def invoke(self, **kwargs):
                return dict(mock_result)

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start a workflow first
            start_resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Status test.", "auto_accept": True}),
                content_type="application/json",
            )
            assert start_resp.status_code == 200
            wf_id = start_resp.get_json()["workflow_id"]

            # Check status
            resp = client.get(f"/api/workflow/{wf_id}/status")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert data["workflow_id"] == wf_id
            assert "status" in data
            assert "progress" in data


# ======================================================================= #
# API: decisions tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiDecisions:
    def test_decisions_404_for_unknown(self):
        """POST /api/workflow/{id}/decisions for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/unknown123/decisions",
                data=json.dumps({"decisions": {"c1": True}}),
                content_type="application/json",
            )
            assert resp.status_code == 404

    def test_decisions_without_decisions_returns_400(self, monkeypatch):
        """POST without decisions field should return 400."""
        from pyeuropepmc.ui.app import create_app

        class MockGraph:
            def invoke(self, **kwargs):
                return {
                    "source_text": "Test.",
                    "verified_claims": [{"id": "c1", "text": "Test claim", "evidence": []}],
                    "bibliography_format": "bibtex",
                    "review": {"overall_quality": "high", "llm_review": "Good"},
                    "workflow_id": "mock789",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start a workflow
            start_resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Test.", "auto_accept": False}),
                content_type="application/json",
            )
            wf_id = start_resp.get_json()["workflow_id"]

            # Submit empty decisions
            resp = client.post(
                f"/api/workflow/{wf_id}/decisions",
                data=json.dumps({"decisions": {}}),
                content_type="application/json",
            )
            assert resp.status_code == 400

    def test_decisions_with_valid_choices(self, monkeypatch):
        """POST with valid decisions should complete the workflow."""
        from pyeuropepmc.ui.app import create_app

        # Mock ClaimWriter and Claim to avoid real dependency resolution
        class MockReport:
            improved_text = "Improved decision text."
            bibliography = [{"cite_key": "ref1", "title": "Decision Paper"}]
            review_notes = ""

        class MockWriter:
            def __init__(self, **kwargs):
                pass

            def write_report(self, **kwargs):
                return MockReport()

        class MockClaim:
            @classmethod
            def from_dict(cls, d):
                return cls()

            def to_dict(self):
                return {"id": "c1", "text": "Test"}

        class MockClaimSet:
            def __init__(self, **kwargs):
                pass

        monkeypatch.setattr("pyeuropepmc.claims.writer.ClaimWriter", MockWriter)
        monkeypatch.setattr("pyeuropepmc.claims.models.Claim", MockClaim)
        monkeypatch.setattr("pyeuropepmc.claims.models.ClaimSet", MockClaimSet)

        class MockGraph:
            def invoke(self, **kwargs):
                return {
                    "source_text": "Test decision.",
                    "extraction_complete": True,
                    "verified_claims": [
                        {
                            "id": "c1",
                            "text": "Test claim",
                            "evidence": [],
                            "verdict": "supported",
                            "confidence": 0.9,
                        }
                    ],
                    "verification_complete": True,
                    "review": {"overall_quality": "high", "llm_review": "Looks good"},
                    "review_complete": True,
                    "user_decisions": {},
                    "decisions_complete": False,
                    "bibliography_format": "bibtex",
                    "workflow_id": "dec123",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start flow
            start_resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Test decision.", "auto_accept": False}),
                content_type="application/json",
            )
            wf_id = start_resp.get_json()["workflow_id"]

            # Submit decisions
            resp = client.post(
                f"/api/workflow/{wf_id}/decisions",
                data=json.dumps({"decisions": {"c1": True}}),
                content_type="application/json",
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert data["status"] == "complete"
            assert "redirect" in data
            assert "/results" in data["redirect"]


# ======================================================================= #
# API: bibliography tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiBibliography:
    def test_bibliography_404_for_unknown(self):
        """GET /api/workflow/{id}/bibliography for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/api/workflow/unknown123/bibliography")
            assert resp.status_code == 404

    def test_bibliography_returns_content(self, monkeypatch):
        """GET /api/workflow/{id}/bibliography should return BibTeX content."""
        from pyeuropepmc.ui.app import create_app

        class MockGraph:
            def invoke(self, **kwargs):
                return {
                    "source_text": "Bib test.",
                    "extraction_complete": True,
                    "verified_claims": [],
                    "verification_complete": True,
                    "review": {},
                    "review_complete": True,
                    "user_decisions": {},
                    "decisions_complete": True,
                    "improved_text": "Improved.",
                    "bibliography": [
                        {
                            "cite_key": "ref1",
                            "type": "article",
                            "title": "Test Article",
                            "author": "Smith J",
                            "journal": "Test Journal",
                            "year": "2024",
                        }
                    ],
                    "output_complete": True,
                    "bibliography_format": "bibtex",
                    "workflow_id": "bib123",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start flow
            start_resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Bib test.", "auto_accept": True}),
                content_type="application/json",
            )
            assert start_resp.status_code == 200
            wf_id = start_resp.get_json()["workflow_id"]

            # Get bibliography
            resp = client.get(f"/api/workflow/{wf_id}/bibliography")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert "content" in data
            assert "filename" in data
            assert data["filename"].endswith(".bib")


# ======================================================================= #
# API: claims tests
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiClaims:
    def test_claims_404_for_unknown(self):
        """GET /api/workflow/{id}/claims for unknown id should return 404."""
        from pyeuropepmc.ui.app import create_app

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.get("/api/workflow/unknown123/claims")
            assert resp.status_code == 404

    def test_claims_returns_claims(self, monkeypatch):
        """GET /api/workflow/{id}/claims should return formatted claims."""
        from pyeuropepmc.ui.app import create_app

        class MockGraph:
            def invoke(self, **kwargs):
                return {
                    "source_text": "Claims test.",
                    "extraction_complete": True,
                    "verified_claims": [
                        {
                            "id": "c1",
                            "text": "This is a claim.",
                            "claim_type": "finding",
                            "confidence": 0.85,
                            "verdict": "supported",
                            "evidence": [
                                {
                                    "text": "Evidence text.",
                                    "paper_title": "Test Paper",
                                    "authors": "Smith J",
                                    "source": "MED",
                                    "year": 2024,
                                    "journal": "Test J",
                                    "relevance_score": 0.9,
                                    "quality": "high",
                                }
                            ],
                            "verification_reasoning": "Good evidence.",
                        }
                    ],
                    "verification_complete": True,
                    "review": {"overall_quality": "high", "suggestions": []},
                    "review_complete": True,
                    "user_decisions": {},
                    "decisions_complete": False,
                    "bibliography_format": "bibtex",
                    "workflow_id": "claim123",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start flow
            start_resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Claims test.", "auto_accept": False}),
                content_type="application/json",
            )
            assert start_resp.status_code == 200
            wf_id = start_resp.get_json()["workflow_id"]

            # Get claims
            resp = client.get(f"/api/workflow/{wf_id}/claims")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data is not None
            assert "claims" in data
            assert len(data["claims"]) == 1
            assert data["claims"][0]["id"] == "c1"
            assert "evidence" in data["claims"][0]
            assert len(data["claims"][0]["evidence"]) == 1


# ======================================================================= #
# Integration: full workflow via API
# ======================================================================= #


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestApiFullWorkflow:
    def test_full_workflow_auto_accept(self, monkeypatch):
        """Full workflow with auto_accept should complete end-to-end."""
        from pyeuropepmc.ui.app import create_app

        call_count = 0

        class MockGraph:
            def invoke(self, **kwargs):
                nonlocal call_count
                call_count += 1
                return {
                    "source_text": "Full test.",
                    "extraction_complete": True,
                    "claims_raw": [{"id": "c1", "text": "Full test claim"}],
                    "verified_claims": [{"id": "c1", "text": "Full test claim", "evidence": []}],
                    "verification_complete": True,
                    "verification_summary": {"total": 1, "supported": 1},
                    "review": {"overall_quality": "high", "suggestions": []},
                    "review_complete": True,
                    "user_decisions": {"c1": True},
                    "decisions_complete": True,
                    "improved_text": "Improved full text (1).",
                    "bibliography": [{"cite_key": "ref1", "title": "Full Test"}],
                    "output_complete": True,
                    "errors": [],
                    "bibliography_format": "bibtex",
                    "workflow_id": "full123",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start
            resp1 = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Full test.", "auto_accept": True}),
                content_type="application/json",
            )
            assert resp1.status_code == 200
            data1 = resp1.get_json()
            wf_id = data1["workflow_id"]

            # Status
            resp2 = client.get(f"/api/workflow/{wf_id}/status")
            assert resp2.status_code == 200

            # Bibliography
            resp3 = client.get(f"/api/workflow/{wf_id}/bibliography")
            assert resp3.status_code == 200

            # Results page
            resp4 = client.get(f"/workflow/{wf_id}/results")
            assert resp4.status_code == 200

    def test_full_workflow_with_review(self, monkeypatch):
        """Workflow with user review should work end-to-end."""
        from pyeuropepmc.ui.app import create_app

        # Mock ClaimWriter to avoid real dependency resolution in decisions endpoint
        class MockReport:
            improved_text = "Improved review text."
            bibliography = [{"cite_key": "ref1", "title": "Review Paper"}]
            review_notes = ""

        class MockWriter:
            def __init__(self, **kwargs):
                pass

            def write_report(self, **kwargs):
                return MockReport()

        class MockClaim:
            @classmethod
            def from_dict(cls, d):
                return cls()

            def to_dict(self):
                return {"id": "c1"}

        class MockClaimSet:
            def __init__(self, **kwargs):
                pass

        monkeypatch.setattr("pyeuropepmc.claims.writer.ClaimWriter", MockWriter)
        monkeypatch.setattr("pyeuropepmc.claims.models.Claim", MockClaim)
        monkeypatch.setattr("pyeuropepmc.claims.models.ClaimSet", MockClaimSet)

        class MockGraph:
            def invoke(self, **kwargs):
                return {
                    "source_text": "Review test.",
                    "extraction_complete": True,
                    "claims_raw": [{"id": "c1", "text": "Review test claim"}],
                    "verified_claims": [
                        {
                            "id": "c1",
                            "text": "Review test claim",
                            "claim_type": "finding",
                            "confidence": 0.9,
                            "verdict": "supported",
                            "evidence": [],
                            "verification_reasoning": "Solid.",
                        }
                    ],
                    "verification_complete": True,
                    "verification_summary": {"total": 1, "supported": 1},
                    "review": {"overall_quality": "high", "llm_review": "Good job"},
                    "review_complete": True,
                    "user_decisions": {},
                    "decisions_complete": False,
                    "bibliography_format": "bibtex",
                    "workflow_id": "review123",
                }

            def compile(self):
                return self

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            lambda *a, **kw: MockGraph(),
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            # Start (no auto_accept)
            resp1 = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Review test.", "auto_accept": False}),
                content_type="application/json",
            )
            assert resp1.status_code == 200
            data1 = resp1.get_json()
            assert data1["status"] == "needs_review"
            wf_id = data1["workflow_id"]

            # Review page
            resp2 = client.get(f"/workflow/{wf_id}/review")
            assert resp2.status_code == 200

            # Claims API
            resp3 = client.get(f"/api/workflow/{wf_id}/claims")
            assert resp3.status_code == 200
            claims_data = resp3.get_json()
            assert len(claims_data["claims"]) == 1

            # Submit decisions
            resp4 = client.post(
                f"/api/workflow/{wf_id}/decisions",
                data=json.dumps({"decisions": {"c1": True}}),
                content_type="application/json",
            )
            assert resp4.status_code == 200

            # Results page
            resp5 = client.get(f"/workflow/{wf_id}/results")
            assert resp5.status_code == 200

    def test_workflow_error_handled_gracefully(self, monkeypatch):
        """Workflow that raises an exception should return 500 with error."""
        from pyeuropepmc.ui.app import create_app

        def failing_build(*args, **kwargs):
            raise RuntimeError("Simulated workflow failure")

        monkeypatch.setattr(
            "pyeuropepmc.ui.app.build_supervisor_graph",
            failing_build,
        )

        app = create_app(testing=True)
        with app.test_client() as client:
            resp = client.post(
                "/api/workflow/start",
                data=json.dumps({"text": "Fail test.", "auto_accept": True}),
                content_type="application/json",
            )
            assert resp.status_code == 500
            data = resp.get_json()
            assert data is not None
            assert "error" in data
            # The API response carries a generic message (the real exception
            # is logged server-side only, never exposed to the client).
            assert "Simulated workflow failure" not in data["error"]
            assert data["error"]
