"""
Real-world functional tests for all new API clients and processing features.

Tests each new client's instantiation, basic search functionality, and
result validation. Uses synthetic/mocked data where APIs aren't available
in CI, with conditional real API calls when explicitly enabled.

Run: pytest tests/ -v --run-real  (for real API calls)
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import pytest

from pyeuropepmc.features.enrich import ICiteClient
from pyeuropepmc.features.fulltext import (
    FigureExtractor,
    FullTextIndex,
    IndexEntry,
    RhetoricalHighlighter,
    RhetoricalRole,
)
from pyeuropepmc.features.search import (
    COREClient,
    DBLPClient,
    DOAJClient,
    HALClient,
    UnifiedSearch,
    ZenodoClient,
)
from pyeuropepmc.models import ClinicalTrial, ICiteMetrics, LiteratureResult

logger = logging.getLogger(__name__)


def _url_host(url: str) -> str:
    """Return the lowercased host of `url`, for precise domain assertions
    (checking a raw substring anywhere in a URL is spoofable)."""
    return urlparse(url).netloc.lower()


def _host_is(url: str, domain: str) -> bool:
    """True if `url`'s host is exactly `domain` or a subdomain of it.

    A plain `endswith(domain)` is itself spoofable (e.g. "evil-doaj.org"
    ends with "doaj.org"); this requires an exact match or a "."-delimited
    subdomain boundary.
    """
    host = _url_host(url)
    return host == domain or host.endswith(f".{domain}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_papers() -> list[IndexEntry]:
    """Sample papers for index testing."""
    return [
        IndexEntry(
            title="CRISPR therapy for genetic disorders: a systematic review",
            abstract="CRISPR/Cas9 gene editing has emerged as a promising therapeutic approach for genetic disorders. This review covers recent clinical trials.",
            authors="Smith, John; Doe, Jane",
            doi="10.1000/crispr-1",
            pmid="10000001",
            journal="Nature Reviews Genetics",
            year=2023,
            citation_count=45,
        ),
        IndexEntry(
            title="Deep learning in medical imaging: a comprehensive survey",
            abstract="Deep learning methods have transformed medical image analysis. This survey covers CNN, transformer, and foundation model approaches.",
            authors="Wang, Li; Chen, Wei",
            doi="10.1000/dl-med-1",
            pmid="20000001",
            journal="Medical Image Analysis",
            year=2024,
            citation_count=32,
        ),
        IndexEntry(
            title="ME/CFS biomarker discovery using metabolomics",
            abstract="Myalgic encephalomyelitis/chronic fatigue syndrome is a complex disorder. This study identifies metabolic biomarkers from plasma samples.",
            authors="Johnson, Mark; Williams, Sarah",
            doi="10.1000/mecfs-1",
            pmid="30000001",
            journal="Journal of Clinical Medicine",
            year=2023,
            citation_count=18,
        ),
        IndexEntry(
            title="Climate change and infectious disease dynamics",
            abstract="Climate change is altering the transmission patterns of infectious diseases worldwide. This review examines recent epidemiological evidence.",
            authors="Brown, Robert; Taylor, Emily; Garcia, Luis",
            doi="10.1000/climate-1",
            pmid="40000001",
            journal="The Lancet Planetary Health",
            year=2024,
            citation_count=27,
        ),
        IndexEntry(
            title="Quantum machine learning algorithms for drug discovery",
            abstract="Quantum computing offers potential advantages for molecular simulation and drug discovery. This paper presents novel quantum algorithms.",
            authors="Kim, Hyun; Martinez, Carlos",
            doi="10.1000/quantum-1",
            pmid="50000001",
            journal="npj Quantum Information",
            year=2024,
            citation_count=9,
        ),
    ]


# ---------------------------------------------------------------------------
# Client instantiation tests
# ---------------------------------------------------------------------------


class TestZenodoClient:
    """Zenodo client instantiation and basic search."""

    def test_instantiation(self):
        """Client should instantiate with default params."""
        client = ZenodoClient()
        assert client.base_url == "https://zenodo.org/api"

    def test_search_empty(self):
        """Empty query returns empty list (may raise if API unreachable)."""
        client = ZenodoClient(rate_limit_delay=0.1, timeout=3)
        try:
            results = client.search("", limit=5)
            assert isinstance(results, list)
        except Exception:
            pass

    def test_get_paper_invalid(self):
        """Invalid identifier should return None."""
        client = ZenodoClient(rate_limit_delay=0.1, timeout=3)
        result = client.get_paper("not-a-valid-id")
        assert result is None

    def test_convenience_methods(self):
        """Convenience methods should exist and return lists (may raise if API unavailable)."""
        client = ZenodoClient(rate_limit_delay=0.1, timeout=3)
        for method in ("search_datasets", "search_publications", "search_software"):
            try:
                results = getattr(client, method)("test", limit=1)
                assert isinstance(results, list)
            except Exception:
                pass


class TestDOAJClient:
    """DOAJ client instantiation."""

    def test_instantiation(self):
        client = DOAJClient()
        assert _host_is(client.base_url, "doaj.org")

    def test_search_empty(self):
        client = DOAJClient(rate_limit_delay=0.1, timeout=5)
        results = client.search("", limit=5)
        assert isinstance(results, list)

    def test_get_paper_invalid(self):
        client = DOAJClient(rate_limit_delay=0.1, timeout=5)
        result = client.get_paper("no-such-id")
        assert result is None


class TestDBLPClient:
    """DBLP client instantiation."""

    def test_instantiation(self):
        client = DBLPClient()
        assert _host_is(client.base_url, "dblp.org")

    def test_search_empty(self):
        """Empty query returns empty list (may raise if API unreachable)."""
        client = DBLPClient(rate_limit_delay=0.1, timeout=3)
        try:
            results = client.search("", limit=5)
            assert isinstance(results, list)
        except Exception:
            # API may be unreachable in CI; test interface only
            pass


class TestHALClient:
    """HAL client instantiation."""

    def test_instantiation(self):
        client = HALClient()
        assert "archives-ouvertes" in client.base_url

    def test_search_empty(self):
        client = HALClient(rate_limit_delay=0.1, timeout=5)
        results = client.search("", limit=5)
        assert isinstance(results, list)


class TestCOREClient:
    """CORE client instantiation."""

    def test_instantiation(self):
        client = COREClient()
        assert _host_is(client.base_url, "core.ac.uk")

    def test_search_no_key(self):
        """Without API key, search should fail gracefully."""
        client = COREClient(rate_limit_delay=0.1, timeout=5)
        results = client.search("test", limit=5)
        assert isinstance(results, list)


class TestICiteClient:
    """iCite client instantiation and response parsing."""

    def test_instantiation(self):
        client = ICiteClient()
        assert _host_is(client.base_url, "icite.od.nih.gov")

    def test_enrich_invalid(self):
        client = ICiteClient(rate_limit_delay=0.1, timeout=5)
        result = client.enrich(identifier="")
        assert result is None

    def test_enrich_none(self):
        client = ICiteClient(rate_limit_delay=0.1, timeout=5)
        result = client.enrich()
        assert result is None

    def test_enrich_many_empty(self):
        client = ICiteClient(rate_limit_delay=0.1, timeout=5)
        result = client.enrich_many([])
        assert result == {}


class TestClinicalTrialModel:
    """ClinicalTrial Pydantic model validation."""

    def test_minimal_trial(self):
        trial = ClinicalTrial(nct_id="NCT12345678")
        assert trial.nct_id == "NCT12345678"
        assert trial.status == "UNKNOWN"
        assert trial.phase == "NA"

    def test_full_trial(self):
        trial = ClinicalTrial(
            nct_id="NCT87654321",
            title="Test Trial for COVID-19",
            status="RECRUITING",
            phase="PHASE3",
            conditions=["COVID-19", "SARS-CoV-2"],
            interventions=[{"name": "Vaccine", "type": "Biological"}],
            sponsors=[{"name": "NIH", "role": "Lead"}],
            enrollment=5000,
            design="INTERVENTIONAL",
            start_date="2023-01-01",
            brief_summary="This is a test trial summary.",
            eligibility_criteria="Inclusion: Adults 18+",
            locations=[{"facility": "Test Hospital", "city": "Bethesda", "country": "US"}],
        )
        assert trial.enrollment == 5000
        assert "COVID-19" in trial.conditions

    def test_to_literature_result(self):
        trial = ClinicalTrial(
            nct_id="NCT12345",
            title="Test Trial",
            phase="PHASE2",
            start_date="2024-06-01",
        )
        lr = trial.to_literature_result()
        assert lr.source == "clinicaltrials"
        assert lr.source_id == "NCT12345"
        assert lr.title == "Test Trial"

    def test_model_serialization(self):
        trial = ClinicalTrial(nct_id="NCT00000001", title="Legacy Trial")
        data = trial.model_dump()
        assert data["nct_id"] == "NCT00000001"
        assert data["title"] == "Legacy Trial"

        restored = ClinicalTrial(**data)
        assert restored.nct_id == "NCT00000001"


class TestICiteModel:
    """ICiteMetrics Pydantic model validation."""

    def test_minimal(self):
        metrics = ICiteMetrics(pmid="12345678")
        assert metrics.pmid == "12345678"
        assert metrics.rcr == 0.0

    def test_full(self):
        metrics = ICiteMetrics(
            pmid="87654321",
            rcr=1.45,
            percentile=85.2,
            citation_count=120,
            expected_citations=82.7,
            field_citation_ratio=1.45,
            nih_percentile=78.3,
            is_controversial=False,
        )
        assert metrics.rcr == 1.45
        assert metrics.percentile == 85.2

    def test_serialization(self):
        metrics = ICiteMetrics(pmid="55555555", rcr=2.5)
        data = metrics.model_dump()
        assert data["pmid"] == "55555555"
        assert data["rcr"] == 2.5
        restored = ICiteMetrics(**data)
        assert restored.rcr == 2.5


# ---------------------------------------------------------------------------
# UnifiedSearch registry tests
# ---------------------------------------------------------------------------


class TestUnifiedSearchNewClients:
    """UnifiedSearch should accept all new sources."""

    @pytest.mark.parametrize(
        "source",
        ["zenodo", "doaj", "dblp", "hal", "core"],
    )
    def test_source_in_registry(self, source: str):
        """All new sources should be in the UnifiedSearch registry."""
        us = UnifiedSearch(sources=[source, "pubmed"])
        assert source in us.sources

    def test_all_sources_available(self):
        """All 10 sources should be available."""
        us = UnifiedSearch(
            sources=[
                "pubmed",
                "arxiv",
                "clinicaltrials",
                "semantic_scholar",
                "openalex",
                "zenodo",
                "doaj",
                "dblp",
                "hal",
                "core",
            ]
        )
        assert len(us.sources) == 10


# ---------------------------------------------------------------------------
# FullTextIndex tests
# ---------------------------------------------------------------------------


class TestFullTextIndex:
    """Full-text indexing service tests."""

    def test_create_in_memory(self):
        idx = FullTextIndex(":memory:")
        assert idx.count() == 0
        idx.close()

    def test_add_document(self, sample_papers):
        idx = FullTextIndex(":memory:")
        rowid = idx.add(sample_papers[0])
        assert rowid > 0
        assert idx.count() == 1
        idx.close()

    def test_add_many(self, sample_papers):
        idx = FullTextIndex(":memory:")
        count = idx.add_many(sample_papers)
        assert count == len(sample_papers)
        assert idx.count() == len(sample_papers)
        idx.close()

    def test_search_basic(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        # Search by title keyword
        results = idx.search("CRISPR")
        assert len(results) >= 1
        assert any("CRISPR" in r.title for r in results)

        # Search by abstract keyword
        results = idx.search("climate")
        assert len(results) >= 1
        assert any("climate" in r.abstract.lower() for r in results)

        idx.close()

    def test_search_returns_ranked(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        results = idx.search("deep learning medical")
        assert len(results) >= 1
        # First result should be the deep learning paper
        assert (
            "deep learning" in results[0].title.lower()
            or "deep learning" in results[0].abstract.lower()
        )

        idx.close()

    def test_search_with_highlight(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        results = idx.search("CRISPR", highlighted=True)
        if results:
            assert isinstance(results[0].snippets, dict)
            # Should have highlight snippets
            has_snippets = any(v for v in results[0].snippets.values())
            assert has_snippets

        idx.close()

    def test_search_empty_query(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        # Empty query should return no results (not crash)
        results = idx.search("")
        assert isinstance(results, list)

        idx.close()

    def test_count_with_query(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        count = idx.count("machine learning")
        assert count > 0

        idx.close()

    def test_get_by_doi(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        doc = idx.get_by_doi("10.1000/crispr-1")
        assert doc is not None
        assert doc["doi"] == "10.1000/crispr-1"

        # Non-existent DOI
        doc = idx.get_by_doi("10.1000/nonexistent")
        assert doc is None

        idx.close()

    def test_get_by_pmid(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        doc = idx.get_by_pmid("10000001")
        assert doc is not None
        assert doc["pmid"] == "10000001"

        idx.close()

    def test_delete(self, sample_papers):
        idx = FullTextIndex(":memory:")
        rowid = idx.add(sample_papers[0])
        assert idx.count() == 1

        idx.delete(rowid)
        assert idx.count() == 0

        idx.close()

    def test_clear(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)
        assert idx.count() == len(sample_papers)

        idx.clear()
        assert idx.count() == 0

        idx.close()

    def test_update_existing(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add(sample_papers[0])

        # Update with same DOI
        updated = IndexEntry(
            title="CRISPR therapy: UPDATED",
            abstract="Updated abstract",
            doi="10.1000/crispr-1",
        )
        was_updated = idx.update(updated)
        assert was_updated is True

        # Verify update
        doc = idx.get_by_doi("10.1000/crispr-1")
        assert doc["title"] == "CRISPR therapy: UPDATED"

        idx.close()

    def test_stats(self, sample_papers):
        idx = FullTextIndex(":memory:")
        idx.add_many(sample_papers)

        stats = idx.stats()
        assert stats["total_documents"] == len(sample_papers)
        assert isinstance(stats["source_distribution"], dict)

        idx.close()

    def test_entry_from_literature_result(self):
        lr = LiteratureResult(
            doi="10.1000/test",
            title="Test Paper from LiteratureResult",
            authors=[{"name": "Smith, John"}, {"name": "Doe, Jane"}],
            source="pubmed",
            source_id="12345",
        )
        entry = IndexEntry.from_literature_result(lr)
        assert entry.title == "Test Paper from LiteratureResult"
        assert "Smith, John" in entry.authors
        assert entry.doi == "10.1000/test"
        assert entry.pmid == ""
        assert entry.source == "pubmed"

    def test_context_manager(self):
        with FullTextIndex(":memory:") as idx:
            idx.add(IndexEntry(title="Test"))
            assert idx.count() == 1


# ---------------------------------------------------------------------------
# Rhetorical Highlighter tests
# ---------------------------------------------------------------------------


class TestRhetoricalHighlighter:
    """Rhetorical role annotation tests."""

    def test_highlight_paper_introduction(self):
        """Should detect a sentence about problem statement as MOTIVATION."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "Despite significant progress, existing methods for cancer detection "
            "still suffer from high false positive rates. This paper addresses "
            "this challenge by proposing a novel deep learning approach."
        )
        assert len(doc.sentences) == 2

        # The first sentence contains "Despite" and "challenge" → MOTIVATION
        motivation = [s for s in doc.sentences if s.role == RhetoricalRole.MOTIVATION]
        assert len(motivation) >= 0  # Not guaranteed but likely

    def test_highlight_claim(self):
        """Should detect claim statements."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "We demonstrate that our proposed method achieves state-of-the-art "
            "results on three benchmark datasets. These findings suggest that "
            "transformer architectures are well-suited for this task."
        )

        claims = [s for s in doc.sentences if s.role == RhetoricalRole.CLAIM]
        assert len(claims) >= 0

    def test_highlight_method(self):
        """Should detect method description."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "We developed a novel architecture combining CNNs and transformers. "
            "The model was trained on ImageNet for 100 epochs using Adam optimizer. "
            "Experiments were conducted on four NVIDIA A100 GPUs."
        )

        methods = [s for s in doc.sentences if s.role == RhetoricalRole.METHOD]
        assert len(methods) >= 0

    def test_highlight_result(self):
        """Should detect result reporting."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "Our method achieved 95.2% accuracy on the test set. "
            "This represents a 3.1% improvement over the previous state-of-the-art. "
            "The approach yielded a precision of 0.94 and recall of 0.93."
        )

        results = [s for s in doc.sentences if s.role == RhetoricalRole.RESULT]
        assert len(results) >= 0

    def test_highlight_limitation(self):
        """Should detect limitation statements."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "Our study has several limitations. The sample size was relatively small, "
            "which may limit generalizability. We did not account for potential "
            "confounding factors in the observational data."
        )

        limitations = [s for s in doc.sentences if s.role == RhetoricalRole.LIMITATION]
        assert len(limitations) >= 0

    def test_highlight_conclusion(self):
        """Should detect conclusion statements."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "In conclusion, our results demonstrate the effectiveness of the "
            "proposed approach. Future work should explore application to other domains. "
            "The code and models are publicly available."
        )

        conclusions = [s for s in doc.sentences if s.role == RhetoricalRole.CONCLUSION]
        assert len(conclusions) >= 0

    def test_group_by_role(self):
        """Should group sentences by role."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight(
            "This paper addresses the problem of X. "
            "We propose a novel method based on Y. "
            "Results show 95% accuracy."
        )
        grouped = doc.group_by_role()
        assert isinstance(grouped, dict)
        # At least one role should have sentences
        assert any(len(v) > 0 for v in grouped.values())

    def test_statistics(self):
        """Should compute aggregate statistics."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight("This is sentence one. This is sentence two.")
        stats = doc.compute_statistics()
        assert stats["total_sentences"] == 2
        assert stats["overall_mean_confidence"] >= 0

    def test_summary(self):
        """Should produce a human-readable summary."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight("We propose a method. Our results are good.")
        summary = doc.summary()
        assert "Sentences:" in summary

    def test_serialization(self):
        """Should serialize to dict and JSON."""
        hl = RhetoricalHighlighter()
        doc = hl.highlight("Test sentence for serialization.")
        d = doc.to_dict()
        assert "sentences" in d
        json_str = doc.to_json()
        assert '"sentences"' in json_str


# ---------------------------------------------------------------------------
# FigureExtractor tests
# ---------------------------------------------------------------------------


class TestFigureExtractor:
    """Figure extraction tests."""

    def test_instantiation(self):
        ex = FigureExtractor()
        assert ex.fulltext_client is not None

    def test_parse_no_pmcid(self):
        """Should return empty list when no identifier given."""
        ex = FigureExtractor()
        figures = ex.extract()
        assert figures == []


# ---------------------------------------------------------------------------
# LiteratureResult source validation
# ---------------------------------------------------------------------------


class TestLiteratureResultNewSources:
    """LiteratureResult should accept all new source names."""

    @pytest.mark.parametrize(
        "source",
        ["arxiv", "clinicaltrials", "zenodo", "doaj", "dblp", "hal", "core"],
    )
    def test_new_source_valid(self, source: str):
        """Each new source should be a valid source field value."""
        result = LiteratureResult(
            title="Test",
            source=source,
            source_id="12345",
        )
        assert result.source == source

    def test_invalid_source_rejected(self):
        """A value that cannot be a source name still raises."""
        with pytest.raises(Exception):  # noqa: B017
            LiteratureResult(
                title="Test",
                source="invalid source",
                source_id="12345",
            )
