"""Precision and recall per rhetorical role on the hand-labelled sentences in
``tests/fixtures/rhetoric/labeled.json``.

    python benchmarks/evaluate_rhetoric_roles.py

Compares three classifiers on the same 93 sentences from three open-access papers: the older
``RhetoricalHighlighter`` of ``pyeuropepmc.features.fulltext.rhetorical`` (rules written for
computer-science papers), the rules of the MCP tool without section information (what a paper
without headings gets), and the rules with the section each sentence is in (the normal case).
Precision is the share of the sentences given a role that really have it; recall the share of
the sentences with the role that were found. ``unknown`` counts as no answer.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

FIXTURE = Path(__file__).parents[1] / "tests" / "fixtures" / "rhetoric" / "labeled.json"
ROLES = ("background", "motivation", "method", "result", "claim", "limitation", "conclusion")


def load() -> list[dict]:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["sentences"]
    return [r for r in rows if r["label"] != "excluded"]


def old_classifier(row: dict) -> str:
    from pyeuropepmc.features.fulltext.rhetorical import RhetoricalHighlighter

    return RhetoricalHighlighter()._classify_sentence(row["text"])[0].value


def rules(row: dict, *, sections: bool) -> str:
    from pyeuropepmc.mcp import _rhetoric as rh

    kind = rh.section_kind(row["section"]) if sections else None
    return rh.classify(row["text"], kind)[0]


def table(name: str, rows: list[dict], predict) -> None:
    predicted: collections.Counter[str] = collections.Counter()
    correct: collections.Counter[str] = collections.Counter()
    gold: collections.Counter[str] = collections.Counter()
    for row in rows:
        role = predict(row)
        predicted[role] += 1
        gold[row["label"]] += 1
        correct[role] += role == row["label"]
    right = sum(correct[r] for r in ROLES)
    print(f"\n{name}: {right}/{len(rows)} sentences right, {predicted['unknown']} unknown")
    print(f"  {'role':11} {'given':>5} {'right':>5} {'precision':>9} {'gold':>5} {'recall':>7}")
    for role in ROLES:
        precision = f"{correct[role] / predicted[role]:.2f}" if predicted[role] else "-"
        recall = f"{correct[role] / gold[role]:.2f}" if gold[role] else "-"
        print(
            f"  {role:11} {predicted[role]:>5} {correct[role]:>5} {precision:>9} "
            f"{gold[role]:>5} {recall:>7}"
        )


def main() -> None:
    rows = load()
    sets = collections.Counter(r["set"] for r in rows)
    papers = len({r["paper"] for r in rows})
    print(f"{len(rows)} labelled sentences from {papers} papers: {dict(sets)}")
    table("older RhetoricalHighlighter", rows, old_classifier)
    table("tool rules, no section information", rows, lambda r: rules(r, sections=False))
    table("tool rules, with sections", rows, lambda r: rules(r, sections=True))
    for name in ("dev", "held_out", "stress"):
        subset = [r for r in rows if r["set"] == name]
        right = sum(rules(r, sections=True) == r["label"] for r in subset)
        print(f"\nwith sections, {name}: {right}/{len(subset)} right")


if __name__ == "__main__":
    main()
