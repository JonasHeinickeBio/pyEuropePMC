"""Score the PICO decomposers on the gold questions in ``tests/fixtures/pico``.

    python benchmarks/evaluate_pico_parser.py

Compares the rule-based decomposer of the MCP tool (``pyeuropepmc.mcp._pico``) with the older
parser in ``pyeuropepmc.features.review.pico``. For every gold element it counts:

* exact: the extracted text equals the gold text (case-insensitive), or both are empty
* partial: not exact, but the two share at least half of their words
* fabricated: an extracted text that is not a piece of the question (should never happen)

A gold element that is empty and left empty counts as exact: not inventing an element is a
correct answer.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pico"
SETS = ("dev", "held_out", "harder")
OLD_KEYS = {
    "population": "population",
    "intervention": "intervention",
    "comparison": "comparison",
    "outcome": "outcome",
    "study_design": "study_design",
    "time_frame": "time_frame",
}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[\w-]+", text.lower()))


def classify(got: str, gold: str) -> str:
    if got.strip().lower() == gold.strip().lower():
        return "exact"
    if got and gold:
        a, b = _words(got), _words(gold)
        if a and b and len(a & b) / len(a | b) >= 0.5:
            return "partial"
    return "wrong"


def new_parser(question: str, framework: str) -> dict[str, str]:
    from pyeuropepmc.mcp import _pico

    return {k: v.text for k, v in _pico.decompose(question, framework).elements.items()}


def old_parser(question: str, framework: str) -> dict[str, str]:
    from pyeuropepmc.features.review.pico import pico_decompose

    if framework == "SPIDER":
        return {}  # the old parser has no SPIDER support
    elements = pico_decompose(question).to_dict()
    return {k: elements[v] for k, v in OLD_KEYS.items() if elements.get(v)}


def score(parser, questions: list[dict]) -> dict[str, int]:
    counts = {
        "exact": 0,
        "partial": 0,
        "wrong": 0,
        "fabricated": 0,
        "elements": 0,
        "stated": 0,  # gold elements the question really states
        "stated_exact": 0,  # ... that were extracted exactly
        "stated_partial": 0,  # ... that were extracted in part
        "invented": 0,  # elements extracted where the question states none
    }
    for item in questions:
        got = parser(item["question"], item["framework"])
        for key, gold in item["gold"].items():
            verdict = classify(got.get(key, ""), gold)
            counts[verdict] += 1
            counts["elements"] += 1
            if gold:
                counts["stated"] += 1
                counts["stated_exact"] += verdict == "exact"
                counts["stated_partial"] += verdict == "partial"
            elif got.get(key):
                counts["invented"] += 1
        counts["fabricated"] += sum(
            1 for text in got.values() if text and text.lower() not in item["question"].lower()
        )
    return counts


def main() -> None:
    print(
        f"{'set':9} {'parser':6} {'Q':>2} | {'stated':>6} {'exact':>6} {'part.':>5} {'found':>6} "
        f"| {'unstated':>8} {'invented':>8} | {'fabricated':>10}"
    )
    for name in SETS:
        questions = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))[
            "questions"
        ]
        for label, parser in (("rules", new_parser), ("old", old_parser)):
            c = score(parser, questions)
            stated, unstated = c["stated"], c["elements"] - c["stated"]
            found = c["stated_exact"] + c["stated_partial"]
            print(
                f"{name:9} {label:6} {len(questions):>2} | {stated:>6} {c['stated_exact']:>3} "
                f"{100 * c['stated_exact'] / stated:>2.0f}% {c['stated_partial']:>5} "
                f"{100 * found / stated:>5.0f}% | {unstated:>8} {c['invented']:>8} | "
                f"{c['fabricated']:>10}"
            )
    print(
        "\nstated: elements the question states; exact/part./found: extracted exactly, in part, "
        "either way (share of stated);\nunstated: elements the question does not state; "
        "invented: extracted anyway; fabricated: extracted text that is not in the question."
    )


if __name__ == "__main__":
    main()
