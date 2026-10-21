"""Rule-based decomposition of a research question into PICO, PICOS, PICOT or SPIDER elements.

Pure functions, no I/O, no model. Every element is a verbatim span of the question, reported
with its position, so a caller can check it and nothing is ever invented; an element the
question does not state is reported as missing. The rules recognise the usual phrasings of a
clinical question (``In P, does I reduce O compared with C?``, ``What is the effect of I on O in
P?``, ``Is I more effective than C for O?``, ``Is I associated with O?``, ``Effectiveness of I
for O in P``, ``P treated with I``); anything else is reported as not understood rather than
guessed at. The existing ``features.review.pico`` parser takes the rest of the sentence for
each element and misses the structure of most questions, so it is not used here (see
``docs/features/mcp-server.md`` for the measured difference).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import re

FRAMEWORKS = ("PICO", "PICOS", "PICOT", "SPIDER")

#: Elements each framework reports, in order, and the ones it needs to be called complete.
ELEMENTS = {
    "PICO": ("population", "intervention", "comparison", "outcome"),
    "PICOS": ("population", "intervention", "comparison", "outcome", "study_design"),
    "PICOT": ("population", "intervention", "comparison", "outcome", "time_frame"),
    "SPIDER": ("sample", "phenomenon_of_interest", "design", "evaluation", "research_type"),
}
REQUIRED = {
    "PICO": ("population", "intervention", "outcome"),
    "PICOS": ("population", "intervention", "outcome", "study_design"),
    "PICOT": ("population", "intervention", "outcome", "time_frame"),
    "SPIDER": ("sample", "phenomenon_of_interest", "evaluation"),
}
#: Query terms are built from these, in this order, unless the caller chooses.
DEFAULT_QUERY_ELEMENTS = ("population", "intervention")
MAX_QUESTION_CHARS = 2000

_VERBS = (
    r"reduc(?:e|es|ed)|improv(?:e|es|ed)|affect(?:s|ed)?|prevent(?:s|ed)?|increas(?:e|es|ed)|"
    r"decreas(?:e|es|ed)|lower(?:s|ed)?|alter(?:s|ed)?|influenc(?:e|es|ed)|chang(?:e|es|ed)|"
    r"enhanc(?:e|es|ed)|impact(?:s|ed)?|promot(?:e|es|ed)|worsen(?:s|ed)?|rais(?:e|es|ed)|"
    r"modify|modifies|protect(?:s)? against|caus(?:e|es|ed)|lead(?:s)? to|predict(?:s)?|"
    r"mitigat(?:e|es)|attenuat(?:e|es)|suppress(?:es)?|treat(?:s)?|cur(?:e|es)|help(?:s)?|"
    r"slow(?:s)?|delay(?:s)?|stimulat(?:e|es)|inhibit(?:s)?"
)
_GERUND = re.compile(
    r"^(?:reducing|improving|preventing|increasing|decreasing|lowering|managing|treating|"
    r"enhancing|promoting|controlling|affecting|slowing|delaying|mitigating|minimi[sz]ing|"
    r"maximi[sz]ing|achieving|maintaining)\s+",
    re.IGNORECASE,
)
_BOUNDARY = (
    r"(?=\s+(?:for|in|on|at|after|over|within|among|amongst|during|regarding)\b|\s*[,;?]|\s*$)"
)
_POP_HEAD = (
    r"patients?|adults?|children|child|adolescents?|infants?|neonates?|newborns?|toddlers?|"
    r"women|woman|men|man|people|persons?|individuals?|participants?|subjects?|volunteers?|"
    r"elderly|veterans?|students?|nurses?|physicians?|doctors?|clinicians?|workers?|caregivers?|"
    r"survivors?|mothers?|parents?|athletes?|smokers?|residents?|populations?|cohorts?|"
    r"communities|families|households|mice|mouse|rats?|animals?|cell lines?|cells|samples?|"
    r"specimens?|isolates?|hospitali[sz]ed|outpatients?|inpatients?|older people"
)
_FUNCTION_WORDS = r"in|on|at|for|of|to|with|among|amongst|and|or|by|from|as|than|versus|vs"
_FLAGS = re.IGNORECASE

_DESIGN = re.compile(
    r"\b(?:randomi[sz]ed controlled trials?|randomi[sz]ed clinical trials?|randomi[sz]ed trials?|"
    r"RCTs?|systematic reviews?|meta-?analys[ie]s|cohort stud(?:y|ies)|"
    r"case[- ]control stud(?:y|ies)|cross-sectional stud(?:y|ies)|"
    r"observational stud(?:y|ies)|qualitative stud(?:y|ies)|"
    r"clinical trials?|pilot stud(?:y|ies)|case series|case reports?)\b",
    _FLAGS,
)
_NUMBER = r"(?:\d+(?:\.\d+)?|one|two|three|four|five|six|eight|ten|twelve|eighteen|twenty-four)"
_TIME = re.compile(
    rf"\b(?:(?:at|after|over|within|during|for|up to|following|by)\s+)?{_NUMBER}[ -]?"
    r"(?:days?|weeks?|months?|years?)(?:\s+(?:of\s+)?follow[- ]?up)?\b|\b(?:short|long)-term\b",
    _FLAGS,
)
_COMPARISON = [
    re.compile(
        rf"\b(?:compared\s+(?:with|to|against)|in\s+comparison\s+(?:with|to)|versus|vs\.?|"
        rf"relative\s+to|rather\s+than|instead\s+of)\s+(?P<c>[^,;?]+?){_BOUNDARY}",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:effective|efficacious|beneficial|safe|safer|useful|good)\s+"
        rf"(?P<m>as\s+(?P<c>[^,;?]+?)){_BOUNDARY}",
        _FLAGS,
    ),
    re.compile(
        r"\b(?:superior|inferior|preferable|better|worse|more\s+\w+|less\s+\w+)\s+"
        rf"(?P<m>(?:to|than)\s+(?P<c>[^,;?]+?)){_BOUNDARY}",
        _FLAGS,
    ),
]
_LEADING_POPULATION = re.compile(
    r"^[\s,;:]*(?:in|among|amongst|for)\s+(?:an?\s+|the\s+)?(?P<p>[^,;?]+?)\s*,", _FLAGS
)
_TAIL_POPULATION = re.compile(
    rf"\b(?:in|among|amongst|for)\s+(?:an?\s+|the\s+)?"
    rf"(?P<p>(?:(?!(?:{_FUNCTION_WORDS})\b)[\w-]+\s+){{0,3}}?(?:{_POP_HEAD})\b[^,;?]*?)"
    rf"{_BOUNDARY.replace('for|', '')}",
    _FLAGS,
)

_TAIL = r"\s*\??\s*$"
_FRAMES: list[tuple[str, re.Pattern[str]]] = [
    (
        "association",
        re.compile(
            r"^[\s,;:]*(?:is|are|was|were|does|do)\s+(?P<i>.+?)\s+(?:associated\s+with|"
            r"linked\s+(?:to|with)|related\s+to|predictive\s+of|a\s+risk\s+factor\s+for)\s+"
            rf"(?P<o>.+?){_TAIL}",
            _FLAGS,
        ),
    ),
    (
        "verb",
        re.compile(
            r"^[\s,;:]*(?:how\s+)?(?:does|do|did|can|could|will|would|might|may|should)\s+"
            rf"(?P<i>.+?)\s+(?P<v>{_VERBS})\s+(?P<o>.+?){_TAIL}",
            _FLAGS,
        ),
    ),
    (
        "effect_of",
        re.compile(
            r"^[\s,;:]*(?:what\s+(?:is|are|was|were)\s+)?(?:the\s+)?(?:effects?|impact|"
            r"efficacy|effectiveness|safety|role|influence|benefits?|risks?)\s+of\s+"
            rf"(?P<i>.+?)\s+(?P<prep>on|in|for|against|upon)\s+(?P<o>.+?){_TAIL}",
            _FLAGS,
        ),
    ),
    (
        "how_effective",
        re.compile(
            r"^[\s,;:]*how\s+(?:effective|efficacious|safe|useful)\s+(?:is|are)\s+"
            rf"(?P<i>.+?)\s+(?P<prep>for|in|at|against)\s+(?P<o>.+?){_TAIL}",
            _FLAGS,
        ),
    ),
    (
        "is_effective",
        re.compile(
            r"^[\s,;:]*(?:is|are|was|were)\s+(?P<i>.+?)\s+(?:(?:more|less|as)\s+)?"
            r"(?:effective|efficacious|beneficial|safe|safer|useful|superior|inferior|better|"
            r"cost-effective)\s+(?P<prep>for|in|at|against)\s+(?P<o>.+?)" + _TAIL,
            _FLAGS,
        ),
    ),
    (
        "treated_with",
        re.compile(
            r"^[\s,;:]*(?P<p>(?:" + _POP_HEAD + r")\b.+?)\s+(?:treated|managed|receiving|given|on)"
            rf"\s+(?:with\s+)?(?P<i>.+?){_TAIL}",
            _FLAGS,
        ),
    ),
]

_SPIDER_EVALUATION = (
    r"experiences?|perceptions?|perspectives?|views?|attitudes?|beliefs?|opinions?|barriers|"
    r"facilitators|challenges|needs|expectations|feelings|preferences|satisfaction"
)
_SPIDER = re.compile(
    rf"^[\s,;:]*(?:what\s+(?:are|were|is|was)\s+)?(?:the\s+)?(?P<e>{_SPIDER_EVALUATION})\s+"
    r"(?:of|among|for)\s+(?P<s>.+?)"
    r"(?:\s+(?:receiving|undergoing|using|regarding|about|during|following|after|towards?)\s+"
    rf"(?P<pi>.+?))?{_TAIL}",
    _FLAGS,
)
_SPIDER_DESIGN = re.compile(
    r"\b(?:semi-structured\s+interviews?|interviews?|focus\s+groups?|surveys?|questionnaires?|"
    r"ethnograph\w+|grounded\s+theory|phenomenolog\w+|case\s+stud(?:y|ies))\b",
    _FLAGS,
)
_SPIDER_RESEARCH = re.compile(
    r"\b(?:qualitative|quantitative|mixed[- ]methods?)\b(?:\s+(?:study|research|studies))?", _FLAGS
)


@dataclass(frozen=True)
class Span:
    """A verbatim piece of the question and where it is (``question[start:end] == text``)."""

    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, int | str]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass
class Decomposition:
    framework: str
    elements: dict[str, Span] = field(default_factory=dict)
    relation: Span | None = None  # the verb or phrase that links intervention and outcome
    notes: list[str] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        return [name for name in REQUIRED[self.framework] if name not in self.elements]

    @property
    def optional_missing(self) -> list[str]:
        return [
            name
            for name in ELEMENTS[self.framework]
            if name not in self.elements and name not in REQUIRED[self.framework]
        ]

    @property
    def complete(self) -> bool:
        return not self.missing


class _Work:
    """The question with the spans already taken blanked out, so a later rule cannot reuse them."""

    def __init__(self, question: str) -> None:
        self.question = question
        self.chars = list(question)

    @property
    def text(self) -> str:
        return "".join(self.chars)

    def take(self, start: int, end: int) -> None:
        for index in range(start, end):
            self.chars[index] = " "

    def span(self, start: int, end: int) -> Span | None:
        """The text between ``start`` and ``end`` without surrounding space and punctuation."""
        raw = "".join(self.chars[start:end])  # blanked parts count as space
        lead = len(raw) - len(raw.lstrip(" \t\n,;:"))
        trail = len(raw) - len(raw.rstrip(" \t\n,;:?."))
        start, end = start + lead, end - trail
        if end <= start:
            return None
        return Span(self.question[start:end], start, end)


def _strip_gerund(span: Span | None) -> tuple[Span | None, Span | None]:
    """``reducing hospitalisation`` -> (``hospitalisation``, ``reducing``)."""
    if span is None:
        return None, None
    match = _GERUND.match(span.text)
    if not match:
        return span, None
    verb = Span(span.text[: match.end()].strip(), span.start, span.start + match.end() - 1)
    rest = span.text[match.end() :]
    return (Span(rest, span.start + match.end(), span.end) if rest else None), verb


def _put(result: Decomposition, name: str, span: Span | None) -> None:
    if span is not None and name not in result.elements:
        result.elements[name] = span


def _take_phrases(result: Decomposition, work: _Work) -> None:
    """Study design and time frame: self-contained phrases, taken out first."""
    for name, pattern in (("study_design", _DESIGN), ("time_frame", _TIME)):
        match = pattern.search(work.text)
        if match:
            _put(result, name, work.span(match.start(), match.end()))
            work.take(match.start(), match.end())


def _take_comparison(result: Decomposition, work: _Work) -> None:
    """The marker goes with the comparison; the value is the element."""
    for pattern in _COMPARISON:
        match = pattern.search(work.text)
        if match:
            _put(result, "comparison", work.span(*match.span("c")))
            work.take(*(match.span("m") if "m" in pattern.groupindex else match.span()))
            return


def _take_population(result: Decomposition, work: _Work) -> None:
    """``In P, ...`` first, otherwise ``... in P`` at the end of the question."""
    match = _LEADING_POPULATION.search(work.text)
    if match:
        _put(result, "population", work.span(*match.span("p")))
        work.take(match.start(), match.end())
    if "population" in result.elements:
        return
    tails = list(_TAIL_POPULATION.finditer(work.text))
    if tails:  # the last one: a population is named at the end of the question
        _put(result, "population", work.span(*tails[-1].span("p")))
        work.take(tails[-1].start(), tails[-1].end())


def _apply_frame(result: Decomposition, work: _Work) -> None:
    """Intervention, outcome and the relation between them, from the first pattern that fits."""
    for name, pattern in _FRAMES:
        match = pattern.search(work.text)
        if not match:
            continue
        groups = match.groupdict()
        _put(result, "intervention", work.span(*match.span("i")))
        if groups.get("p"):
            _put(result, "population", work.span(*match.span("p")))
        if groups.get("o"):
            outcome, verb = _strip_gerund(work.span(*match.span("o")))
            _put(result, "outcome", outcome)
            result.relation = verb
        if groups.get("v"):
            result.relation = work.span(*match.span("v"))
        if name in ("is_effective", "how_effective"):
            result.notes.append(
                "'effective for X': X is read as the outcome; if it is the condition treated, "
                "it belongs to the population"
            )
        if name == "association":
            result.notes.append("an association question: the intervention is the exposure")
        return
    result.notes.append(
        "no known question pattern was recognised, so intervention and outcome are not "
        "extracted; state the question as 'does X reduce Y in Z?'"
    )


def _decompose_pico(question: str, framework: str) -> Decomposition:
    result = Decomposition(framework)
    work = _Work(question)
    _take_phrases(result, work)
    _take_comparison(result, work)
    _take_population(result, work)
    _apply_frame(result, work)
    return result


def _decompose_spider(question: str) -> Decomposition:
    result = Decomposition("SPIDER")
    work = _Work(question)
    for name, pattern in (("design", _SPIDER_DESIGN), ("research_type", _SPIDER_RESEARCH)):
        match = pattern.search(work.text)
        if match:
            result.elements[name] = Span(question[match.start() : match.end()], *match.span())
            work.take(match.start(), match.end())
    match = _SPIDER.search(work.text)
    if match:
        for name, group in (
            ("evaluation", "e"),
            ("sample", "s"),
            ("phenomenon_of_interest", "pi"),
        ):
            if match.group(group):
                span = work.span(*match.span(group))
                if span:
                    result.elements[name] = span
    else:
        result.notes.append(
            "no SPIDER pattern was recognised; the question should ask for the experiences, "
            "views or attitudes of a group, e.g. 'What are the experiences of nurses ...?'"
        )
    return result


def decompose(question: str, framework: str = "PICO") -> Decomposition:
    """The elements of ``question`` under ``framework`` (one of :data:`FRAMEWORKS`)."""
    framework = framework.strip().upper()
    if framework not in FRAMEWORKS:
        raise ValueError(f"unknown framework {framework!r}; valid: {list(FRAMEWORKS)}")
    text = question.strip()
    if not text:
        raise ValueError("the question is empty")
    if len(text) > MAX_QUESTION_CHARS:
        raise ValueError(
            f"the question is {len(text)} characters; the limit is {MAX_QUESTION_CHARS}"
        )
    return _decompose_spider(text) if framework == "SPIDER" else _decompose_pico(text, framework)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_CONDITION = re.compile(
    r"\s+(?:with|having|diagnosed\s+with|who\s+have|who\s+has|suffering\s+from|living\s+with)\s+",
    re.IGNORECASE,
)
_ALTERNATIVES = re.compile(r"\s+or\s+|\s*/\s*|\s*,\s*", re.IGNORECASE)
_UNSAFE = re.compile(r'["()\[\]{}:*?\\^~!]')
_LEADING_DETERMINER = re.compile(r"^(?:the|a|an|of)\s+", re.IGNORECASE)


def concepts(element: str, text: str) -> list[str]:
    """Search terms for an element: its alternatives, with the condition of a population.

    ``adults with type 2 diabetes`` gives ``type 2 diabetes`` (demographics are poorly
    indexed and cut recall); ``statins or aspirin`` gives both.
    """
    if element == "population":
        parts = _CONDITION.split(text, maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            text = parts[1]
    terms: list[str] = []
    for alternative in _ALTERNATIVES.split(text):
        term = _LEADING_DETERMINER.sub("", _UNSAFE.sub(" ", alternative))
        term = " ".join(term.split())
        if len(term) > 1 and term.lower() not in {t.lower() for t in terms}:
            terms.append(term)
    return terms


def phrase(term: str) -> str:
    """A Europe PMC phrase: quoted when it has more than one word."""
    return f'"{term}"' if re.search(r"[\s-]", term) else term


def build_query(
    decomposition: Decomposition,
    use: tuple[str, ...] = DEFAULT_QUERY_ELEMENTS,
    expand: Callable[[str], str | None] | None = None,
) -> tuple[str, list[str]]:
    """``(query, elements used)``: an AND of one OR group per element.

    ``expand`` may turn a term into a ready fragment (for example a MeSH group); terms it
    returns ``None`` for are quoted as written.
    """
    groups: list[str] = []
    used: list[str] = []
    for name in use:
        span = decomposition.elements.get(name)
        if span is None:
            continue
        parts = []
        for term in concepts(name, span.text):
            parts.append((expand(term) if expand else None) or phrase(term))
        if not parts:
            continue
        used.append(name)
        groups.append(parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")")
    return " AND ".join(groups), used
