"""
Web UI for the multi-agent claim verification workflow.

Provides a Flask web application that wraps the LangGraph-based
``SupervisorClaimWorkflow`` with:

- Text input page: enter sentences/paragraphs for analysis
- Claim review page: browse claims with evidence, accept/reject
- Results page: view improved text, download bibliography
- REST API for programmatic access and async workflow execution

The UI stores workflow state in memory (suitable for single-user or
development use).  For production, replace with a database backend.

Usage
-----
Start the development server::

    python -m pyeuropepmc.ui.app

Or programmatically within an existing Flask app::

    from pyeuropepmc.ui.app import create_app
    app = create_app()
    app.run()
"""

from pyeuropepmc.ui.app import create_app

__all__ = ["create_app"]
