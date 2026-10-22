"""The text of the server's MCP prompts: reusable literature workflows.

A prompt is a template the client offers the user, which fills in the arguments and sends the
result to the model. Each one here spells out a sequence of this server's own tools, so the
model follows the sequence instead of improvising one. Every call is written in backticks as
``tool(param=...)`` so that a test can read the tool and parameter names back out of the text
and check them against the tools the server really serves (``tool_calls``).

Pure: no request, no server import.
"""

from __future__ import annotations

import re

MAX_PAPERS = 100
DIRECTIONS = ("both", "forward", "backward")

_YEARS = re.compile(r"^\s*(\d{4})\s*(?:[-–]\s*(\d{4}))?\s*$")
_PMCID = re.compile(r"^(?:PMC)?(\d{1,10})$", re.IGNORECASE)
_CALL = re.compile(r"`([a-z][a-z0-9_]*)\(([^`]*)\)`")
_PARAM = re.compile(r"\b([a-z_][a-z0-9_]*)=")


def _phrase(text: str) -> str:
    """One line that is safe inside a double-quoted argument."""
    return " ".join(text.replace('"', "'").split())


def _years(years: str) -> tuple[str, str]:
    """``("2019", "2024")`` from ``"2019-2024"``, ``("2020", "2020")`` from ``"2020"``."""
    if not years.strip():
        return "", ""
    match = _YEARS.match(years)
    if not match:
        raise ValueError(f"years must look like 2020 or 2019-2024, got {years!r}")
    first, last = match.group(1), match.group(2) or match.group(1)
    if int(first) > int(last):
        raise ValueError(f"years run backwards: {years!r}")
    return first, last


def literature_review(topic: str, years: str = "", max_papers: int = 20) -> str:
    """Steps for a cited review of ``topic``: size, search, screen, read, write."""
    subject = _phrase(topic)
    if not subject:
        raise ValueError("topic must not be empty")
    if not 1 <= max_papers <= MAX_PAPERS:
        raise ValueError(f"max_papers must be between 1 and {MAX_PAPERS}, got {max_papers}")
    first, last = _years(years)
    window = f', date_from="{first}", date_to="{last}"' if first else ""
    scope = (
        f"published {first}" + (f" to {last}" if last != first else "") if first else "any year"
    )
    return f"""Write a cited literature review of: {subject}

Scope: papers {scope}; at most {max_papers} papers in the review. Use only the tools of this \
server, follow the steps in order, and report what each step found.

1. Size the topic. Run `count_papers(query="{subject}"{window})`. If there are more than a few \
thousand hits, narrow the query (for example `TITLE:` or `ABSTRACT:` terms, `source="MED"`, \
`open_access=true`) and count again. Check a query you wrote yourself with \
`validate_query(query="...")` first. If you want MeSH terms, `mesh_expand(terms=["..."])` \
returns them.
2. Search. Run `search_papers(query="{subject}"{window}, limit={max_papers * 3}, \
sort="cited")` with the query you settled on. This returns the most cited papers first; if the \
topic is recent, run it again with `sort="date"`.
3. Screen. From titles and abstracts alone, keep the papers that answer the topic, up to \
{max_papers}. List every paper you dropped with the reason, so the selection can be checked. \
If you need to screen against explicit criteria with an LLM, `paper_screening(query="...", \
inclusion_criteria=["..."], exclusion_criteria=["..."])` does that, but it needs an LLM provider.
4. Read. For each selected paper that has a PMCID, run \
`get_paper_fulltext(pmcid="PMC...", format="outline")` and then \
`get_paper_fulltext(pmcid="PMC...", sections=["methods", "results"])`. A paper that is not open \
access has no full text: say so, and work from its abstract only.
5. Write the review: group the findings by theme, give the design and size of each study you \
rely on, say where studies disagree, and end with limitations and gaps. Cite every claim with \
the PMID, PMCID or DOI of the paper it comes from, and do not cite a paper you did not read. \
Finish with the counts: hits found, papers screened, papers read in full text, papers cited."""


def critical_appraisal(pmcid: str) -> str:
    """Steps for a critical appraisal of one open-access paper."""
    match = _PMCID.match(pmcid.strip())
    if not match:
        raise ValueError(f"pmcid must look like PMC1234567, got {pmcid!r}")
    ident = f"PMC{match.group(1)}"
    return f"""Critically appraise the paper {ident}. Base every statement on its text and \
quote the section it comes from; if the paper does not say something, write "not reported".

1. Get the structure. Run `get_paper_fulltext(pmcid="{ident}", format="outline")`. If it fails \
because the paper is not open access, stop and say so: there is no full text to appraise.
2. Read the methods. Run `get_paper_fulltext(pmcid="{ident}", sections=["methods"])`. Note the \
study design, setting, eligibility criteria, sample size and how it was reached, interventions \
or exposures, outcomes, and the statistical methods.
3. Read the results. Run `get_paper_fulltext(pmcid="{ident}", sections=["results"])`. Note \
participant flow and losses, the main effect sizes with their confidence intervals, and \
whether the reported analyses match the methods.
4. Find what the authors concede. Run \
`tag_paper_sentences(pmcid="{ident}", roles=["limitation", "conclusion"])`, then compare the \
conclusions with the results.
5. Check the context. Run `enrich_paper(pmcid="{ident}")` for funders, citation impact and \
any retraction or correction notice.
6. Assess, in this order: study design and whether it fits the question; sample (size, \
selection, representativeness); bias (selection, performance, detection, attrition, reporting) \
and confounding; statistical analysis; limitations the authors state and those they do not; \
funding and conflicts of interest; whether the conclusions follow from the results.

Finish with a verdict in three lines: strengths, weaknesses, and how far the conclusions can \
be trusted."""


def citation_trace(pmid: str, direction: str = "both") -> str:
    """Steps for following a paper's references and citations."""
    ident = pmid.strip()
    if not ident.isdigit():
        raise ValueError(f"pmid must be digits only, got {pmid!r}")
    way = direction.strip().lower()
    if way not in DIRECTIONS:
        raise ValueError(f"direction must be one of {list(DIRECTIONS)}, got {direction!r}")
    steps = [
        f'Identify the paper. Run `get_paper_details(pmid="{ident}")` and note its title, '
        "year, journal and citation count."
    ]
    if way in ("both", "backward"):
        steps.append(
            f'Go backward. Run `get_paper_references(article_id="{ident}", source="MED", '
            "limit=100)`. These are the papers it builds on."
        )
    if way in ("both", "forward"):
        steps.append(
            f'Go forward. Run `get_paper_citations(pmid="{ident}", source="MED", limit=100)`. '
            "These are the papers that build on it."
        )
    steps.append(
        "Pick the neighbours that matter: the five most cited papers of each list (the "
        "`citedByCount` field), plus any that appear in both. For each, run "
        '`get_paper_details(pmid="...")` and read its title and abstract.'
    )
    if way == "both":
        steps.append(
            f'To go further than one step, run `citation_snowball(identifier="{ident}", '
            'strategy="both", max_papers=50, max_depth=2)`.'
        )
    steps.append(
        "Report: the foundations the paper rests on, the work that followed it, and which "
        "neighbouring papers are the most influential and why. Cite each by PMID and say "
        "whether you read its abstract or only saw it in a list."
    )
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(steps, 1))
    return (
        f"Trace the citation neighbourhood of PMID {ident} ({way}). Use only the tools of this "
        f"server and follow the steps in order.\n\n{numbered}"
    )


def tool_calls(text: str) -> list[tuple[str, list[str]]]:
    """``(tool, [parameter names])`` for every backticked ``tool(param=...)`` call in ``text``."""
    return [(tool, _PARAM.findall(args)) for tool, args in _CALL.findall(text)]
