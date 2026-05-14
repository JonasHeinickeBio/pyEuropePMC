# ME/CFS KG Best-Practice Capability Profile

This document defines professional capability expectations for building:
- Scientific literature knowledge graphs (KGs)
- Physiological/clinical KGs

from Europe PMC data with PyEuropePMC.

It is operationalized in the integration test:
- tests/search/functional/test_mecfs_large_scale_kg_readiness.py

## Literature-Grounded Requirements

### 1. FAIR and machine-actionable data
- Requirement: data should be findable, accessible, interoperable, reusable.
- Practical check: structured metadata, queryable OA status, standardized RDF output.
- Reference: Wilkinson et al., 2016, Scientific Data, doi:10.1038/sdata.2016.18.

### 2. Scalable corpus ingestion
- Requirement: retrieval should support high-volume literature (100,000 scale).
- Practical check: cursor-based pagination with bounded request budget.
- Reference context: Europe PMC large-scale indexed literature platform.

### 3. Full-text retrievability
- Requirement: KG extraction pipelines should use full text where available, not only metadata.
- Practical check: XML availability probe over sampled PMCIDs.
- Reference context: standard biomedical IE and relation extraction workflows.

### 4. Annotation availability and ontology linkage
- Requirement: entities should be represented as machine-readable annotations with external concept links.
- Practical check: annotation probe success and owl:sameAs presence in RDF.
- Reference context: OA/Web Annotation model + biomedical ontology alignment practice.

### 5. Context-preserving entity extraction
- Requirement: text mining should preserve local textual context for explainability and downstream relation extraction.
- Practical check: prefix/postfix/section in parsed entities and RDF predicates.
- Reference context: Open Annotation selectors and explainable IE pipelines.

### 6. Provenance and evidence traceability
- Requirement: every physiological assertion should be traceable back to source publication context.
- Practical check: article_id/article_uri in parsed entities and OA body/provenance in RDF.
- Reference context: evidence graph and biomedical curation standards.

## Physiological KG-Specific Expectations

### 1. Semantic normalization
- Requirement: biological/physiological mentions should be normalized into ontology-backed concepts.
- Practical check: entity category plus ontology links in RDF.

### 2. Evidence density from text mining signals
- Requirement: a usable physiology KG should have measurable annotation support.
- Practical check: hasTextMinedTerms ratio and non-empty annotation entity hits.

### 3. Interoperable graph serialization
- Requirement: graph must be exportable to standard linked-data formats.
- Practical check: RDF triples generated from annotation payloads.

## Recommended Execution

Run only when intentionally performing large network validation:

PYEUROPMC_RUN_LARGE_NETWORK_TESTS=1 \
PYEUROPMC_MECFS_TARGET_PAPERS=100000 \
PYEUROPMC_MECFS_PAGE_SIZE=1000 \
python -m pytest tests/search/functional/test_mecfs_large_scale_kg_readiness.py -q

Optional probe tuning:
- PYEUROPMC_MECFS_XML_PROBE_SIZE
- PYEUROPMC_MECFS_ANNOTATION_PROBE_SIZE

## Produced QA Artifact

The test writes a structured JSON report to pytest temporary output containing:
- Corpus metrics
- XML and annotation probe metrics
- Enrichment feature detection
- Capability pass/fail matrix for literature and physiological KG readiness
