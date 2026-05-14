"""Large-scale ME/CFS literature readiness test for KG construction.

This test performs a production-style crawl over Europe PMC ME/CFS results,
collecting up to 100,000 records with cursor pagination and evaluating whether
the resulting corpus is suitable for scientific literature KG and physiological KG
construction.

The capability checks in this test are aligned with common biomedical KG
best-practice requirements from the literature, including:
- FAIR data stewardship (Wilkinson et al., 2016, doi:10.1038/sdata.2016.18)
- Ontology-grounded entity linking and semantic interoperability
- Context-preserving annotations (section/prefix/postfix)
- Provenance and evidence traceability
- Physiological/clinical KG needs: temporal-context anchors, confidence signals,
  and machine-readable linkage to external biomedical concepts.

Execution:
- This test is intentionally marked as slow/integration/network.
- It is skipped by default unless PYEUROPMC_RUN_LARGE_NETWORK_TESTS=1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import pytest
from rdflib import Namespace

from pyeuropepmc.clients.annotations import AnnotationsClient
from pyeuropepmc.clients.fulltext import FullTextClient
from pyeuropepmc.clients.search import SearchClient
from pyeuropepmc.processing.annotation_parser import parse_annotations
from pyeuropepmc.processing.annotations_to_rdf import annotations_to_rdf

pytestmark = [pytest.mark.slow, pytest.mark.integration, pytest.mark.network]

MECFS_QUERY = (
    '("myalgic encephalomyelitis" OR "chronic fatigue syndrome" OR "ME/CFS") '
)

TARGET_PAPERS_DEFAULT = 100_000
PAGE_SIZE_DEFAULT = 1_000
XML_PROBE_SIZE_DEFAULT = 30
ANNOTATION_PROBE_SIZE_DEFAULT = 30


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


def _collect_mecfs_corpus(
    client: SearchClient,
    query: str,
    target_papers: int,
    page_size: int,
) -> tuple[CorpusMetrics, list[str]]:
    """Collect up to target_papers ME/CFS records with cursor pagination."""
    cursor = "*"
    hit_count = 0
    scanned_papers = 0
    requests_used = 0
    open_access_papers = 0
    papers_in_pmc = 0
    papers_with_text_mined_terms = 0
    sampled_pmcids: list[str] = []
    seen_pmcids: set[str] = set()

    max_requests = math.ceil(target_papers / page_size) + 10

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
            if _is_yes(paper.get("inPMC")) and pmcid:
                papers_in_pmc += 1
                if pmcid not in seen_pmcids:
                    seen_pmcids.add(pmcid)
                    sampled_pmcids.append(pmcid)

            if _is_yes(paper.get("hasTextMinedTerms")):
                papers_with_text_mined_terms += 1

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
        unique_pmcids_seen=len(seen_pmcids),
    )
    return metrics, sampled_pmcids


def _probe_xml_and_annotations(
    pmcids: list[str],
    xml_probe_size: int,
    annotation_probe_size: int,
) -> tuple[ProbeMetrics, dict[str, Any] | None]:
    """Probe XML and annotation availability over sampled PMCIDs."""
    xml_candidates = pmcids[:xml_probe_size]
    annotation_candidates = pmcids[:annotation_probe_size]

    xml_successes = 0
    annotation_successes = 0
    annotation_entity_hits = 0
    first_annotation_payload: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="mecfs_xml_probe_") as temp_dir:
        temp_path = Path(temp_dir)

        with FullTextClient(rate_limit_delay=0.1) as fulltext_client:
            for pmcid in xml_candidates:
                try:
                    out_file = temp_path / f"{pmcid}.xml"
                    downloaded = fulltext_client.download_xml_by_pmcid(pmcid, out_file)
                    if downloaded and Path(downloaded).exists() and Path(downloaded).stat().st_size > 0:
                        xml_successes += 1
                except Exception:
                    continue

    with AnnotationsClient(rate_limit_delay=0.1) as annotation_client:
        for pmcid in annotation_candidates:
            try:
                payload = annotation_client.get_annotations_by_article_ids([pmcid])
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
            except Exception:
                continue

    probe_metrics = ProbeMetrics(
        xml_probe_size=len(xml_candidates),
        xml_successes=xml_successes,
        annotation_probe_size=len(annotation_candidates),
        annotation_successes=annotation_successes,
        annotation_entity_hits=annotation_entity_hits,
    )
    return probe_metrics, first_annotation_payload


def _evaluate_enrichment(first_annotation_payload: dict[str, Any] | None) -> tuple[dict[str, bool], dict[str, bool]]:
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

    OWL = Namespace("http://www.w3.org/2002/07/owl#")
    OA = Namespace("http://www.w3.org/ns/oa#")
    PYEUROPMC = Namespace("https://w3id.org/pyeuropepmc/vocab#")

    rdf_fields["owl_same_as"] = any(graph.triples((None, OWL.sameAs, None)))
    rdf_fields["entity_category"] = any(graph.triples((None, PYEUROPMC.entityCategory, None)))
    rdf_fields["text_prefix"] = any(graph.triples((None, PYEUROPMC.textPrefix, None)))
    rdf_fields["text_postfix"] = any(graph.triples((None, PYEUROPMC.textPostfix, None)))
    rdf_fields["open_annotation_body"] = any(graph.triples((None, OA.hasBody, None)))

    return parser_fields, rdf_fields


def _evaluate_capabilities(
    corpus: CorpusMetrics,
    probes: ProbeMetrics,
    parser_fields: dict[str, bool],
    rdf_fields: dict[str, bool],
) -> list[KGCapabilityResult]:
    """Score capabilities expected for literature and physiological KGs."""
    capabilities = [
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
    return capabilities


@pytest.mark.skipif(
    os.getenv("PYEUROPMC_RUN_LARGE_NETWORK_TESTS", "0") != "1",
    reason="Set PYEUROPMC_RUN_LARGE_NETWORK_TESTS=1 to run large network ME/CFS test.",
)
def test_mecfs_large_scale_kg_readiness(tmp_path: Path) -> None:
    """Evaluate ME/CFS corpus readiness for scientific-literature and physiological KGs."""
    target_papers = _env_int("PYEUROPMC_MECFS_TARGET_PAPERS", TARGET_PAPERS_DEFAULT)
    page_size = _env_int("PYEUROPMC_MECFS_PAGE_SIZE", PAGE_SIZE_DEFAULT)
    xml_probe_size = _env_int("PYEUROPMC_MECFS_XML_PROBE_SIZE", XML_PROBE_SIZE_DEFAULT)
    annotation_probe_size = _env_int(
        "PYEUROPMC_MECFS_ANNOTATION_PROBE_SIZE", ANNOTATION_PROBE_SIZE_DEFAULT
    )

    # Keep the default aligned with the user requirement unless overridden intentionally.
    assert target_papers >= 100_000

    with SearchClient(rate_limit_delay=0.1) as search_client:
        corpus_metrics, sampled_pmcids = _collect_mecfs_corpus(
            client=search_client,
            query=MECFS_QUERY,
            target_papers=target_papers,
            page_size=page_size,
        )

    # If no results are available from Europe PMC for this query, treat as an external-data skip.
    if corpus_metrics.scanned_papers == 0:
        pytest.skip("No ME/CFS papers returned from Europe PMC for this run.")

    probe_metrics, first_annotation_payload = _probe_xml_and_annotations(
        sampled_pmcids,
        xml_probe_size=xml_probe_size,
        annotation_probe_size=annotation_probe_size,
    )

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

    report_path = tmp_path / "mecfs_kg_readiness_report.json"
    report_path.write_text(
        json.dumps(
            {
                "query": report.query,
                "corpus_metrics": asdict(report.corpus_metrics),
                "probe_metrics": asdict(report.probe_metrics),
                "enrichment_fields_present": report.enrichment_fields_present,
                "rdf_enrichment_present": report.rdf_enrichment_present,
                "capabilities": [asdict(c) for c in report.capabilities],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    # Core expectations for professional readiness
    assert corpus_metrics.scanned_papers >= min(corpus_metrics.effective_target, target_papers)
    assert corpus_metrics.open_access_papers >= 0
    assert corpus_metrics.papers_in_pmc >= 0
    assert corpus_metrics.papers_with_text_mined_terms >= 0

    # Availability checks requested in the prompt.
    assert probe_metrics.xml_probe_size >= 0
    assert probe_metrics.annotation_probe_size >= 0

    # Capability gate: all required capabilities should pass in a successful run.
    failed_capabilities = [c for c in capabilities if not c.passed]
    assert not failed_capabilities, (
        "KG readiness capabilities failed: "
        + ", ".join(f"{c.domain}:{c.capability}" for c in failed_capabilities)
        + f". Report: {report_path}"
    )
