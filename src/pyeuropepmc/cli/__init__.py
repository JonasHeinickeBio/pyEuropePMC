"""
pyEuropePMC CLI — command-line interface for core operations.

Provides a ``typer``-based CLI with subcommand groups:

- ``benchmark`` — Run benchmarks, profile articles, manage datasets
"""

from __future__ import annotations

import typer

from pyeuropepmc.cli.benchmark import benchmark_app

app = typer.Typer(
    name="pyeuropepmc",
    help="pyEuropePMC — Python toolkit for Europe PMC",
    no_args_is_help=True,
)

app.add_typer(benchmark_app, name="benchmark", help="Benchmark XML parser quality and performance")


if __name__ == "__main__":
    app()
