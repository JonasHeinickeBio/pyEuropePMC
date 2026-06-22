"""
pyEuropePMC CLI — command-line interface for core operations.

Provides a ``typer``-based CLI with subcommand groups:

- ``benchmark`` — Run benchmarks, profile articles, manage datasets
- ``normalize`` — Normalize JATS XML for text mining pipelines
"""

from __future__ import annotations

import typer

from pyeuropepmc.cli.benchmark import benchmark_app
from pyeuropepmc.cli.normalize import normalize_app

app = typer.Typer(
    name="pyeuropepmc",
    help="pyEuropePMC — Python toolkit for Europe PMC",
    no_args_is_help=True,
)

app.add_typer(benchmark_app, name="benchmark", help="Benchmark XML parser quality and performance")
app.add_typer(normalize_app, name="normalize", help="Normalize JATS XML for text mining pipelines")


if __name__ == "__main__":
    app()
