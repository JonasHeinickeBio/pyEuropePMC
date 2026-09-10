"""
CLI commands for the multi-agent claim verification workflow.

Provides command-line access to the LangGraph-based claim verification
pipeline with supervisor-driven sub-agents, parallel verification,
and the Flask web UI.

Usage::

    # Run the full pipeline with a text argument
    pyeuropepmc claim verify "CRISPR-Cas9 corrects 75% of mutations." --auto-accept

    # Run with text from a file
    pyeuropepmc claim verify --file paragraph.txt --auto-accept

    # Stream node-by-node progress
    pyeuropepmc claim stream "ME/CFS is a heterogeneous disease."

    # Start the web UI
    pyeuropepmc claim serve
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from pyeuropepmc._optional_imports import OptionalDependencyError

try:
    import typer
except ImportError:
    raise OptionalDependencyError(
        "typer", "CLI interface", "pip install pyeuropepmc[standard]"
    ) from None

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]
    Progress = None  # type: ignore[assignment]
    SpinnerColumn = None  # type: ignore[assignment]
    TextColumn = None  # type: ignore[assignment]
    BarColumn = None  # type: ignore[assignment]
    TimeRemainingColumn = None  # type: ignore[assignment]
    Rule = None  # type: ignore[assignment]
    Syntax = None  # type: ignore[assignment]
    Text = None  # type: ignore[assignment]

from pyeuropepmc.agentic.langgraph import (
    LANGGRAPH_AVAILABLE,
    run_supervisor_graph,
    stream_supervisor_graph,
)

claim_app = typer.Typer(
    name="claim",
    help="Multi-agent claim verification from Europe PMC literature",
    no_args_is_help=True,
)

console = Console() if Console else None


def _require_langgraph() -> None:
    """Exit with error if LangGraph is not installed."""
    if not LANGGRAPH_AVAILABLE:
        msg = (
            "LangGraph is required for the claim verification workflow.\n"
            "Install with: pip install pyeuropepmc[agentic]"
        )
        typer.echo(msg, err=True)
        raise typer.Exit(code=1) from None


def _read_text(text_arg: str | None, file_arg: Path | None) -> str:
    """Resolve the input text from argument or file.

    Precedence: ``--file`` argument > positional ``text`` > stdin.
    If both are missing, raises ``typer.Exit``.
    """
    if file_arg is not None:
        try:
            return file_arg.read_text(encoding="utf-8")
        except FileNotFoundError:
            typer.echo(f"Error: file not found: {file_arg}", err=True)
            raise typer.Exit(code=1) from None
        except Exception as e:
            typer.echo(f"Error reading file: {e}", err=True)
            raise typer.Exit(code=1) from None

    if text_arg is not None and text_arg.strip():
        return text_arg

    # Try reading from stdin (piped input)
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            return stdin_text

    typer.echo(
        "Error: provide text as an argument, use ``--file``, or pipe input via stdin.",
        err=True,
    )
    raise typer.Exit(code=1) from None


def _show_header(text: str, title: str = "Claim Workflow") -> None:
    """Show a formatted header with text preview and word count."""
    if not console:
        return
    words = len(text.split())
    chars = len(text)
    preview = text[:200].replace("\n", " ")
    if len(text) > 200:
        preview += "..."
    console.print()
    console.print(
        Panel(
            f"[bold]Text:[/] {preview}\n[dim]{words} words, {chars} characters[/]",
            title=title,
        )
    )
    console.print()


# ------------------------------------------------------------------ #
# verify — run full pipeline
# ------------------------------------------------------------------ #


@claim_app.command()
def verify(
    text: str = typer.Argument(
        None,
        help="Sentence or paragraph to analyze (omit to use --file or stdin)",
    ),
    file: Path = typer.Option(
        None,
        "--file",
        "-F",
        exists=False,
        help="Read input text from a file",
        dir_okay=False,
    ),
    auto_accept: bool = typer.Option(
        False,
        "--auto-accept",
        "-a",
        help="Auto-accept all claims without user interaction",
    ),
    llm_enabled: bool = typer.Option(
        True,
        "--llm/--no-llm",
        help="Enable LLM-dependent features",
    ),
    bib_format: str = typer.Option(
        "bibtex",
        "--bib-format",
        "-f",
        help="Bibliography output format (bibtex, ris, json)",
    ),
    parallel_workers: int = typer.Option(
        0,
        "--parallel",
        "-p",
        help="Number of parallel verification workers (0 = sequential)",
    ),
    max_retries: int = typer.Option(
        2,
        "--max-retries",
        "-r",
        help="Maximum sub-agent retries before failure",
    ),
    output: str = typer.Option(
        "text",
        "--output",
        "-o",
        help="Output format: text, json, or quiet",
    ),
):
    """
    Run the full multi-agent claim verification pipeline.

    Extracts claims, verifies them against Europe PMC literature,
    reviews evidence quality, makes decisions, and writes an improved
    text with citations and bibliography.

    The input text can be provided as a positional argument, via ``--file``,
    or piped through stdin.
    """
    _require_langgraph()

    resolved = _read_text(text, file)
    if not resolved.strip():
        typer.echo("Error: text cannot be empty", err=True)
        raise typer.Exit(code=1) from None

    if output != "quiet":
        _show_header(resolved)

    if llm_enabled:
        typer.echo("  LLM: enabled")

    # --- Run pipeline with progress spinner ---
    show_progress = output != "json" and output != "quiet" and console

    try:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("[cyan]Running claim verification pipeline...", total=100)

                def _progress_callback(pct: float) -> None:
                    progress.update(task, completed=int(pct * 100))

                result = run_supervisor_graph(
                    source_text=resolved,
                    llm_enabled=llm_enabled,
                    auto_accept=auto_accept,
                    bibliography_format=bib_format,
                    use_checkpointer=False,
                    parallel_workers=parallel_workers,
                    max_retries=max_retries,
                    progress_callback=_progress_callback,
                )
                progress.update(task, completed=100)
        else:
            result = run_supervisor_graph(
                source_text=resolved,
                llm_enabled=llm_enabled,
                auto_accept=auto_accept,
                bibliography_format=bib_format,
                use_checkpointer=False,
                parallel_workers=parallel_workers,
                max_retries=max_retries,
            )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    # --- Output ---
    if output == "json":
        _print_json(result)
        return

    if output == "quiet":
        return

    _print_verify_results(result)


def _print_verify_results(result: dict) -> None:
    """Pretty-print verification results using Rich."""
    if not console:
        print(result)
        return

    has_errors = result.get("errors", [])
    if has_errors:
        console.print(f"\n[red]Errors:[/] {'; '.join(has_errors)}")

    # --- Summary table ---
    table = Table(title="Claim Verification Results")
    table.add_column("Attribute", style="cyan")
    table.add_column("Value", style="green")

    n_claims = len(result.get("claims_raw", []))
    n_verified = len(result.get("verified_claims", []))
    n_decisions = len(result.get("user_decisions", {}))
    n_bib = len(result.get("bibliography", []))

    table.add_row("Claims Extracted", str(n_claims))
    table.add_row("Claims Verified", str(n_verified))
    summary = result.get("verification_summary", {})
    table.add_row("Verification Summary", json.dumps(summary))
    table.add_row("Decisions Made", str(n_decisions))
    table.add_row("Bibliography Entries", str(n_bib))

    review = result.get("review", {})
    table.add_row("Review Quality", review.get("overall_quality", "N/A"))
    table.add_row("Workflow Progress", f"{result.get('workflow_progress', 0):.0%}")

    if result.get("supervisor_phase") == "failed":
        table.add_row("Status", "[red]Failed[/]")
    else:
        table.add_row("Status", "[green]Complete[/]")

    console.print("\n")
    console.print(table)

    # --- Verified claims detail ---
    verified = result.get("verified_claims", [])
    if verified:
        console.print(Rule("[bold]Verified Claims[/]"))
        for i, vc in enumerate(verified):
            _print_claim_detail(i + 1, vc)

    # --- Improved text ---
    improved = result.get("improved_text", "")
    if improved:
        console.print(Rule("[bold]Improved Text (with citations)[/]"))
        console.print(Panel(improved, title="Improved Text"))

    # --- Decisions ---
    decisions = result.get("user_decisions", {})
    if decisions:
        console.print(Rule("[bold]Claim Decisions[/]"))
        for cid, accepted in decisions.items():
            icon = "[green]✓[/]" if accepted else "[red]✗[/]"
            console.print(f"  {icon} {cid}: {'Accepted' if accepted else 'Rejected'}")


def _print_claim_detail(idx: int, claim: dict) -> None:
    """Print a single verified claim with evidence."""
    claim_text = claim.get("text", "") or claim.get("original_text", "")
    claim_type = claim.get("claim_type", claim.get("type", "unknown"))
    verdict = claim.get("verdict", "unknown")
    confidence = claim.get("confidence", "N/A")
    reasoning = claim.get("verification_reasoning", "") or ""
    evidence = claim.get("evidence", [])

    verdict_color = {
        "supported": "green",
        "refuted": "red",
        "insufficient_evidence": "yellow",
        "partially_supported": "yellow",
    }.get(verdict, "white")

    console.print(
        f"\n[bold]Claim {idx}:[/] {claim_text[:200]}{'...' if len(str(claim_text)) > 200 else ''}"
    )
    console.print(
        f"  Type: [cyan]{claim_type}[/]  "
        f"Verdict: [{verdict_color}]{verdict}[/]  "
        f"Confidence: {confidence}"
    )

    if evidence:
        for j, ev in enumerate(evidence[:3]):
            console.print(
                f"  [dim]Evidence {j + 1}:[/] {ev.get('paper_title', '?')}  "
                f"(relevance: {ev.get('relevance_score', 'N/A'):.2f})"
            )
            snippet = str(ev.get("text", ""))[:120]
            if snippet:
                console.print(f"          {snippet}...")
        if len(evidence) > 3:
            console.print(f"          [dim]... and {len(evidence) - 3} more[/]")
    else:
        console.print("  [dim]No evidence found[/]")

    if reasoning:
        console.print(f"  [dim]Reasoning:[/] {reasoning[:200]}")


# ------------------------------------------------------------------ #
# stream — node-by-node streaming
# ------------------------------------------------------------------ #


@claim_app.command()
def stream(
    text: str = typer.Argument(
        None,
        help="Sentence or paragraph to analyze (omit to use --file or stdin)",
    ),
    file: Path = typer.Option(
        None,
        "--file",
        "-F",
        exists=False,
        help="Read input text from a file",
        dir_okay=False,
    ),
    auto_accept: bool = typer.Option(
        False,
        "--auto-accept",
        "-a",
        help="Auto-accept all claims without user interaction",
    ),
    llm_enabled: bool = typer.Option(
        True,
        "--llm/--no-llm",
        help="Enable LLM-dependent features",
    ),
    bib_format: str = typer.Option(
        "bibtex",
        "--bib-format",
        "-f",
        help="Bibliography output format",
    ),
    parallel_workers: int = typer.Option(
        0,
        "--parallel",
        "-p",
        help="Number of parallel verification workers",
    ),
    max_retries: int = typer.Option(
        2,
        "--max-retries",
        "-r",
        help="Maximum sub-agent retries before failure",
    ),
):
    """
    Run the claim verification pipeline in **stream mode**.

    Prints each node's output as it executes, showing the supervisor's
    phase routing and sub-agent results in real time.
    """
    _require_langgraph()

    resolved = _read_text(text, file)
    if not resolved.strip():
        typer.echo("Error: text cannot be empty", err=True)
        raise typer.Exit(code=1) from None

    if console:
        _show_header(resolved)
        console.print("[bold]Starting claim verification (stream mode)...[/]\n")
    else:
        typer.echo("Starting claim verification (stream mode)...")

    try:
        gen = stream_supervisor_graph(
            source_text=resolved,
            llm_enabled=llm_enabled,
            auto_accept=auto_accept,
            bibliography_format=bib_format,
            parallel_workers=parallel_workers,
            max_retries=max_retries,
        )

        for step in gen:
            for node_name, update in step.items():
                if isinstance(update, dict):
                    _print_stream_step(node_name, update)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None


def _print_stream_step(node_name: str, update: dict) -> None:
    """Print a single streaming step to the console."""
    if not console:
        return

    phase = update.get("supervisor_phase") or node_name
    progress_val = update.get("workflow_progress", 0)

    if node_name == "supervisor":
        if phase == "done":
            console.print("\n[green]✓ Pipeline complete (100%)[/]")
        elif phase == "failed":
            errors = update.get("errors", [])
            err_str = f": {'; '.join(errors)}" if errors else ""
            console.print(f"\n[red]✗ Pipeline failed{err_str}[/]")
        else:
            console.print(
                f"[cyan]►[/] Supervisor routing to [bold]{phase}[/] ({progress_val:.0%})"
            )
    else:
        # Sub-agent node
        errors = update.get("errors", [])
        action_msgs = [m for m in update.get("agent_messages", []) if m.get("agent") == node_name]
        action = action_msgs[-1].get("action", "complete") if action_msgs else None

        if errors:
            console.print(f"  [red]✗ {node_name}:[/] {'; '.join(errors)}")
        elif action:
            console.print(f"  [green]✓ {node_name}:[/] {action}")
        else:
            console.print(f"  [green]✓ {node_name}:[/] complete")


# ------------------------------------------------------------------ #
# serve — start the Flask web UI
# ------------------------------------------------------------------ #


@claim_app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host to bind the web server to",
    ),
    port: int = typer.Option(
        5000,
        "--port",
        "-p",
        help="Port to bind the web server to",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        "-d",
        help="Enable Flask debug mode",
    ),
):
    """
    Start the **Flask web UI** for the claim verification workflow.

    Opens a browser-based interface where you can:

    \b
    1. Input text for analysis
    2. Review claims with evidence
    3. Accept/reject each claim
    4. View improved text with citations
    5. Download bibliography

    Example::

        pyeuropepmc claim serve --port 8080
    """
    try:
        from pyeuropepmc.ui import create_app
    except ImportError:
        typer.echo(
            "Flask is required for the web UI.\nInstall with: pip install pyeuropepmc[ui]",
            err=True,
        )
        raise typer.Exit(code=1) from None

    app = create_app()
    url = f"http://{host}:{port}"

    if console:
        console.print("\n[bold green]✓[/] pyEuropePMC Claim UI starting...")
        console.print(f"   Open [link={url}]{url}[/] in your browser")
        console.print("   Press [bold]Ctrl+C[/] to stop\n")
    else:
        typer.echo(f"Starting pyEuropePMC Claim UI at {url}")

    app.run(host=host, port=port, debug=debug)


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #


def _print_json(data: dict) -> None:
    """Print a dict as formatted JSON."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


__all__ = ["claim_app"]
