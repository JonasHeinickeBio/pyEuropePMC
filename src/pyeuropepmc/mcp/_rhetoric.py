"""Sentences of a paper's body text, with the section each one comes from.

Pure functions, no I/O. The structured full text (``FullTextXMLParser``) gives sections with
blocks; this module turns the running text of those blocks into sentences, leaving out what is
not argument: the front matter, the reference list and administrative sections such as
acknowledgments, funding and conflicts of interest.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

#: Sections that carry no argument. Matched against every part of a section's path.
_ADMINISTRATIVE = re.compile(
    r"^(?:acknowledg\w*|funding|financial support|conflicts? of interest|competing interests?|"
    r"declaration of interests?|disclosures?|author contributions?|authors?['’] contributions?|"
    r"supplementary\b.*|supporting information|footnotes?|references?|bibliography|"
    r"associated data|data availability.*|availability of data.*|abbreviations?|notes?|"
    r"orcid.*|consent for publication|article title|abstract|"
    r"(?!significance|impact|key points).*\bstatements?)$",
    re.IGNORECASE,
)
#: Block types whose text is running prose.
_PROSE_BLOCKS = {"paragraph", "list", "text"}

#: Words after which a full stop does not end a sentence.
_ABBREVIATIONS = frozenset(
    {
        "al", "fig", "figs", "eg", "ie", "vs", "approx", "ca", "cf", "no", "nos", "eq", "eqs",
        "ref", "refs", "tab", "dr", "mr", "mrs", "ms", "prof", "st", "inc", "ltd", "co", "vol",
        "pp", "p", "resp", "viz", "sp", "spp", "subsp", "var", "min", "max", "avg", "mol", "wt",
        "etc", "ed", "eds", "sec", "supp", "suppl", "mt", "jr", "sr", "dept", "univ", "ph",
    }
)  # fmt: skip
_CANDIDATE = re.compile(r"[.!?][\"')\]]*\s+")
_START = re.compile(r"[\"'(\[]*[A-ZÀ-ÞΑ-Ω]")
_WORD_BEFORE = re.compile(r"([A-Za-z][A-Za-z.]*)$")


@dataclass(frozen=True)
class Sentence:
    text: str
    start: int  # offset in the text it was split from
    end: int


def _is_boundary(text: str, stop_end: int, next_start: int) -> bool:
    """Whether the sentence-final mark that ends at ``stop_end`` really ends a sentence."""
    if not _START.match(text, next_start):
        return False  # "e.g. the", "vs. placebo", "5.2 mg", "p53 was": no capital follows
    if text[stop_end - 1] != ".":
        return True  # "?" and "!"
    found = _WORD_BEFORE.search(text[: stop_end - 1])
    if found is None:
        return True  # "3).", "5." : a number or a closing bracket before the stop
    token = found.group(1)
    if "." in token:
        return False  # "e.g.", "i.e.", "U.S."
    key = token.lower()
    if key in _ABBREVIATIONS:
        return _after_et_al(text, next_start) if key == "al" else False
    return not (
        len(token) == 1 and token.isupper()
    )  # an initial or a genus: "J. Smith", "E. coli"


def _after_et_al(text: str, next_start: int) -> bool:
    """``et al.`` ends a sentence only when an ordinary sentence follows."""
    return re.match(r"[A-Z][a-z]+\s+[a-z]", text[next_start:]) is not None


def split_sentences(text: str) -> list[Sentence]:
    """Sentences of running scientific prose, with their offsets in ``text``.

    A full stop followed by a capital letter ends a sentence unless it belongs to an abbreviation
    (``Fig.``, ``vs.``, ``e.g.``, ``et al.``), an initial or a genus (``J. Smith``,
    ``C. albicans``) or a number. Text after a full stop that starts in lower case or with a digit
    stays in the same sentence: splitting too little is the safer error here.
    """
    sentences: list[Sentence] = []
    start = 0
    for match in _CANDIDATE.finditer(text):
        if not _is_boundary(text, match.start() + 1, match.end()):
            continue
        end = match.start() + 1 + len(match.group()[1:].rstrip())
        _append(sentences, text, start, end)
        start = match.end()
    _append(sentences, text, start, len(text))
    return sentences


def _append(out: list[Sentence], text: str, start: int, end: int) -> None:
    piece = text[start:end]
    lead = len(piece) - len(piece.lstrip())
    stripped = piece.strip()
    if stripped:
        out.append(Sentence(stripped, start + lead, start + lead + len(stripped)))


@dataclass(frozen=True)
class BodySentence:
    text: str
    section: str  # the section path, "Results/Patients"
    top: str  # its first part, "Results"
    index: int  # position among the body sentences, in reading order


def is_administrative(title: str) -> bool:
    return bool(_ADMINISTRATIVE.match(" ".join(title.split())))


def body_sentences(sections: list[dict[str, Any]]) -> list[BodySentence]:
    """Sentences of the argument in reading order: body sections only, prose blocks only, no
    front matter, references or administrative sections."""
    out: list[BodySentence] = []
    for section in sections:
        if section.get("section_type") != "body":
            continue
        path = str(section.get("section_path") or section.get("title") or "")
        parts = [p.strip() for p in path.split("/") if p.strip()]
        if not parts or any(is_administrative(p) for p in parts):
            continue
        for block in section.get("content") or []:
            if not isinstance(block, dict) or block.get("type") not in _PROSE_BLOCKS:
                continue
            for sentence in split_sentences(str(block.get("text") or "")):
                text = " ".join(sentence.text.split())  # the XML keeps its line breaks
                out.append(BodySentence(text, "/".join(parts), parts[0], len(out)))
    return out


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

#: The roles the tool can return. The library's ``RhetoricalRole`` has more (supporting and
#: contradicting citation, supplementary); a keyword rule cannot tell those apart in biomedical
#: prose, so they are never returned.
ROLES = (
    "background",
    "motivation",
    "method",
    "result",
    "claim",
    "limitation",
    "conclusion",
)
UNKNOWN = "unknown"

_NUMBERING = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[ivxlc]+\.|[a-z]\.)\s+", re.IGNORECASE)
_KINDS: list[tuple[str, re.Pattern[str]]] = [
    ("limitation", re.compile(r"\blimitations?\b", re.IGNORECASE)),
    ("results_discussion", re.compile(r"\bresults?\b.*\bdiscussion\b", re.IGNORECASE)),
    ("conclusion", re.compile(r"\b(?:conclusions?|concluding|summary)\b", re.IGNORECASE)),
    ("discussion", re.compile(r"\b(?:discussion|comment|interpretation)\b", re.IGNORECASE)),
    (
        "methods",
        re.compile(
            r"\b(?:methods?|materials|methodology|study design|subjects|participants|patients and|"
            r"experimental (?:procedures?|design|section)|procedures?|statistical analys[ie]s)\b",
            re.IGNORECASE,
        ),
    ),
    ("results", re.compile(r"\b(?:results?|findings|outcomes?)\b", re.IGNORECASE)),
    (
        "introduction",
        re.compile(
            r"\b(?:introduction|background|overview|rationale|objectives?)\b", re.IGNORECASE
        ),
    ),
]


#: The section kinds ``classify`` knows (and ``None`` for "unknown").
_KINDS_NAMES = (
    "introduction",
    "methods",
    "results",
    "results_discussion",
    "discussion",
    "conclusion",
    "limitation",
)


def section_kind(path: str) -> str | None:
    """What a section is for, from its path: ``introduction``, ``methods``, ``results``,
    ``results_discussion``, ``discussion``, ``conclusion``, ``limitation`` or ``None``.

    The innermost part that says something wins for limitations; otherwise the top-level part
    decides, because subsection titles ("Radiotherapy", "Strains") say nothing about the role.
    """
    parts = [_NUMBERING.sub("", p.strip()) for p in path.split("/") if p.strip()]
    for part in reversed(parts):
        if _KINDS[0][1].search(part):
            return "limitation"
    for part in parts:
        for kind, pattern in _KINDS[1:]:
            if pattern.search(part):
                return kind
    return None


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_CONCLUDING = _rx(r"\b(?:in conclusion|in summary|to conclude|to summari[sz]e|taken together)\b")
_LIMITATION = _rx(
    r"\b(?:limitations?|limited by|may limit|might limit|small (?:sample|number)|"
    r"future (?:research|studies|work)|remains? (?:to be|unclear|unknown|undefined)|"
    r"should be interpreted|not related to the purpose|"
    r"it is important to (?:also )?consider the possibility)\b"
)
_AIM = _rx(
    r"\b(?:we aim|aimed|aims? (?:of|to)|the (?:purpose|objective|goal)|"
    r"we (?:hypothesi[sz]ed?|sought|"
    r"set out)|to (?:investigate|determine|assess|evaluate|examine|test|compare)\b.*\bwe\b|"
    r"remains? (?:unclear|unknown)|(?:are|is|has|have) (?:not|yet to be|never) "
    r"(?:yet |well |been |fully )*(?:understood|established|recogni[sz]ed|determined|"
    r"investigated|studied|clear)|justified)\b"
)
_OWN_RESULT = _rx(
    r"\b(?:we (?:found|observed|showed|obtained|detected|noted|saw|demonstrated)|our (?:results|"
    r"data|findings|study|analysis)|(?:in|of) (?:the|this) (?:present|current) study|this study "
    r"(?:showed|found|demonstrated)|all groups|were (?:significantly|similar)|"
    r"(?:the|this) effect|appeared to)\b"
)
_AGREEMENT = _rx(
    r"\b(?:in line with|consistent with|similar to|in agreement|supports?|supported|"
    r"agrees?|compared (?:with|to)|in contrast|contrary to|confirm(?:s|ed)? (?:previous|earlier)|"
    r"conserved|highlights?|importance)\b"
)
_INTERPRET = _rx(
    r"\b(?:suggest\w*|indicat\w*|impl(?:y|ies|ied)|likely|probably|may|might|could|"
    r"hypothesi[sz]e|seems?|thus|therefore|explains?|would|will (?:not )?(?:grow|thrive))\b"
)
_OTHERS = _rx(
    r"(?:\b[A-Z][a-z]+(?:-[A-Z][a-z]+)? et al\b|\bpreviously\b|\bprior\b|\brecently\b|"
    r"\b(?:has|have|had|was|were) been (?:reported|shown|described|proposed|suggested|known)\b|"
    r"\b(?:was|were) reported\b|\breported that\b|\bhas also been\b|\bstudies\b|"
    r"\bit is (?:known|well known)\b|\[\d+(?:[,–-]\s*\d+)*\])"
)
_DONE = _rx(
    r"\b(?:we (?:developed|constructed|generated|created|neutrali[sz]ed|used|performed|"
    r"employed|applied|cloned|deleted|tagged|measured|analy[sz]ed|assessed|tested|treated)|"
    r"to (?:assess|test|examine|investigate|determine|analy[sz]e|address|verify)\b.*\bwe\b|"
    r"(?:was|were) (?:generated|constructed|created|cloned|deleted|tagged|obtained from|"
    r"grown|cultured|incubated|transformed))\b"
)
_PROCEDURE = _rx(
    r"\b(?:were (?:performed|measured|assessed|analy[sz]ed|collected|recruited|included|excluded|"
    r"randomi[sz]ed|instructed|asked|used|applied|carried out|conducted|quantified|"
    r"transferred|incubated|purchased)|was (?:performed|measured|assessed|analy[sz]ed|collected|"
    r"used|applied|carried out|conducted|quantified|calculated|computed)|"
    r"(?:using|with) (?:the )?(?:software|kit|antibody|primers?|microscope)|we (?:used|performed|"
    r"collected|recruited|measured|calculated|included))\b"
)
_STATISTIC = _rx(
    r"(?:\bp\s*[<=>≤]\s*0?\.\d+|\bF\(\d|\b(?:significant(?:ly)?|increased|decreased|higher|lower|"
    r"fold|mean|median)\b|\((?:Figure|Fig\.|Table)s?\s*[S\d]|\bn\s*=\s*\d+)"
)


def _intro_role(text: str) -> tuple[str, float]:
    if _AIM.search(text):
        return "motivation", 0.8
    if re.search(r"\bwe (?:find|show|found|demonstrate|report)\b", text, re.IGNORECASE):
        return "claim", 0.6
    return "background", 0.75


def _results_role(text: str) -> tuple[str, float]:
    if _CONCLUDING.search(text):
        return "conclusion", 0.7
    if _DONE.search(text) and not _OWN_RESULT.search(text):
        return "method", 0.6
    if re.search(
        r"\b(?:these|our) (?:results?|data|findings|observations)\s+"
        r"(?:indicate|suggest|imply|show|demonstrate)",
        text,
        re.IGNORECASE,
    ):
        return "claim", 0.65
    return "result", 0.8


def _discussion_role(text: str) -> tuple[str, float]:
    if _CONCLUDING.search(text):
        return "conclusion", 0.85
    if _LIMITATION.search(text):
        return (
            ("background", 0.6)
            if _OTHERS.search(text) and not _OWN_RESULT.search(text)
            else (
                "limitation",
                0.7,
            )
        )
    if _AIM.search(text) and re.search(
        r"\b(?:our|we|this) (?:study|aim|work)", text, re.IGNORECASE
    ):
        return "motivation", 0.7
    if _OWN_RESULT.search(text):
        if _AGREEMENT.search(text) or _INTERPRET.search(text):
            return "claim", 0.65
        return "result", 0.65
    if _OTHERS.search(text) and not re.search(r"\b(?:we|our)\b", text, re.IGNORECASE):
        return "background", 0.6
    if _AGREEMENT.search(text) or _INTERPRET.search(text):
        return "claim", 0.55
    # No cue at all: a guess of "background" was right in 2 of 7 labelled cases, so say so.
    return UNKNOWN, 0.0


def _unstructured_role(text: str) -> tuple[str, float]:
    """Sentence cues alone, for text whose section says nothing.

    Only roles whose cues were right in at least 70 % of the labelled sentences are returned
    (conclusion, method, background); the cues for result, motivation and limitation were not,
    so those sentences stay ``unknown`` here.
    """
    if _CONCLUDING.search(text):
        return "conclusion", 0.6
    if _PROCEDURE.search(text):
        return "method", 0.5
    if _OTHERS.search(text) and not _OWN_RESULT.search(text):
        return "background", 0.45
    return UNKNOWN, 0.0


def classify(text: str, kind: str | None) -> tuple[str, float]:
    """``(role, confidence)`` of one sentence given what kind of section it is in.

    The section is the strongest signal in a research paper (methods describe what was done,
    results what was found), so it sets the default; cues in the sentence move it where the
    section mixes roles (a discussion restates results, cites earlier work, admits limits) and
    decide alone when the section is unknown. A sentence no rule is sure about is ``unknown``.
    """
    if kind == "limitation":
        return ("limitation", 0.8) if not _OTHERS.search(text) else ("background", 0.5)
    if kind == "methods":
        return "method", 0.9
    if kind == "introduction":
        return _intro_role(text)
    if kind == "results":
        return _results_role(text)
    if kind in ("discussion", "results_discussion"):
        return _discussion_role(text)
    if kind == "conclusion":
        return ("limitation", 0.6) if _LIMITATION.search(text) else ("conclusion", 0.85)
    return _unstructured_role(text)


# ---------------------------------------------------------------------------
# Tagging a paper
# ---------------------------------------------------------------------------


@dataclass
class Tagged:
    sentence: BodySentence
    role: str
    confidence: float
    kind: str | None
    source: str = "rules"  # "rules" | "llm"


def tag(sentences: list[BodySentence], min_confidence: float = 0.3) -> list[Tagged]:
    """Classify every sentence; one the rules are less sure about than ``min_confidence`` is
    ``unknown``."""
    out: list[Tagged] = []
    for sentence in sentences:
        kind = section_kind(sentence.section)
        role, confidence = classify(sentence.text, kind)
        if role != UNKNOWN and confidence < min_confidence:
            role, confidence = UNKNOWN, confidence
        out.append(Tagged(sentence, role, round(confidence, 2), kind))
    return out


def validate_roles(roles: list[str] | None) -> tuple[str, ...] | None:
    """The roles asked for, or ``None`` for all; an unknown name lists the valid ones."""
    if not roles:
        return None
    chosen = [r.strip().lower() for r in roles if r.strip()]
    unknown = [r for r in chosen if r not in (*ROLES, UNKNOWN)]
    if unknown:
        raise ValueError(f"unknown role(s) {unknown}; valid: {[*ROLES, UNKNOWN]}")
    return tuple(dict.fromkeys(chosen))


def fit(tagged: list[Tagged], max_chars: int) -> tuple[list[Tagged], int, bool]:
    """The sentences, in reading order, that fit ``max_chars`` of text without cutting one;
    ``(kept, characters in all of them, whether some were left out)``. At least one sentence is
    kept."""
    total = sum(len(t.sentence.text) for t in tagged)
    kept: list[Tagged] = []
    used = 0
    for item in tagged:
        size = len(item.sentence.text)
        if kept and used + size > max_chars:
            break
        kept.append(item)
        used += size
    return kept, total, len(kept) < len(tagged)


def group(kept: list[Tagged]) -> dict[str, list[dict[str, Any]]]:
    """Role -> its sentences in reading order, as the tool returns them."""
    roles: dict[str, list[dict[str, Any]]] = {}
    for item in kept:
        roles.setdefault(item.role, []).append(
            {
                "text": item.sentence.text,
                "section": item.sentence.section,
                "confidence": item.confidence,
            }
        )
    return dict(sorted(roles.items(), key=lambda kv: ((*ROLES, UNKNOWN).index(kv[0]))))


def statistics(tagged: list[Tagged]) -> dict[str, Any]:
    """Counts over every sentence of the body, not only the ones returned."""
    counts = {role: 0 for role in (*ROLES, UNKNOWN)}
    kinds: dict[str, int] = {}
    for item in tagged:
        counts[item.role] += 1
        kinds[item.kind or "none"] = kinds.get(item.kind or "none", 0) + 1
    total = len(tagged)
    return {
        "sentences": total,
        "by_role": {role: n for role, n in counts.items() if n},
        "unknown_share": round(counts[UNKNOWN] / total, 2) if total else 0.0,
        "by_section_kind": dict(sorted(kinds.items())),
    }
