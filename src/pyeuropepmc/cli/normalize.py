"""CLI commands for JATS XML normalization."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table
import typer

from pyeuropepmc.processing.jats_normalizer import JATSNormalizer

normalize_app = typer.Typer(
    help="Normalize JATS XML for text mining pipelines",
    no_args_is_help=True,
)
console = Console()


@normalize_app.command("text")
def normalize_text(
    input_path: Path = typer.Argument(
        ..., help="Path to a JATS XML file or directory of XML files"
    ),
    output_path: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (stdout if omitted)"
    ),
    no_entities: bool = typer.Option(False, "--no-entities", help="Skip entity normalization"),
    no_markup: bool = typer.Option(False, "--no-markup", help="Skip display markup stripping"),
    no_sections: bool = typer.Option(
        False, "--no-sections", help="Skip section type canonicalization"
    ),
    no_ids: bool = typer.Option(False, "--no-ids", help="Skip identifier normalization"),
    remove_structural: bool = typer.Option(
        False, help="Remove fig/table-wrap/supplementary-material from body"
    ),
) -> None:
    """Normalize a JATS XML file to clean plain text."""
    normalizer = JATSNormalizer(
        normalize_entities=not no_entities,
        strip_display_markup=not no_markup,
        section_types=not no_sections,
        normalize_identifiers=not no_ids,
        remove_structural=remove_structural,
    )
    xml_content = _read_xml(input_path)
    result = normalizer.normalize_xml(xml_content)
    text: str = result["body_text"]

    if output_path:
        output_path.write_text(text, encoding="utf-8")
        console.print(f"[green]Written to {output_path}[/green]")
    else:
        console.print(text)


@normalize_app.command("sections")
def normalize_sections_cmd(
    input_path: Path = typer.Argument(
        ..., help="Path to a JATS XML file or directory of XML files"
    ),
    output_path: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (stdout if omitted)"
    ),
    no_entities: bool = typer.Option(False, "--no-entities", help="Skip entity normalization"),
    no_markup: bool = typer.Option(False, "--no-markup", help="Skip display markup stripping"),
    no_sections: bool = typer.Option(
        False, "--no-sections", help="Skip section type canonicalization"
    ),
) -> None:
    """Extract normalized sections from a JATS XML file."""
    normalizer = JATSNormalizer(
        normalize_entities=not no_entities,
        strip_display_markup=not no_markup,
        section_types=not no_sections,
    )
    xml_content = _read_xml(input_path)
    result = normalizer.normalize_xml(xml_content)
    sections = result["sections"]

    table = Table(title=f"Sections ({len(sections)} found)")
    table.add_column("Type", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Depth", style="dim")
    table.add_column("Words", style="dim")

    for sec in sections:
        title_text = sec.get("title", "")
        content_text = sec.get("text", "")
        word_count = len(content_text.split()) if content_text else 0
        table.add_row(
            sec.get("type", "other"),
            title_text[:60] + ("..." if len(title_text) > 60 else ""),
            str(sec.get("level", 0)),
            str(word_count),
        )

    console.print(table)

    if output_path:
        import json

        output_path.write_text(
            json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        console.print(f"[green]Written to {output_path}[/green]")


@normalize_app.command("bioc")
def normalize_bioc(
    input_path: Path = typer.Argument(..., help="Path to a JATS XML file"),
    output_path: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (stdout if omitted)"
    ),
) -> None:
    """Convert a JATS XML file to BioC JSON format."""
    normalizer = JATSNormalizer(bio_c_output=True)
    xml_content = _read_xml(input_path)
    result = normalizer.normalize_xml(xml_content)

    import json

    bioc_data = result.get("bio_c", result)

    if output_path:
        output_path.write_text(
            json.dumps(bioc_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        console.print(f"[green]Written to {output_path}[/green]")
    else:
        console.print(json.dumps(bioc_data, indent=2, ensure_ascii=False))


@normalize_app.command("classify")
def classify_heading(
    heading: str = typer.Argument(..., help="Section heading to classify"),
) -> None:
    """Classify a section heading into a canonical type."""
    from pyeuropepmc.processing.jats_normalizer import classify_section

    section_type = classify_section(heading)
    console.print(f"[cyan]{heading}[/cyan] -> [green]{section_type}[/green]")


@normalize_app.command("batch")
def normalize_batch(
    input_dir: Path = typer.Argument(..., help="Directory containing JATS XML files"),
    output_dir: Path = typer.Argument(..., help="Output directory for normalized files"),
    output_format: str = typer.Option("text", help="Output format: text, sections, bioc"),
    no_entities: bool = typer.Option(False, "--no-entities", help="Skip entity normalization"),
    no_markup: bool = typer.Option(False, "--no-markup", help="Skip display markup stripping"),
    no_sections: bool = typer.Option(
        False, "--no-sections", help="Skip section type canonicalization"
    ),
    recursive: bool = typer.Option(False, help="Recursively search subdirectories"),
) -> None:
    """Batch-normalize all JATS XML files in a directory."""
    import json

    normalizer = JATSNormalizer(
        normalize_entities=not no_entities,
        strip_display_markup=not no_markup,
        section_types=not no_sections,
        bio_c_output=(output_format == "bioc"),
    )

    glob_pattern = "**/*.xml" if recursive else "*.xml"
    xml_files = sorted(input_dir.glob(glob_pattern))

    if not xml_files:
        console.print(f"[red]No XML files found in {input_dir}[/red]")
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Processing {len(xml_files)} files...")

    success = 0
    failed = 0

    for xml_file in xml_files:
        try:
            xml_content = xml_file.read_text(encoding="utf-8")
            result = normalizer.normalize_xml(xml_content)

            out_file = output_dir / xml_file.with_suffix(
                f".{output_format}.json" if output_format != "text" else ".txt"
            )

            if output_format == "text":
                out_file.write_text(result["body_text"], encoding="utf-8")
            elif output_format == "sections":
                out_file.write_text(
                    json.dumps(result["sections"], indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            elif output_format == "bioc":
                out_file.write_text(
                    json.dumps(result.get("bio_c", result), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

            success += 1
            console.print(f"  [green]✓[/green] {xml_file.name}")

        except Exception as exc:
            failed += 1
            console.print(f"  [red]✗[/red] {xml_file.name}: {exc}")

    console.print(
        f"\n[bold]Done:[/bold] {success} succeeded, {failed} failed out of {len(xml_files)}"
    )


def _read_xml(path: Path) -> str:
    """Read XML content from a file."""
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(code=1)
    return path.read_text(encoding="utf-8")
