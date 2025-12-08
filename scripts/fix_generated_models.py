#!/usr/bin/env python3
"""
Post-processing script for LinkML-generated models/generated.py to make it pre-commit conform.

This script performs the following fixes:
1. Wraps long docstrings (>99 characters) in class docstrings.
2. Adds @classmethod decorators and type annotations to @field_validator methods.
3. Runs ruff check --fix to auto-fix remaining linting issues.
4. Runs ruff format for consistent formatting.

Usage:
    python scripts/fix_generated_models.py src/pyeuropepmc/models/generated.py

After running this script, you may need to:
- Run `poetry lock` if dependencies have changed.
- Run `pre-commit run --all-files` to verify.
"""

import argparse
from pathlib import Path
import re
import subprocess
import sys


def wrap_docstring(docstring: str, max_length: int = 95) -> str:
    """Wrap a docstring to max_length characters per line."""
    if not docstring:
        return docstring

    # Remove existing quotes
    docstring = docstring.strip()
    if docstring.startswith('"""') and docstring.endswith('"""'):
        docstring = docstring.removeprefix('"""').removesuffix('"""')
    elif docstring.startswith("'''") and docstring.endswith("'''"):
        docstring = docstring.removeprefix("'''").removesuffix("'''")

    lines = docstring.split("\n")

    wrapped_lines = []
    for line in lines:
        if len(line) <= max_length:
            wrapped_lines.append(line)
        else:
            # Simple wrapping at word boundaries
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= max_length:
                    current_line += (" " + word) if current_line else word
                else:
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = word
            if current_line:
                wrapped_lines.append(current_line)

    return "\n".join(f"    {line}" for line in wrapped_lines)


def fix_class_docstrings(content: str) -> str:
    """Fix class docstrings by wrapping long lines."""

    def wrap_class_docstring(match: re.Match[str]) -> str:
        class_name = match.group(1)
        docstring = match.group(2)
        wrapped = wrap_docstring(docstring)
        return f'{class_name}\n    """\n{wrapped}\n    """'

    # Pattern for class docstrings
    class_pattern = r'(class \w+[^:]*:)\n    """\n(.*?)\n    """'
    return re.sub(class_pattern, wrap_class_docstring, content, flags=re.DOTALL)


def fix_field_validators(content: str) -> str:
    """Add @classmethod decorators and type annotations to @field_validator methods."""
    # First, ensure all @field_validator have @classmethod
    content = re.sub(
        r"(@field_validator\([^)]+\))\n(    )def ", r"\1\n\2@classmethod\n\2def ", content
    )

    # Add type annotations to field_validator methods
    content = re.sub(r"def (pattern_\w+)\(cls, v\):", r"def \1(cls, v: Any) -> Any:", content)

    return content


def run_ruff_fix(file_path: Path) -> None:
    """Run ruff check --fix to auto-fix linting issues."""
    subprocess.run(["poetry", "run", "ruff", "check", "--fix", str(file_path)], check=False)


def run_ruff_format(file_path: Path) -> None:
    """Run ruff format for consistent formatting."""
    subprocess.run(["poetry", "run", "ruff", "format", str(file_path)], check=True)


def fix_generated_models(file_path: str, dry_run: bool = False) -> None:
    """Fix the generated models file for pre-commit compliance."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File {file_path} does not exist.")
        sys.exit(1)

    content = path.read_text()

    # Apply fixes
    content = fix_class_docstrings(content)
    content = fix_field_validators(content)

    if dry_run:
        print("Dry run: changes would be applied to", file_path)
        # Could print diff here, but for simplicity, just indicate
        return

    # Write back
    path.write_text(content)

    # Run ruff fixes
    run_ruff_fix(path)
    run_ruff_format(path)

    print(f"Fixed {file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fix LinkML-generated models for pre-commit compliance."
    )
    parser.add_argument("file_path", help="Path to the generated models file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying the file",
    )

    args = parser.parse_args()

    fix_generated_models(args.file_path, args.dry_run)
