"""
Flask web application for the multi-agent claim verification workflow.

Provides a browser-based UI where users can:
1. Input a sentence or paragraph for analysis
2. Review extracted claims with evidence
3. Accept/reject each claim
4. View the improved text with citations
5. Download the bibliography

The app uses the ``SupervisorClaimWorkflow`` (LangGraph) for workflow
execution and stores state in memory for simplicity.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import secrets
from threading import Lock
from typing import Any
import uuid

from pyeuropepmc.agentic.langgraph.claims_graph import build_supervisor_graph

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Flask import
# ---------------------------------------------------------------------------

try:
    from flask import Flask, jsonify, render_template, request, send_file, url_for

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    render_template = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]
    send_file = None  # type: ignore[assignment]
    url_for = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# In-memory workflow store
# ---------------------------------------------------------------------------

_workflows: dict[str, dict[str, Any]] = {}
_workflows_lock = Lock()
TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def _get_template_folder() -> str:
    """Get the absolute path to the templates directory."""
    return str(TEMPLATE_DIR.resolve())


def _get_static_folder() -> str:
    """Get the absolute path to the static directory."""
    return str(STATIC_DIR.resolve())


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(testing: bool = False) -> Flask:
    """
    Create and configure the Flask application.

    Parameters
    ----------
    testing : bool, optional
        If True, enables testing mode (errors propagate, no template caching)

    Returns
    -------
    Flask
        Configured Flask application
    """
    if not FLASK_AVAILABLE:
        raise ImportError("Flask is required for the UI. Install with: pip install flask")

    app = Flask(
        __name__,
        template_folder=_get_template_folder(),
        static_folder=_get_static_folder(),
    )
    # Random per-process key: this UI keeps all state in memory and has no
    # persistent sessions across restarts, so a stable key isn't needed.
    app.config["SECRET_KEY"] = os.environ.get("PYEUROPEPMC_UI_SECRET_KEY") or secrets.token_hex(32)
    app.config["TESTING"] = testing

    # ------------------------------------------------------------------ #
    # Routes — pages
    # ------------------------------------------------------------------ #

    @app.route("/", methods=["GET"])
    def index():
        """Landing page: input text for analysis."""
        return render_template("index.html")

    @app.route("/workflow/<workflow_id>/review", methods=["GET"])
    def review_page(workflow_id: str):
        """Review page: browse claims and accept/reject."""
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return render_template("error.html", message="Workflow not found."), 404

        if wf.get("status") == "error":
            return render_template("error.html", message=wf.get("error", "Unknown error")), 500

        claims = _claims_for_display(wf.get("verified_claims", []))
        review = wf.get("review", {})
        decisions = wf.get("user_decisions", {})

        return render_template(
            "review.html",
            workflow_id=workflow_id,
            claims=claims,
            review=review,
            decisions=decisions,
            progress=wf.get("workflow_progress", 0.0),
        )

    @app.route("/workflow/<workflow_id>/results", methods=["GET"])
    def results_page(workflow_id: str):
        """Results page: view improved text and bibliography."""
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return render_template("error.html", message="Workflow not found."), 404

        return render_template(
            "results.html",
            workflow_id=workflow_id,
            improved_text=wf.get("improved_text", ""),
            original_text=wf.get("source_text", ""),
            bibliography=wf.get("bibliography", []),
            review=wf.get("review", {}),
            progress=wf.get("workflow_progress", 0.0),
        )

    # ------------------------------------------------------------------ #
    # Routes — API
    # ------------------------------------------------------------------ #

    @app.route("/api/workflow/start", methods=["POST"])
    def api_start_workflow():
        """
        Start a new claim verification workflow.

        Request JSON::

            {"text": "...", "auto_accept": false, "bib_format": "bibtex"}

        Response::

            {"workflow_id": "...", "status": "started"}
        """
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"error": "No text provided"}), 400

        auto_accept = data.get("auto_accept", False)
        bib_format = data.get("bib_format", "bibtex")

        workflow_id = uuid.uuid4().hex[:12]

        try:
            graph = build_supervisor_graph(llm_enabled=True, use_checkpointer=False)
            result = graph.invoke(
                source_text=text,
                auto_accept=auto_accept,
                bibliography_format=bib_format,
            )

            with _workflows_lock:
                _workflows[workflow_id] = {
                    **result,
                    "workflow_id": workflow_id,
                    "status": "error"
                    if result.get("supervisor_phase") == "failed"
                    else "complete",
                }

            wf = _workflows[workflow_id]

            if wf["status"] == "error":
                return jsonify(
                    {
                        "workflow_id": workflow_id,
                        "status": "error",
                        "error": " | ".join(wf.get("errors", [])),
                    }
                ), 500

            # If auto_accept, go straight to results
            if auto_accept:
                return jsonify(
                    {
                        "workflow_id": workflow_id,
                        "status": "complete",
                        "redirect": url_for("results_page", workflow_id=workflow_id),
                    }
                )

            # Otherwise, go to review
            return jsonify(
                {
                    "workflow_id": workflow_id,
                    "status": "needs_review",
                    "redirect": url_for("review_page", workflow_id=workflow_id),
                }
            )

        except Exception as e:
            logger.error("Workflow error: %s", e)
            with _workflows_lock:
                _workflows[workflow_id] = {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": str(e),
                    "source_text": text,
                }
            # Log the real exception server-side only; the client gets a
            # generic message so internal details (paths, internals) never
            # leak through the API response.
            return jsonify(
                {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": "An internal error occurred while running the workflow.",
                }
            ), 500

    @app.route("/api/workflow/<workflow_id>/status", methods=["GET"])
    def api_workflow_status(workflow_id: str):
        """Get the current status of a workflow."""
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return jsonify({"error": "Workflow not found"}), 404

        return jsonify(
            {
                "workflow_id": workflow_id,
                "status": wf.get("status", "unknown"),
                "progress": wf.get("workflow_progress", 0.0),
                "claims_count": len(wf.get("verified_claims", [])),
                "output_complete": wf.get("output_complete", False),
            }
        )

    @app.route("/api/workflow/<workflow_id>/decisions", methods=["POST"])
    def api_submit_decisions(workflow_id: str):
        """
        Submit user decisions for claim acceptance/rejection.

        Request JSON::

            {"decisions": {"claim_id_1": true, "claim_id_2": false, ...}}

        The server will run the write phase with these decisions and
        redirect to the results page.
        """
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return jsonify({"error": "Workflow not found"}), 404

        data = request.get_json(silent=True) or {}
        decisions = data.get("decisions", {})

        if not decisions:
            return jsonify({"error": "No decisions provided"}), 400

        # Store decisions
        wf["user_decisions"] = decisions
        wf["decisions_complete"] = True

        # Run write phase with these decisions
        try:
            from pyeuropepmc.claims.writer import ClaimWriter

            writer = ClaimWriter(llm_enabled=True)
            source_text = wf.get("source_text", "")

            # Reconstruct claim set from verified claims
            from pyeuropepmc.claims.models import Claim, ClaimSet

            claims = [Claim.from_dict(c) for c in wf.get("verified_claims", [])]
            claim_set = ClaimSet(source_text=source_text, claims=claims)

            report = writer.write_report(
                original_text=source_text,
                claim_set=claim_set,
                user_decisions=decisions,
                bibliography_format=wf.get("bibliography_format", "bibtex"),
            )

            review = wf.get("review", {})
            report.review_notes = review.get("llm_review")

            wf["improved_text"] = report.improved_text
            wf["bibliography"] = report.bibliography
            wf["output_complete"] = True
            wf["workflow_progress"] = 1.0
            wf["status"] = "complete"

        except Exception as e:
            logger.error("Write phase error: %s", e)
            wf["status"] = "error"
            wf["error"] = str(e)
            # Log the real exception server-side only; the client gets a
            # generic message so internal details never leak through the API.
            return jsonify({"error": "An internal error occurred while writing the report."}), 500

        return jsonify(
            {
                "status": "complete",
                "redirect": url_for("results_page", workflow_id=workflow_id),
            }
        )

    @app.route("/api/workflow/<workflow_id>/bibliography", methods=["GET"])
    def api_download_bibliography(workflow_id: str):
        """Download the bibliography as a file."""
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return jsonify({"error": "Workflow not found"}), 404

        bib = wf.get("bibliography", [])
        bib_format = wf.get("bibliography_format", "bibtex")

        if bib_format == "bibtex":
            content = _bib_to_bibtex(bib)
            filename = f"bibliography_{workflow_id}.bib"
            mimetype = "application/x-bibtex"
        elif bib_format == "ris":
            content = _bib_to_ris(bib)
            filename = f"bibliography_{workflow_id}.ris"
            mimetype = "application/x-research-info-systems"
        else:
            content = json.dumps(bib, indent=2)
            filename = f"bibliography_{workflow_id}.json"
            mimetype = "application/json"

        return jsonify(
            {
                "content": content,
                "filename": filename,
                "mimetype": mimetype,
            }
        )

    @app.route("/api/workflow/<workflow_id>/claims", methods=["GET"])
    def api_get_claims(workflow_id: str):
        """Get the claims for review (for AJAX-based UI)."""
        with _workflows_lock:
            wf = _workflows.get(workflow_id)

        if wf is None:
            return jsonify({"error": "Workflow not found"}), 404

        claims = _claims_for_display(wf.get("verified_claims", []))
        return jsonify(
            {
                "claims": claims,
                "review": wf.get("review", {}),
                "decisions": wf.get("user_decisions", {}),
            }
        )

    return app


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _claims_for_display(verified_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format claims for template rendering."""
    display = []
    for c in verified_claims:
        display.append(
            {
                "id": c.get("id", ""),
                "text": c.get("text", ""),
                "claim_type": c.get("claim_type", "other"),
                "confidence": c.get("confidence", 0.0),
                "verdict": c.get("verdict", "not_checked"),
                "evidence": [
                    {
                        "text": e.get("text", "")[:200],
                        "paper_title": e.get("paper_title", "")[:80],
                        "authors": e.get("authors", "")[:60],
                        "source": e.get("source", ""),
                        "year": e.get("year"),
                        "journal": e.get("journal", ""),
                        "relevance_score": e.get("relevance_score", 0.0),
                        "quality": e.get("quality", "medium"),
                    }
                    for e in c.get("evidence", [])
                ],
                "verification_reasoning": c.get("verification_reasoning", ""),
            }
        )
    return display


def _bib_to_bibtex(bibliography: list[dict[str, Any]]) -> str:
    """Convert bibliography list to BibTeX format string."""
    lines = []
    for i, entry in enumerate(bibliography):
        cite_key = entry.get("cite_key", f"ref{i + 1}")
        lines.append(f"@{entry.get('type', 'article')}{{{cite_key},")
        for key in (
            "author",
            "title",
            "journal",
            "year",
            "volume",
            "number",
            "pages",
            "doi",
            "url",
        ):
            value = entry.get(key)
            if value:
                lines.append(f"  {key} = {{{value}}},")
        lines.append("}\n")
    return "\n".join(lines)


def _bib_to_ris(bibliography: list[dict[str, Any]]) -> str:
    """Convert bibliography list to RIS format string."""
    lines = ["TY  - JOUR"]
    for entry in bibliography:
        if entry.get("author"):
            for author in str(entry["author"]).split(" and "):
                lines.append(f"AU  - {author.strip()}")
        if entry.get("title"):
            lines.append(f"TI  - {entry['title']}")
        if entry.get("journal"):
            lines.append(f"JO  - {entry['journal']}")
        if entry.get("year"):
            lines.append(f"PY  - {entry['year']}")
        if entry.get("doi"):
            lines.append(f"DO  - {entry['doi']}")
        if entry.get("url"):
            lines.append(f"UR  - {entry['url']}")
        lines.append("ER  - \n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("PYEUROPEPMC_UI_DEBUG") == "1"
    logger.info("Starting pyEuropePMC UI on http://127.0.0.1:5000")
    app.run(debug=debug, host="127.0.0.1", port=5000)  # nosec B201 - localhost dev server


__all__ = ["create_app"]
