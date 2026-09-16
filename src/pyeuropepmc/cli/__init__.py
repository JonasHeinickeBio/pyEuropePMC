"""
pyEuropePMC CLI — command-line interface for core operations.

Provides a ``typer``-based CLI with subcommand groups:

- ``benchmark`` — Run benchmarks, profile articles, manage datasets
- ``claim`` — Multi-agent claim verification with LangGraph
- ``normalize`` — Normalize JATS XML for text mining pipelines
- ``unified_search`` — Unified multi-source search with deduplication
- ``mcp`` — Run the MCP server (``pyeuropepmc-mcp`` by another name)

Environment
-----------
Automatically loads ``.env`` files from (in order):

1. Current working directory (``./.env``)
2. Parent directories of CWD
3. ``~/.config/pyeuropepmc/.env``

Key variables: ``OPENAI_API_KEY``, ``OPENAI_MODEL``, ``OPENAI_BASE_URL``,
``LLM_ENABLED``, ``LLM_CACHE_ENABLED``.
"""

from __future__ import annotations

from pyeuropepmc._optional_imports import OptionalDependencyError

# Load .env file before anything else
from pyeuropepmc.utils.env_loader import load_env as _load_env

_load_env()

try:
    import typer
except ImportError:
    raise OptionalDependencyError(
        "typer", "CLI interface", "pip install pyeuropepmc[standard]"
    ) from None

from pyeuropepmc.cli.benchmark import benchmark_app
from pyeuropepmc.cli.claim import claim_app
from pyeuropepmc.cli.normalize import normalize_app
from pyeuropepmc.cli.unified_search import app as unified_search_app

app = typer.Typer(
    name="pyeuropepmc",
    help="pyEuropePMC — Python toolkit for Europe PMC",
    no_args_is_help=True,
)

app.add_typer(benchmark_app, name="benchmark", help="Benchmark XML parser quality and performance")
app.add_typer(claim_app, name="claim", help="Multi-agent claim verification with LangGraph")
app.add_typer(normalize_app, name="normalize", help="Normalize JATS XML for text mining pipelines")
app.add_typer(
    unified_search_app,
    name="unified_search",
    help="Unified multi-source search with deduplication",
)


@app.command(
    name="mcp",
    help="Run the MCP server (the same server as the pyeuropepmc-mcp command)",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        # The server's own argument parser owns --transport, --host, --port,
        # --log-level and --help; click must not intercept them.
        "help_option_names": [],
    },
)
def mcp_command(ctx: typer.Context) -> None:
    """Run the MCP server.

    ``pyeuropepmc-mcp`` is the same server. This subcommand exists because a
    client that launches the package with ``uvx pyeuropepmc`` gets the console
    script named after the distribution - this CLI - and has no way to ask for
    the other one; ``uvx pyeuropepmc mcp`` reaches the server with no install.
    """
    from pyeuropepmc.mcp.server import _main_entry

    _main_entry(ctx.args)


if __name__ == "__main__":
    app()
