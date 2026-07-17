"""
Interactive CLI for the claim workflow with user confirmation UI.

Uses Rich for a user-friendly terminal interface where users can:
1. Review extracted claims with evidence
2. Accept/reject each claim-evidence pair
3. Trigger text improvement with accepted citations
4. Export bibliography

This implements the "user confirmation UI" step in the workflow.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import sys
from typing import Any

from pyeuropepmc.claims.extractor import ClaimExtractor
from pyeuropepmc.claims.models import ClaimSet, Verdict
from pyeuropepmc.claims.reviewer import ClaimReviewer
from pyeuropepmc.claims.verifier import ClaimVerifier
from pyeuropepmc.claims.writer import ClaimWriter

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


def run_full_workflow(
    text: str,
    output_dir: str | Path | None = None,
    skip_llm: bool = False,
    auto_accept: bool = False,
    bibliography_format: str = "bibtex",
) -> dict[str, Any]:
    """
    Run the full claim workflow: extract → verify → review → confirm → write.

    Parameters
    ----------
    text : str
        The source text to analyze
    output_dir : str or Path, optional
        Directory for output files
    skip_llm : bool, optional
        Skip LLM-dependent steps (default: False)
    auto_accept : bool, optional
        Auto-accept all claims without user interaction (default: False)
    bibliography_format : str, optional
        Output format: "bibtex", "ris", or "csl" (default: "bibtex")

    Returns
    -------
    dict
        Full workflow results with improved text and bibliography
    """
    if RICH_AVAILABLE:
        console = Console()
        console.print(
            Panel.fit(
                "[bold blue]Scientific Claim Verification Workflow[/bold blue]\n"
                "Extract → Verify → Review → Confirm → Write",
                border_style="blue",
            )
        )
        console.print(f"\n[bold]Input text:[/bold] {text[:100]}...")

    # Step 1: Extract claims
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Step 1/5:[/bold cyan] Extracting claims...")

    extractor = ClaimExtractor(llm_enabled=not skip_llm)
    claim_set = extractor.extract(text)

    if RICH_AVAILABLE:
        console.print(f"  → Extracted [bold]{len(claim_set.claims)}[/bold] atomic claims")

    # Step 2: Verify claims
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Step 2/5:[/bold cyan] Verifying claims against literature...")

    verifier = ClaimVerifier(llm_enabled=not skip_llm)
    claim_set = verifier.verify_claim_set(claim_set)

    if RICH_AVAILABLE:
        summary = claim_set.verification_summary
        console.print(
            f"  → [green]{summary['supported']} supported[/green], "
            f"[red]{summary['refuted']} refuted[/red], "
            f"{summary['insufficient_evidence']} insufficient, "
            f"{summary['not_checked']} unchecked"
        )

    # Step 3: Review
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Step 3/5:[/bold cyan] Reviewing evidence quality...")

    reviewer = ClaimReviewer(llm_enabled=not skip_llm)
    review = reviewer.review_claim_set(claim_set)

    if RICH_AVAILABLE:
        console.print(f"  → Quality: [bold]{review.get('overall_quality', 'unknown')}[/bold]")

    # Step 4: User confirmation
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Step 4/5:[/bold cyan] User confirmation...")
    else:
        logger.info("Step 4/5: User confirmation (auto-accept mode)")

    user_decisions = _get_user_decisions(
        claim_set,
        auto_accept=auto_accept,
        review=review,
    )

    if RICH_AVAILABLE:
        accepted = sum(1 for v in user_decisions.values() if v)
        console.print(f"  → Accepted [bold]{accepted}[/bold] / {len(user_decisions)} claims")

    # Step 5: Write improved text
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]Step 5/5:[/bold cyan] Generating improved text...")

    writer = ClaimWriter(llm_enabled=not skip_llm)
    report = writer.write_report(
        original_text=text,
        claim_set=claim_set,
        user_decisions=user_decisions,
        bibliography_format=bibliography_format,
    )

    # Add review notes
    report.review_notes = review.get("llm_review")

    if RICH_AVAILABLE:
        console.print(f"  → Text improved with [bold]{len(report.bibliography)}[/bold] references")
        console.print("\n[bold green]Workflow complete![/bold green]")

    # Output
    result = report.to_dict()
    result["review"] = review

    if output_dir:
        _save_outputs(result, output_dir, text)

    return result


def _get_user_decisions(
    claim_set: ClaimSet,
    auto_accept: bool = False,
    review: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """Get user confirmation for each claim."""
    decisions: dict[str, bool] = {}

    if auto_accept or not RICH_AVAILABLE:
        for claim in claim_set.claims:
            if claim.verdict == Verdict.REFUTED:
                decisions[claim.id] = False
            else:
                decisions[claim.id] = True
        return decisions

    console = Console()

    # Show summary first
    summary = claim_set.verification_summary
    summary_table = Table(title="Verification Summary", show_header=True)
    summary_table.add_column("Status", style="bold")
    summary_table.add_column("Count")

    verdict_styles = {
        "supported": "green",
        "refuted": "red",
        "insufficient_evidence": "yellow",
        "partially_supported": "cyan",
        "unverifiable": "dim",
        "not_checked": "dim",
    }

    for verdict, count in summary.items():
        style = verdict_styles.get(verdict, "")
        summary_table.add_row(
            f"[{style}]{verdict.replace('_', ' ').title()}[/{style}]", str(count)
        )

    console.print(summary_table)

    if summary.get("refuted", 0) > 0:
        console.print("\n[bold red]⚠ WARNING:[/bold red] Some claims were refuted by evidence.")
    if summary.get("insufficient_evidence", 0) > 0:
        console.print("[bold yellow]⚠ NOTE:[/bold yellow] Some claims have insufficient evidence.")

    # Review each claim
    for i, claim in enumerate(claim_set.claims):
        console.print(f"\n[bold]Claim {i + 1}/{len(claim_set.claims)}:[/bold]")

        # Verdict with style
        verdict_styles_map = {
            Verdict.SUPPORTED: "green",
            Verdict.REFUTED: "red",
            Verdict.INSUFFICIENT_EVIDENCE: "yellow",
            Verdict.PARTIALLY_SUPPORTED: "cyan",
            Verdict.UNVERIFIABLE: "dim",
            Verdict.NOT_CHECKED: "dim",
        }
        v_style = verdict_styles_map.get(claim.verdict, "")
        verdict_text = Text(f"[{v_style}]{claim.verdict.value}[/{v_style}]")

        console.print(
            Panel(
                f"[bold]Text:[/bold] {claim.text}\n"
                f"[bold]Type:[/bold] {claim.claim_type.value}  "
                f"[bold]Confidence:[/bold] {claim.confidence:.2f}  "
                f"[bold]Verdict:[/bold] {verdict_text}",
                border_style="cyan" if claim.verdict == Verdict.SUPPORTED else "yellow",
                padding=(1, 2),
            )
        )

        # Evidence
        if claim.evidence:
            ev_table = Table(title="Evidence", show_header=True)
            ev_table.add_column("#", style="dim")
            ev_table.add_column("Paper", style="bold", max_width=40)
            ev_table.add_column("Relevance", style="blue")
            ev_table.add_column("Quality")

            for j, ev in enumerate(claim.evidence[:3]):
                quality_colors = {
                    "high": "green",
                    "medium": "yellow",
                    "low": "red",
                    "uncertain": "dim",
                }
                q_color = quality_colors.get(ev.quality.value, "")
                ev_table.add_row(
                    str(j + 1),
                    ev.paper_title[:50],
                    f"{ev.relevance_score:.2f}",
                    f"[{q_color}]{ev.quality.value}[/{q_color}]",
                )
            console.print(ev_table)

        if claim.verification_reasoning:
            console.print(f"[dim]Reasoning: {claim.verification_reasoning[:200]}[/dim]")

        # Get user decision
        if claim.verdict == Verdict.REFUTED:
            default = False
        elif claim.verdict == Verdict.SUPPORTED:
            default = True
        else:
            default = None  # ask

        if default is not None:
            accept = Confirm.ask(
                "  Include this claim?",
                default=default,
            )
        else:
            accept = Confirm.ask(
                "  Include this claim? (insufficient evidence)",
                default=False,
            )

        decisions[claim.id] = accept

    return decisions


def _save_outputs(
    result: dict[str, Any],
    output_dir: str | Path,
    original_text: str,
) -> None:
    """Save workflow outputs to files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save improved text
    improved_path = output_dir / "improved_text.md"
    improved_path.write_text(
        f"# Improved Text with Citations\n\n"
        f"{result.get('improved_text', original_text)}\n\n"
        f"---\n\n"
        f"## Bibliography\n\n"
    )
    # Append bibliography
    for entry in result.get("bibliography", []):
        improved_path.write_text(
            improved_path.read_text() + f"- {entry.get('author', '')} ({entry.get('year', '')}). "
            f"{entry.get('title', '')}. {entry.get('journal', '')}. "
            f"[{entry.get('source', '')}]\n"
        )

    # Save full report as JSON
    report_path = output_dir / "claim_report.json"
    report_path.write_text(json.dumps(result, indent=2, default=str))

    logger.info(f"Outputs saved to {output_dir}")


def cli_main():
    """CLI entry point for the claim workflow."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scientific Claim Verification Workflow",
    )
    parser.add_argument("text", nargs="?", help="Text to analyze")
    parser.add_argument("--file", "-f", help="Read text from file")
    parser.add_argument("--output", "-o", default="./claim_output", help="Output directory")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM steps")
    parser.add_argument("--auto-accept", action="store_true", help="Auto-accept all claims")
    parser.add_argument("--bib-format", choices=["bibtex", "ris", "csl"], default="bibtex")

    args = parser.parse_args()

    # Get text
    text = args.text
    if args.file:
        text = Path(args.file).read_text()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        parser.print_help()
        sys.exit(1)

    # Run workflow
    result = run_full_workflow(
        text=text,
        output_dir=args.output,
        skip_llm=args.skip_llm,
        auto_accept=args.auto_accept,
        bibliography_format=args.bib_format,
    )

    # Print improved text
    if result.get("improved_text"):
        print("\n" + "=" * 60)
        print("IMPROVED TEXT:")
        print("=" * 60)
        print(result["improved_text"])


if __name__ == "__main__":
    cli_main()


__all__ = ["run_full_workflow", "cli_main"]
