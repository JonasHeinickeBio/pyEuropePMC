#!/usr/bin/env python3
"""Check that CHANGELOG.md keeps new entries under ``[Unreleased]``.

Merging main into a branch that edits the changelog can put its entries under a version that
main has already cut (git merges the lines, not their meaning). This checks the merged result:

1. ``## [Unreleased]`` exists once and is the first section.
2. No ``###`` heading repeats within a section (four merges left four "Features" headings).
3. With ``--base``: every released section the base already has is unchanged. A release that
   cuts ``[Unreleased]`` adds a new section and passes; a line added to ``[4.4.0]`` does not.

Standard library only, so the workflow needs no environment setup.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

UNRELEASED = "Unreleased"
_SECTION = re.compile(r"^## \[(?P<name>[^\]]+)\]", re.MULTILINE)
_SUBSECTION = re.compile(r"^### (?P<name>.+?)\s*$", re.MULTILINE)


def sections(text: str) -> list[tuple[str, str]]:
    """The ``## [name]`` sections of a changelog, in order, as (name, text) pairs."""
    marks = list(_SECTION.finditer(text))
    return [
        (m["name"], text[m.start() : marks[i + 1].start() if i + 1 < len(marks) else len(text)])
        for i, m in enumerate(marks)
    ]


def problems(head: str, base: str | None = None) -> list[str]:
    """What is wrong with ``head`` (and, given the base's text, against it)."""
    found: list[str] = []
    parts = sections(head)
    names = [name for name, _ in parts]

    if names.count(UNRELEASED) != 1:
        found.append(
            f"expected exactly one '## [{UNRELEASED}]' section, found {names.count(UNRELEASED)}"
        )
    elif names[0] != UNRELEASED:
        found.append(f"'## [{UNRELEASED}]' must be the first section, but '## [{names[0]}]' is")

    for name, body in parts:
        counts = Counter(m["name"] for m in _SUBSECTION.finditer(body))
        found.extend(
            f"'## [{name}]' has the heading '### {heading}' {n} times; merge them into one"
            for heading, n in counts.items()
            if n > 1
        )

    if base is not None:
        mine = dict(parts)
        for name, body in sections(base):
            if name == UNRELEASED:
                continue
            if name not in mine:
                found.append(f"released section '## [{name}]' was removed")
            elif mine[name].strip() != body.strip():
                found.append(
                    f"released section '## [{name}]' changed; entries belong under "
                    f"'## [{UNRELEASED}]' (label the PR 'changelog-edit' to correct a release)"
                )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("changelog", type=Path)
    parser.add_argument("--base", type=Path, help="the base branch's CHANGELOG.md")
    args = parser.parse_args(argv)

    base = args.base.read_text(encoding="utf-8") if args.base else None
    found = problems(args.changelog.read_text(encoding="utf-8"), base)
    for line in found:
        print(f"::error file={args.changelog}::{line}")
    if not found:
        print(f"{args.changelog}: ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
