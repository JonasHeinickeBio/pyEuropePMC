#!/usr/bin/env python3
"""Large-scale ME/CFS literature readiness demo for KG construction.

This runnable example performs a production-style crawl over Europe PMC ME/CFS
results, collecting up to 100,000 records with cursor pagination and evaluating
whether the resulting corpus is suitable for scientific literature KG and
physiological KG construction.

The checks in this demo are aligned with common biomedical KG best-practice
requirements from the literature, including:
- FAIR data stewardship (Wilkinson et al., 2016, doi:10.1038/sdata.2016.18)
- Ontology-grounded entity linking and semantic interoperability
- Context-preserving annotations (section/prefix/postfix)
- Provenance and evidence traceability
- Physiological/clinical KG needs: temporal-context anchors, confidence
  signals, and machine-readable linkage to external biomedical concepts.

FEATURES:
- Cursor-based pagination to collect large literature corpora efficiently
- Real-time progress reporting with ETA calculations during long-running phases
- Checkpoint/cache system for resuming interrupted runs
- Multi-phase execution (corpus collection → XML/annotation probes → evaluation)
- Detailed metrics (OA ratio, PMC presence, text-mining signals)
- 9-point KG capability matrix (scientific literature + physiological domains)
- JSON report output for downstream analysis

CACHING & RESUMPTION:
- By default, checkpoints are saved after each phase to ~/.cache/mecfs_demo/
- Use --no-cache to disable caching
- Use --clear-cache to delete existing checkpoints and start fresh
- Use --no-resume to ignore checkpoints and re-run all phases
- Checkpoints enable resuming from the last completed phase if interrupted

PROGRESS REPORTING:
- Corpus crawl: Shows scanned/target papers, hit count, requests, ETA
- XML probes: Real-time progress with success count and ETA
- Annotation probes: Real-time progress with success count and ETA
- All phases report elapsed time and estimated time-to-completion

Usage:
    python 04-mecfs-kg-readiness-demo.py
    python 04-mecfs-kg-readiness-demo.py --no-cache
    python 04-mecfs-kg-readiness-demo.py --clear-cache --target-papers 50000

Environment variables:
    PYEUROPMC_MECFS_TARGET_PAPERS: Corpus size target, default 100000
    PYEUROPMC_MECFS_PAGE_SIZE: Search page size, default 1000
    PYEUROPMC_MECFS_XML_PROBE_SIZE: XML probe sample size, default 0 (all)
    PYEUROPMC_MECFS_ANNOTATION_PROBE_SIZE: Annotation probe sample size, default 0 (all)

Output:
    A JSON readiness report is written to data/output by default.
    Cache/checkpoints are stored in data/output/.mecfs_demo_cache by default.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import datetime
import logging
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any

from rdflib import Namespace

from pyeuropepmc.clients.annotations import AnnotationsClient
from pyeuropepmc.clients.fulltext import FullTextClient
from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.processing.annotation_parser import parse_annotations
from pyeuropepmc.processing.annotations_to_rdf import annotations_to_rdf

MECFS_QUERY = (
    '("myalgic encephalomyelitis" OR "chronic fatigue syndrome" OR "ME/CFS") '
    "AND (HAS_ABSTRACT:y OR IN_PMC:y)"
)

TARGET_PAPERS_DEFAULT = 100_000
PAGE_SIZE_DEFAULT = 1_000
XML_PROBE_SIZE_DEFAULT = 0
ANNOTATION_PROBE_SIZE_DEFAULT = 0
DEFAULT_OUTPUT_PATH = Path("data/output/mecfs_kg_readiness_demo_report.json")
DEFAULT_CACHE_PATH = Path("data/output/.mecfs_demo_cache")
DEFAULT_PROGRESS_EVERY = 10_000

BEST_PRACTICE_REFERENCES = [
    {
        "title": "FAIR guiding principles for scientific data management and stewardship",
        "reference": "Wilkinson et al., Scientific Data (2016)",
        "doi": "10.1038/sdata.2016.18",
    },
    {
        "title": "Open Annotation Data Model",
        "reference": "W3C Open Annotation Community Group",
        "doi": "https://www.w3.org/TR/annotation-model/",
    },
    {
        "title": "OBO Foundry principles for interoperable biomedical ontologies",
        "reference": "Biomedical ontology best practice",
        "doi": "https://obofoundry.org/principles/fp-000-summary.html",
    },
]


@dataclass
class CorpusMetrics:
    """Aggregated corpus-level metrics from Europe PMC search results."""

    target_papers: int
    hit_count: int
    scanned_papers: int
    requests_used: int
    open_access_papers: int
    papers_in_pmc: int
    papers_with_text_mined_terms: int
    unique_pmcids_seen: int

    @property
    def effective_target(self) -> int:
        """Target bounded by available Europe PMC hit count."""
        if self.hit_count <= 0:
            return self.target_papers
        return min(self.target_papers, self.hit_count)

    @property
    def open_access_ratio(self) -> float:
        """Fraction of scanned papers that are open access."""
        return self.open_access_papers / self.scanned_papers if self.scanned_papers else 0.0

    @property
    def in_pmc_ratio(self) -> float:
        """Fraction of scanned papers with PMC full-text presence."""
        return self.papers_in_pmc / self.scanned_papers if self.scanned_papers else 0.0

    @property
    def text_mined_ratio(self) -> float:
        """Fraction of scanned papers with text-mined terms available."""
        return (
            self.papers_with_text_mined_terms / self.scanned_papers if self.scanned_papers else 0.0
        )


@dataclass
class ProbeMetrics:
    """Probe results for XML and annotation availability."""

    xml_probe_size: int
    xml_successes: int
    annotation_probe_size: int
    annotation_successes: int
    annotation_entity_hits: int

    @property
    def xml_success_ratio(self) -> float:
        """Fraction of sampled PMCID records with retrievable XML."""
        return self.xml_successes / self.xml_probe_size if self.xml_probe_size else 0.0

    @property
    def annotation_success_ratio(self) -> float:
        """Fraction of sampled PMCID records with non-empty annotation responses."""
        return (
            self.annotation_successes / self.annotation_probe_size
            if self.annotation_probe_size
            else 0.0
        )

    @property
    def xml_failure_ratio(self) -> float:
        """Fraction of XML probes that did not yield a file."""
        return 1.0 - self.xml_success_ratio if self.xml_probe_size else 0.0

    @property
    def annotation_failure_ratio(self) -> float:
        """Fraction of annotation probes that did not yield structured data."""
        return 1.0 - self.annotation_success_ratio if self.annotation_probe_size else 0.0


@dataclass
class KGCapabilityResult:
    """Single capability check result."""

    domain: str
    capability: str
    passed: bool
    rationale: str
    reference: str


@dataclass
class KGReadinessReport:
    """Structured output for professional QA traceability."""

    query: str
    corpus_metrics: CorpusMetrics
    probe_metrics: ProbeMetrics
    enrichment_fields_present: dict[str, bool]
    rdf_enrichment_present: dict[str, bool]
    capabilities: list[KGCapabilityResult]


@dataclass
class ArticleCandidate:
    """Identifiers used to probe a single paper across APIs."""

    pmcid: str
    pmid: str | None
    doi: str | None


@dataclass
class ProgressTracker:
    """Track and print high-level demo progress."""

    progress_every: int
    start_time: float = field(default_factory=time.time)
    phase_start_time: float = field(default_factory=time.time)

    def announce(self, message: str) -> None:
        """Print a phase banner with timing info."""
        elapsed = time.time() - self.start_time
        if elapsed > 1:
            print(f"\n[{message}] (elapsed: {self._format_time(elapsed)})")
        else:
            print(f"\n[{message}]")
        self.phase_start_time = time.time()

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h{m}m{s}s"
        elif m > 0:
            return f"{m}m{s}s"
        else:
            return f"{s}s"

    def _estimate_eta(self, current: int, target: int, elapsed: float) -> str:
        """Estimate time to completion."""
        if current <= 0:
            return "?"
        rate = current / elapsed
        remaining = target - current
        eta_seconds = remaining / rate if rate > 0 else 0
        return self._format_time(eta_seconds)

    def scan_update(self, scanned: int, target: int, hit_count: int, requests_used: int) -> None:
        """Print corpus crawl progress at a fixed interval with ETA."""
        if scanned == 0:
            return
        if scanned % self.progress_every != 0 and scanned < target:
            return
        elapsed = time.time() - self.phase_start_time
        eta = self._estimate_eta(scanned, target, elapsed)
        print(
            f"  progress: {scanned:,}/{target:,} papers "
            f"| hits={hit_count:,} | requests={requests_used} | elapsed={self._format_time(elapsed)} | ETA={eta}"
        )

    def probe_update(self, label: str, current: int, total: int) -> None:
        """Print XML/annotation probe progress."""
        print(f"  {label}: {current:,}/{total:,}")


@dataclass
class CheckpointData:
    """Serializable checkpoint for resuming interrupted runs."""

    phase: str  # "corpus", "probes", "enrichment", "complete"
    query: str
    target_papers: int
    page_size: int
    xml_probe_size: int
    annotation_probe_size: int
    corpus_metrics: dict[str, Any] | None = None
    sampled_articles: list[dict[str, Any]] | None = None
    probe_metrics: dict[str, Any] | None = None
    first_annotation_payload: dict[str, Any] | None = None
    enrichment_fields: dict[str, Any] | None = None
    rdf_fields: dict[str, Any] | None = None
    capabilities: list[dict[str, Any]] | None = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointData":
        """Reconstruct from JSON dictionary."""
        return cls(**data)


class CheckpointManager:
    """Manage checkpoint persistence and recovery."""

    def __init__(self, cache_dir: Path):
        """Initialize checkpoint manager with cache directory."""
        self.cache_dir = Path(cache_dir)
        self.checkpoint_file = self.cache_dir / "checkpoint.json"

    def save(self, checkpoint: CheckpointData) -> None:
        """Save checkpoint to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    def load(self) -> CheckpointData | None:
        """Load checkpoint from disk if it exists."""
        if not self.checkpoint_file.exists():
            return None
        try:
            data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
            return CheckpointData.from_dict(data)
        except Exception:
            return None

    def clear(self) -> None:
        """Clear checkpoint and cache directory."""
        if self.cache_dir.exists():
            import shutil

            shutil.rmtree(self.cache_dir)


def _env_int(name: str, default: int) -> int:
    """Parse integer environment variables safely."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


def _format_seconds(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    if seconds < 0:
        return "?"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h{m}m{s}s"
    elif m > 0:
        return f"{m}m{s}s"
    else:
        return f"{s}s"


def _extract_results(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract Europe PMC results safely from the search response."""
    result_list = response.get("resultList", {})
    if not isinstance(result_list, dict):
        return []
    results = result_list.get("result", [])
    return results if isinstance(results, list) else []


def _is_yes(value: Any) -> bool:
    """Normalize Europe PMC Y/N fields to boolean."""
    return str(value or "").strip().upper() == "Y"


def _annotation_identifier_candidates(article: ArticleCandidate) -> list[str]:
    """Build an ordered list of identifiers for annotation lookups."""
    candidates: list[str] = []
    if article.pmid:
        candidates.append(article.pmid)
    if article.pmcid and article.pmcid not in candidates:
        candidates.append(article.pmcid)
    if article.doi and article.doi not in candidates:
        candidates.append(article.doi)
    return candidates


def _collect_mecfs_corpus(
    client: SearchClient,
    query: str,
    target_papers: int,
    page_size: int,
    progress_every: int = 10_000,
) -> tuple[CorpusMetrics, list[ArticleCandidate]]:
    """Collect up to target_papers ME/CFS records with cursor pagination."""
    cursor = "*"
    hit_count = 0
    scanned_papers = 0
    requests_used = 0
    open_access_papers = 0
    papers_in_pmc = 0
    papers_with_text_mined_terms = 0
    sampled_articles: list[ArticleCandidate] = []
    seen_article_keys: set[str] = set()

    max_requests = math.ceil(target_papers / page_size) + 10
    start_time = time.time()

    while scanned_papers < target_papers and requests_used < max_requests:
        response = client.search(
            query=query,
            resultType="lite",
            format="json",
            pageSize=page_size,
            cursorMark=cursor,
        )
        assert isinstance(response, dict)

        if requests_used == 0:
            hit_count = int(response.get("hitCount", 0) or 0)

        results = _extract_results(response)
        if not results:
            break

        for paper in results:
            scanned_papers += 1

            if _is_yes(paper.get("isOpenAccess")):
                open_access_papers += 1

            pmcid = str(paper.get("pmcid") or "").strip()
            pmid = str(paper.get("pmid") or "").strip() or None
            doi = str(paper.get("doi") or "").strip() or None
            article_key = pmcid or pmid or doi or str(scanned_papers)

            if _is_yes(paper.get("inPMC")) and pmcid:
                papers_in_pmc += 1

            if _is_yes(paper.get("isOpenAccess")) and article_key not in seen_article_keys:
                seen_article_keys.add(article_key)
                sampled_articles.append(
                    ArticleCandidate(
                        pmcid=pmcid,
                        pmid=pmid,
                        doi=doi,
                    )
                )

            if _is_yes(paper.get("hasTextMinedTerms")):
                papers_with_text_mined_terms += 1

            # Print progress periodically
            if scanned_papers % progress_every == 0 or scanned_papers >= target_papers:
                elapsed = time.time() - start_time
                rate = scanned_papers / elapsed if elapsed > 0 else 0
                remaining = target_papers - scanned_papers
                eta_sec = remaining / rate if rate > 0 else 0
                eta_str = _format_seconds(eta_sec)
                print(
                    f"    scanned {scanned_papers:,}/{target_papers:,} | "
                    f"rate={rate:.1f} papers/sec | ETA={eta_str}"
                )

            if scanned_papers >= target_papers:
                break

        requests_used += 1
        next_cursor = response.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = str(next_cursor)

    metrics = CorpusMetrics(
        target_papers=target_papers,
        hit_count=hit_count,
        scanned_papers=scanned_papers,
        requests_used=requests_used,
        open_access_papers=open_access_papers,
        papers_in_pmc=papers_in_pmc,
        papers_with_text_mined_terms=papers_with_text_mined_terms,
        unique_pmcids_seen=len({article.pmcid for article in sampled_articles if article.pmcid}),
    )
    return metrics, sampled_articles


def _probe_xml_and_annotations(
    articles: list[ArticleCandidate],
    xml_probe_size: int,
    annotation_probe_size: int,
    progress_interval: int = 100,
) -> tuple[ProbeMetrics, dict[str, Any] | None]:
    """Probe XML and annotation availability over the open-access candidate set."""
    xml_candidates = [article.pmcid for article in articles if article.pmcid]
    annotation_candidates = articles

    if xml_probe_size > 0:
        xml_candidates = xml_candidates[:xml_probe_size]
    if annotation_probe_size > 0:
        annotation_candidates = annotation_candidates[:annotation_probe_size]

    xml_successes = 0
    annotation_successes = 0
    annotation_entity_hits = 0
    first_annotation_payload: dict[str, Any] | None = None

    # XML probing with progress reporting
    print(f"    Probing {len(xml_candidates):,} papers for XML availability...")
    xml_start = time.time()
    with tempfile.TemporaryDirectory(prefix="mecfs_xml_probe_") as temp_dir:
        temp_path = Path(temp_dir)

        with FullTextClient(rate_limit_delay=0.1) as fulltext_client:
            for idx, pmcid in enumerate(xml_candidates, 1):
                try:
                    out_file = temp_path / f"{pmcid}.xml"
                    downloaded = fulltext_client.download_xml_by_pmcid(pmcid, out_file)
                    if downloaded and Path(downloaded).exists() and Path(downloaded).stat().st_size > 0:
                        xml_successes += 1
                except Exception:
                    continue

                if idx % progress_interval == 0 or idx == len(xml_candidates):
                    elapsed = time.time() - xml_start
                    rate = idx / elapsed if elapsed > 0 else 0
                    remaining = len(xml_candidates) - idx
                    eta_sec = remaining / rate if rate > 0 else 0
                    print(
                        f"      XML: {idx:,}/{len(xml_candidates):,} | "
                        f"success={xml_successes:,} | ETA={_format_seconds(eta_sec)}"
                    )

    # Annotation probing with progress reporting
    print(f"    Probing {len(annotation_candidates):,} papers for annotations...")
    ann_start = time.time()
    with AnnotationsClient(rate_limit_delay=0.1) as annotation_client:
        for idx, article in enumerate(annotation_candidates, 1):
            for article_id in _annotation_identifier_candidates(article):
                try:
                    payload = annotation_client.get_annotations_by_article_ids(
                        [article_id], section="all"
                    )
                    parsed = parse_annotations(payload)
                    entities = parsed.get("entities", [])
                    relationships = parsed.get("relationships", [])
                    sentences = parsed.get("sentences", [])

                    if entities or relationships or sentences:
                        annotation_successes += 1

                    if entities:
                        annotation_entity_hits += 1
                        if first_annotation_payload is None:
                            first_annotation_payload = parsed
                        break
                except Exception:
                    continue

            if idx % progress_interval == 0 or idx == len(annotation_candidates):
                elapsed = time.time() - ann_start
                rate = idx / elapsed if elapsed > 0 else 0
                remaining = len(annotation_candidates) - idx
                eta_sec = remaining / rate if rate > 0 else 0
                print(
                    f"      Annotations: {idx:,}/{len(annotation_candidates):,} | "
                    f"success={annotation_successes:,} | ETA={_format_seconds(eta_sec)}"
                )

    probe_metrics = ProbeMetrics(
        xml_probe_size=len(xml_candidates),
        xml_successes=xml_successes,
        annotation_probe_size=len(annotation_candidates),
        annotation_successes=annotation_successes,
        annotation_entity_hits=annotation_entity_hits,
    )
    return probe_metrics, first_annotation_payload


def _evaluate_enrichment(
    first_annotation_payload: dict[str, Any] | None,
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Evaluate parser and RDF enrichment signals used by downstream KGs."""
    parser_fields = {
        "entity_id": False,
        "annotation_category": False,
        "prefix": False,
        "postfix": False,
        "section": False,
        "article_provenance": False,
    }

    rdf_fields = {
        "owl_same_as": False,
        "entity_category": False,
        "text_prefix": False,
        "text_postfix": False,
        "open_annotation_body": False,
    }

    if not first_annotation_payload:
        return parser_fields, rdf_fields

    entities = first_annotation_payload.get("entities", [])
    if not entities:
        return parser_fields, rdf_fields

    first_entity = entities[0]
    parser_fields["entity_id"] = bool(first_entity.get("id"))
    parser_fields["annotation_category"] = "annotation_category" in first_entity
    parser_fields["prefix"] = "prefix" in first_entity
    parser_fields["postfix"] = "postfix" in first_entity
    parser_fields["section"] = "section" in first_entity
    parser_fields["article_provenance"] = bool(
        first_entity.get("article_id") or first_entity.get("article_uri")
    )

    graph = annotations_to_rdf(first_annotation_payload)

    owl = Namespace("http://www.w3.org/2002/07/owl#")
    oa = Namespace("http://www.w3.org/ns/oa#")
    pyeuropepmc = Namespace("https://w3id.org/pyeuropepmc/vocab#")

    rdf_fields["owl_same_as"] = any(graph.triples((None, owl.sameAs, None)))
    rdf_fields["entity_category"] = any(graph.triples((None, pyeuropepmc.entityCategory, None)))
    rdf_fields["text_prefix"] = any(graph.triples((None, pyeuropepmc.textPrefix, None)))
    rdf_fields["text_postfix"] = any(graph.triples((None, pyeuropepmc.textPostfix, None)))
    rdf_fields["open_annotation_body"] = any(graph.triples((None, oa.hasBody, None)))

    return parser_fields, rdf_fields


def _evaluate_capabilities(
    corpus: CorpusMetrics,
    probes: ProbeMetrics,
    parser_fields: dict[str, bool],
    rdf_fields: dict[str, bool],
) -> list[KGCapabilityResult]:
    """Score capabilities expected for literature and physiological KGs."""
    return [
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="scalable_corpus_ingestion",
            passed=corpus.scanned_papers >= min(corpus.effective_target, corpus.target_papers),
            rationale="KG pipeline can ingest large literature corpora at search scale.",
            reference="Europe PMC large-scale literature indexing practice",
        ),
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="open_access_aware_filtering",
            passed=corpus.open_access_ratio > 0.0,
            rationale="Open-access status should be queryable for licensing and reuse.",
            reference="FAIR principle A1 (doi:10.1038/sdata.2016.18)",
        ),
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="xml_fulltext_retrievability",
            passed=probes.xml_success_ratio > 0.0,
            rationale="Structured full text (XML) is required for robust relation extraction.",
            reference="Biomedical text-mining workflows best practice",
        ),
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="annotation_availability",
            passed=probes.annotation_success_ratio > 0.0,
            rationale="Entity annotations should be available for automated indexing.",
            reference="Europe PMC Annotations API / SciLite model",
        ),
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="ontology_linked_entities",
            passed=rdf_fields["owl_same_as"] and parser_fields["entity_id"],
            rationale="Entities should link to external ontology concepts for interoperability.",
            reference="Ontology alignment and linked data best practice",
        ),
        KGCapabilityResult(
            domain="scientific_literature_kg",
            capability="context_preserving_annotations",
            passed=(
                parser_fields["prefix"]
                and parser_fields["postfix"]
                and parser_fields["section"]
                and rdf_fields["text_prefix"]
                and rdf_fields["text_postfix"]
            ),
            rationale="Mentions should retain textual context to support explainable extraction.",
            reference="Open Annotation model context selectors",
        ),
        KGCapabilityResult(
            domain="physiological_kg",
            capability="clinical_evidence_traceability",
            passed=parser_fields["article_provenance"] and rdf_fields["open_annotation_body"],
            rationale="Physiological assertions require provenance back to source studies.",
            reference="Biomedical evidence graph best practice",
        ),
        KGCapabilityResult(
            domain="physiological_kg",
            capability="semantic_normalization",
            passed=parser_fields["annotation_category"] and rdf_fields["entity_category"],
            rationale="Physiology concepts should be normalized into interpretable categories.",
            reference="Clinical ontology normalization workflows",
        ),
        KGCapabilityResult(
            domain="physiological_kg",
            capability="text_mining_signal_coverage",
            passed=corpus.text_mined_ratio > 0.0 and probes.annotation_entity_hits > 0,
            rationale="A physiology KG should leverage measurable annotation evidence density.",
            reference="Biomedical KG construction from literature pipelines",
        ),
    ]


def _summarize_capabilities(capabilities: list[KGCapabilityResult]) -> dict[str, int]:
    """Summarize pass/fail counts for the capability matrix."""
    passed = sum(1 for capability in capabilities if capability.passed)
    failed = len(capabilities) - passed
    return {"passed": passed, "failed": failed, "total": len(capabilities)}


def _format_status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _print_report(report: KGReadinessReport) -> None:
    """Render a concise operator-friendly report to stdout."""
    corpus = report.corpus_metrics
    probes = report.probe_metrics

    print("\nME/CFS literature KG readiness demo")
    print("=" * 72)
    print(f"Query: {report.query}")
    print(f"Scanned papers: {corpus.scanned_papers:,}")
    print(f"Hit count: {corpus.hit_count:,}")
    print(f"Open access papers: {corpus.open_access_papers:,} ({corpus.open_access_ratio:.1%})")
    print(f"PMC papers: {corpus.papers_in_pmc:,} ({corpus.in_pmc_ratio:.1%})")
    print(f"Text-mined signal papers: {corpus.papers_with_text_mined_terms:,} ({corpus.text_mined_ratio:.1%})")
    print(f"Unique PMCID samples: {corpus.unique_pmcids_seen:,}")
    print(f"XML probe success: {probes.xml_successes}/{probes.xml_probe_size} ({probes.xml_success_ratio:.1%})")
    print(
        f"Annotation probe success: {probes.annotation_successes}/{probes.annotation_probe_size} "
        f"({probes.annotation_success_ratio:.1%})"
    )

    print("\nCapability matrix")
    print("-" * 72)
    for capability in report.capabilities:
        print(
            f"{_format_status(capability.passed):<4} "
            f"{capability.domain:<24} {capability.capability:<30} {capability.rationale}"
        )
        print(f"     {capability.reference}")

    capability_summary = _summarize_capabilities(report.capabilities)
    print(
        "\nCapability summary: "
        f"{capability_summary['passed']}/{capability_summary['total']} passed, "
        f"{capability_summary['failed']} failed"
    )

    print("\nScientific best-practice references")
    print("-" * 72)
    for reference in BEST_PRACTICE_REFERENCES:
        print(f"- {reference['title']} | {reference['reference']} | {reference['doi']}")


def _save_report(report: KGReadinessReport, output_path: Path) -> Path:
    """Persist the structured readiness report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_payload = {
        "query": report.query,
        "corpus_metrics": asdict(report.corpus_metrics),
        "probe_metrics": asdict(report.probe_metrics),
        "enrichment_fields_present": report.enrichment_fields_present,
        "rdf_enrichment_present": report.rdf_enrichment_present,
        "capabilities": [asdict(capability) for capability in report.capabilities],
    }
    output_path.write_text(json.dumps(output_payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the demo."""
    parser = argparse.ArgumentParser(
        description="Run a large-scale ME/CFS Europe PMC readiness demo for KG construction.",
    )
    parser.add_argument(
        "--target-papers",
        type=int,
        default=_env_int("PYEUROPMC_MECFS_TARGET_PAPERS", TARGET_PAPERS_DEFAULT),
        help="Target number of ME/CFS papers to scan (minimum 100000).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=_env_int("PYEUROPMC_MECFS_PAGE_SIZE", PAGE_SIZE_DEFAULT),
        help="Europe PMC page size for cursor pagination.",
    )
    parser.add_argument(
        "--xml-probe-size",
        type=int,
        default=_env_int("PYEUROPMC_MECFS_XML_PROBE_SIZE", XML_PROBE_SIZE_DEFAULT),
        help="How many PMCID records to probe for XML availability. 0 means all open-access PMCID records.",
    )
    parser.add_argument(
        "--annotation-probe-size",
        type=int,
        default=_env_int("PYEUROPMC_MECFS_ANNOTATION_PROBE_SIZE", ANNOTATION_PROBE_SIZE_DEFAULT),
        help="How many records to probe for annotations. 0 means all open-access records.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path where the JSON readiness report will be written.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help="Print corpus progress every N scanned papers.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Directory for checkpoint cache. Set to empty string to disable caching.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable checkpoint caching entirely.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear checkpoint cache and start fresh.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not attempt to resume from checkpoint; always start fresh.",
    )
    return parser


def main() -> int:
    """Run the demo and emit a readiness report."""
    parser = build_arg_parser()
    args = parser.parse_args()

    logging.getLogger("pyeuropepmc").setLevel(logging.CRITICAL)
    logging.getLogger("pyeuropepmc.core.base").setLevel(logging.CRITICAL)
    logging.getLogger("pyeuropepmc.clients.annotations").setLevel(logging.CRITICAL)

    target_papers = max(args.target_papers, TARGET_PAPERS_DEFAULT)
    if target_papers != args.target_papers:
        print(f"Requested target was below {TARGET_PAPERS_DEFAULT:,}; using {target_papers:,}.")

    page_size = max(1, args.page_size)
    xml_probe_size = max(0, args.xml_probe_size)
    annotation_probe_size = max(0, args.annotation_probe_size)
    progress_every = max(1, args.progress_every)

    # Setup caching
    cache_enabled = not args.no_cache and args.cache_dir
    cache_mgr = CheckpointManager(args.cache_dir) if cache_enabled else None

    if args.clear_cache and cache_mgr:
        print("Clearing checkpoint cache...")
        cache_mgr.clear()
        cache_mgr = None
        cache_enabled = False

    # Try to resume from checkpoint
    checkpoint = None
    if cache_enabled and not args.no_resume and cache_mgr:
        checkpoint = cache_mgr.load()
        if checkpoint:
            print(f"\nResuming from checkpoint (phase={checkpoint.phase}, timestamp={checkpoint.timestamp})")

    try:
        tracker = ProgressTracker(progress_every=progress_every)

        # Phase 1: Corpus collection
        if not checkpoint or checkpoint.phase == "corpus":
            tracker.announce("Corpus crawl")

            with SearchClient(rate_limit_delay=0.1) as search_client:
                corpus_metrics, sampled_articles = _collect_mecfs_corpus(
                    client=search_client,
                    query=MECFS_QUERY,
                    target_papers=target_papers,
                    page_size=page_size,
                    progress_every=progress_every,
                )

            if corpus_metrics.scanned_papers == 0:
                print("No ME/CFS papers were returned from Europe PMC for this demo run.")
                return 1

            print(
                f"Open-access papers discovered: {corpus_metrics.open_access_papers:,}; "
                "checking all available OA records for XML and annotations."
            )

            tracker.scan_update(
                scanned=corpus_metrics.scanned_papers,
                target=target_papers,
                hit_count=corpus_metrics.hit_count,
                requests_used=corpus_metrics.requests_used,
            )

            # Save checkpoint after corpus crawl
            if cache_enabled and cache_mgr:
                checkpoint = CheckpointData(
                    phase="probes",
                    query=MECFS_QUERY,
                    target_papers=target_papers,
                    page_size=page_size,
                    xml_probe_size=xml_probe_size,
                    annotation_probe_size=annotation_probe_size,
                    corpus_metrics=asdict(corpus_metrics),
                    sampled_articles=[
                        {"pmcid": a.pmcid, "pmid": a.pmid, "doi": a.doi}
                        for a in sampled_articles
                    ],
                )
                cache_mgr.save(checkpoint)
                print(f"  ✓ Checkpoint saved (corpus phase complete)")
        else:
            # Restore from checkpoint
            corpus_metrics = CorpusMetrics(**checkpoint.corpus_metrics)
            sampled_articles = [
                ArticleCandidate(**article) for article in checkpoint.sampled_articles
            ]
            print(f"  ✓ Restored corpus metrics ({corpus_metrics.scanned_papers:,} papers)")

        # Phase 2: XML and annotation probes
        if not checkpoint or checkpoint.phase == "probes":
            tracker.announce("XML and annotation probes")

            probe_metrics, first_annotation_payload = _probe_xml_and_annotations(
                sampled_articles,
                xml_probe_size=xml_probe_size,
                annotation_probe_size=annotation_probe_size,
                progress_interval=100,
            )

            tracker.probe_update("XML probe complete", probe_metrics.xml_successes, probe_metrics.xml_probe_size)
            tracker.probe_update(
                "Annotation probe complete",
                probe_metrics.annotation_successes,
                probe_metrics.annotation_probe_size,
            )

            print(
                "  XML failures: "
                f"{probe_metrics.xml_probe_size - probe_metrics.xml_successes:,}/"
                f"{probe_metrics.xml_probe_size:,}"
            )
            print(
                "  Annotation failures: "
                f"{probe_metrics.annotation_probe_size - probe_metrics.annotation_successes:,}/"
                f"{probe_metrics.annotation_probe_size:,}"
            )

            # Save checkpoint after probes
            if cache_enabled and cache_mgr and checkpoint:
                checkpoint.phase = "enrichment"
                checkpoint.probe_metrics = asdict(probe_metrics)
                checkpoint.first_annotation_payload = first_annotation_payload
                cache_mgr.save(checkpoint)
                print(f"  ✓ Checkpoint saved (probes phase complete)")
        else:
            # Restore from checkpoint
            probe_metrics = ProbeMetrics(**checkpoint.probe_metrics)
            first_annotation_payload = checkpoint.first_annotation_payload
            print(
                f"  ✓ Restored probe metrics "
                f"(XML: {probe_metrics.xml_successes}/{probe_metrics.xml_probe_size}, "
                f"Annotations: {probe_metrics.annotation_successes}/{probe_metrics.annotation_probe_size})"
            )

        # Phase 3: Enrichment and capability evaluation
        if not checkpoint or checkpoint.phase == "enrichment":
            tracker.announce("Enrichment and capability evaluation")

            parser_fields, rdf_fields = _evaluate_enrichment(first_annotation_payload)
            capabilities = _evaluate_capabilities(corpus_metrics, probe_metrics, parser_fields, rdf_fields)

            report = KGReadinessReport(
                query=MECFS_QUERY,
                corpus_metrics=corpus_metrics,
                probe_metrics=probe_metrics,
                enrichment_fields_present=parser_fields,
                rdf_enrichment_present=rdf_fields,
                capabilities=capabilities,
            )

            # Save checkpoint after evaluation
            if cache_enabled and cache_mgr and checkpoint:
                checkpoint.phase = "complete"
                checkpoint.enrichment_fields = parser_fields
                checkpoint.rdf_fields = rdf_fields
                checkpoint.capabilities = [asdict(c) for c in capabilities]
                cache_mgr.save(checkpoint)
                print(f"  ✓ Checkpoint saved (evaluation phase complete)")
        else:
            # Restore from checkpoint
            parser_fields = checkpoint.enrichment_fields
            rdf_fields = checkpoint.rdf_fields
            capabilities = [KGCapabilityResult(**c) for c in checkpoint.capabilities]
            report = KGReadinessReport(
                query=MECFS_QUERY,
                corpus_metrics=corpus_metrics,
                probe_metrics=probe_metrics,
                enrichment_fields_present=parser_fields,
                rdf_enrichment_present=rdf_fields,
                capabilities=capabilities,
            )
            print(f"  ✓ Restored evaluation results ({len(capabilities)} capabilities assessed)")

        output_path = _save_report(report, args.output)
        _print_report(report)
        print(f"\nJSON report written to: {output_path.resolve()}")

        failed_capabilities = [capability for capability in capabilities if not capability.passed]
        if failed_capabilities:
            print("\nReadiness note: one or more capability checks failed.")
            for capability in failed_capabilities:
                print(f"- {capability.domain}:{capability.capability}")
        else:
            print("\nReadiness note: all capability checks passed.")

        # Clear checkpoint on successful completion
        if cache_enabled and cache_mgr:
            cache_mgr.clear()
            print(f"Cache cleared after successful completion")

        return 0
    except Exception as exc:
        print(f"ME/CFS readiness demo failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
