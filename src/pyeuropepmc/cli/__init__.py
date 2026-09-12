"""
pyEuropePMC CLI — command-line interface for core operations.

Provides a ``typer``-based CLI with subcommand groups:

- ``benchmark`` — Run benchmarks, profile articles, manage datasets
- ``claim`` — Multi-agent claim verification with LangGraph
- ``normalize`` — Normalize JATS XML for text mining pipelines

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


if __name__ == "__main__":
    app()
