"""Unit tests for literature deduplication engine."""

import pytest

from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    LiteratureMerger,
    MatchLevel,
    MergeReport,
    PaperMatcher,
    SOURCE_PRIORITY,
    deduplicate_by_doi,
    deduplicate_by_hash,
    deduplicate_by_pmid,
    deduplicate_by_title,
    compute_paper_hash,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# Helpers
# ===========================================================================

def make_paper(pmid=None, doi=None, title="Test", year=2024, source="pubmed", **kw):
    paper = {
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "publication_year": year,
        "source": source,
        **kw,
    }
    return paper


# ===========================================================================
# DedupConfig
# ===========================================================================

class TestDedupConfig:
    def test_defaults(self):
        cfg = DedupConfig()
        assert cfg.fuzzy_threshold == 0.90
        assert cfg.year_window == 2
        assert cfg.remove_retracted is True

    def test_threshold_clamping(self):
        cfg = DedupConfig(fuzzy_threshold=1.5)
        assert cfg.fuzzy_threshold == 1.0
        cfg2 = DedupConfig(fuzzy_threshold=-0.5)
        assert cfg2.fuzzy_threshold == 0.0


# ===========================================================================
# deduplicate_by_pmid
# ===========================================================================

class TestDeduplicateByPmid:
    def test_empty(self):
        assert deduplicate_by_pmid([]) == []

    def test_no_duplicates(self):
        papers = [make_paper(pmid="1"), make_paper(pmid="2")]
        result = deduplicate_by_pmid(papers)
        assert len(result) == 2

    def test_duplicates_removed(self):
        papers = [make_paper(pmid="1"), make_paper(pmid="1"), make_paper(pmid="2")]
        result = deduplicate_by_pmid(papers)
        assert len(result) == 2
        assert result[0]["pmid"] == "1"
        assert result[1]["pmid"] == "2"

    def test_papers_without_pmid_kept(self):
        papers = [make_paper(pmid=None), make_paper(pmid=None)]
        result = deduplicate_by_pmid(papers)
        assert len(result) == 2


# ===========================================================================
# deduplicate_by_doi
# ===========================================================================

class TestDeduplicateByDoi:
    def test_empty(self):
        assert deduplicate_by_doi([]) == []

    def test_no_duplicates(self):
        papers = [make_paper(doi="10.1234/one"), make_paper(doi="10.1234/two")]
        result = deduplicate_by_doi(papers)
        assert len(result) == 2

    def test_duplicates_removed(self):
        papers = [
            make_paper(doi="10.1234/ABC"),
            make_paper(doi="10.1234/abc"),  # normalized same
            make_paper(doi="10.1234/other"),
        ]
        result = deduplicate_by_doi(papers)
        assert len(result) == 2

    def test_papers_without_doi_kept(self):
        papers = [make_paper(doi=None), make_paper(doi=None)]
        result = deduplicate_by_doi(papers)
        assert len(result) == 2

    def test_invalid_doi_treated_as_no_doi(self):
        papers = [make_paper(doi="not-a-doi"), make_paper(doi="not-a-doi")]
        result = deduplicate_by_doi(papers)
        assert len(result) == 2  # both kept since neither has a valid DOI


# ===========================================================================
# deduplicate_by_title (fuzzy, year-grouped)
# ===========================================================================

class TestDeduplicateByTitle:
    def test_empty(self):
        assert deduplicate_by_title([]) == []

    def test_exact_duplicate(self):
        papers = [make_paper(title="Hello World"), make_paper(title="Hello World")]
        result = deduplicate_by_title(papers, similarity_threshold=0.95)
        assert len(result) == 1

    def test_similar_titles(self):
        papers = [
            make_paper(title="Effect of X on Y in Patients with Z"),
            make_paper(title="Effect of X on Y in Patients with Zzz"),
        ]
        result = deduplicate_by_title(papers, similarity_threshold=0.85)
        assert len(result) == 1

    def test_different_titles(self):
        papers = [make_paper(title="Cancer Research"), make_paper(title="Heart Disease")]
        result = deduplicate_by_title(papers)
        assert len(result) == 2

    def test_year_grouped_blocking(self):
        """Papers with years far apart should not match."""
        papers = [
            make_paper(title="CRISPR Therapy", year=2020),
            make_paper(title="CRISPR Therapy", year=2025),
        ]
        result = deduplicate_by_title(papers, year_window=2)
        # Years 2020 and 2025 are 5 years apart > window of 2
        assert len(result) == 2

    def test_year_grouped_matches(self):
        """Papers within the year window should match."""
        papers = [
            make_paper(title="CRISPR Therapy for Cancer", year=2020),
            make_paper(title="CRISPR Therapy for Cancer", year=2021),
        ]
        result = deduplicate_by_title(papers, year_window=2)
        assert len(result) == 1

    def test_papers_without_title_kept(self):
        papers = [make_paper(title=None), make_paper(title=None)]
        result = deduplicate_by_title(papers)
        assert len(result) == 2


# ===========================================================================
# compute_paper_hash
# ===========================================================================

class TestComputePaperHash:
    def test_with_doi(self):
        paper = make_paper(doi="10.1234/ABC")
        h = compute_paper_hash(paper)
        assert h is not None
        assert h.startswith("doi:")

    def test_without_doi(self):
        paper = make_paper(doi=None, title="Some Title", year=2024)
        h = compute_paper_hash(paper)
        assert h is not None
        assert h.startswith("title:")

    def test_insufficient_data(self):
        assert compute_paper_hash(make_paper(doi=None, title=None)) is None


# ===========================================================================
# PaperMatcher
# ===========================================================================

class TestPaperMatcher:
    def test_match_by_pmid(self):
        matcher = PaperMatcher()
        p1 = make_paper(pmid="1")
        p2 = make_paper(pmid="1")

        is_dup, level = matcher.match(p1)
        assert not is_dup
        assert level == MatchLevel.NO_MATCH

        is_dup, level = matcher.match(p2)
        assert is_dup
        assert level == MatchLevel.PMID_EXACT

    def test_match_by_doi(self):
        matcher = PaperMatcher()
        p1 = make_paper(doi="10.1234/ABC")
        p2 = make_paper(doi="10.1234/abc")

        matcher.match(p1)
        is_dup, level = matcher.match(p2)
        assert is_dup
        assert level == MatchLevel.DOI_EXACT

    def test_match_by_fuzzy_title(self):
        matcher = PaperMatcher(fuzzy_threshold=0.80)
        p1 = make_paper(title="Effect of X on Y in Patients")
        p2 = make_paper(title="Effect of X on Y in Patients with Z")

        matcher.match(p1)
        is_dup, level = matcher.match(p2)
        assert is_dup
        assert level == MatchLevel.FUZZY_TITLE

    def test_no_match(self):
        matcher = PaperMatcher()
        p1 = make_paper(title="Cancer")
        p2 = make_paper(title="Diabetes")

        matcher.match(p1)
        is_dup, level = matcher.match(p2)
        assert not is_dup
        assert level == MatchLevel.NO_MATCH

    def test_deduplicate_list(self):
        papers = [
            make_paper(pmid="1", title="A"),
            make_paper(pmid="2", title="B"),
            make_paper(pmid="1", title="A"),  # duplicate
            make_paper(pmid="3", title="C"),
        ]
        matcher = PaperMatcher()
        result = matcher.deduplicate(papers)
        assert len(result) == 3


# ===========================================================================
# LiteratureMerger (full pipeline)
# ===========================================================================

class TestLiteratureMerger:
    def test_empty_input(self):
        merger = LiteratureMerger()
        results, report = merger.merge_results([[], []])
        assert results == []
        assert report.total_input == 0

    def test_single_source_no_duplicates(self):
        papers = [
            make_paper(pmid="1", doi="10.1/a", title="Alpha"),
            make_paper(pmid="2", doi="10.1/b", title="Beta"),
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])
        assert len(results) == 2
        assert report.total_input == 2

    def test_doi_duplicates_cross_source(self):
        source_a = [make_paper(pmid="1", doi="10.1234/abc", title="Test")]
        source_b = [make_paper(pmid="2", doi="10.1234/abc", title="Test")]

        merger = LiteratureMerger()
        results, report = merger.merge_results([source_a, source_b])

        assert len(results) == 1  # deduped by DOI
        assert report.duplicates_removed >= 1

    def test_pmid_duplicates(self):
        papers = [
            make_paper(pmid="1", doi="10.1/a", title="A"),
            make_paper(pmid="1", doi="10.1/b", title="B"),  # same PMID, different DOI
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])

        assert len(results) == 1
        assert report.duplicates_removed >= 1

    def test_fuzzy_title_duplicates(self):
        papers = [
            make_paper(pmid="1", title="CRISPR Therapy for Cancer in Mice"),
            make_paper(pmid="2", title="CRISPR Therapy for Cancer in Mice Models"),
        ]
        merger = LiteratureMerger(DedupConfig(fuzzy_threshold=0.80))
        results, report = merger.merge_results([papers])

        assert len(results) == 1
        assert report.duplicates_removed >= 1

    def test_year_grouped_blocking(self):
        """Papers with same title but far years should not be deduped."""
        papers = [
            make_paper(pmid="1", title="CRISPR Therapy", year=2020),
            make_paper(pmid="2", title="CRISPR Therapy", year=2028),
        ]
        merger = LiteratureMerger(DedupConfig(year_window=2))
        results, report = merger.merge_results([papers])

        # Year window of 2: 2020 vs 2028 is 8 years apart > 2
        assert len(results) == 2  # not deduped

    def test_retracted_paper_removal(self):
        papers = [
            make_paper(pmid="1", title="Good paper"),
            make_paper(pmid="2", title="Retracted: Bad paper"),
        ]
        merger = LiteratureMerger(DedupConfig(remove_retracted=True))
        results, report = merger.merge_results([papers])

        assert len(results) == 1
        assert results[0]["pmid"] == "1"

    def test_retracted_removal_disabled(self):
        papers = [
            make_paper(pmid="1", title="Good paper"),
            make_paper(pmid="2", title="Retracted: Bad paper"),
        ]
        merger = LiteratureMerger(DedupConfig(remove_retracted=False))
        results, report = merger.merge_results([papers])

        assert len(results) == 2  # kept

    def test_merge_report_summary(self):
        papers = [
            make_paper(pmid="1", title="A"),
            make_paper(pmid="1", title="A"),
            make_paper(pmid="2", title="B"),
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])

        summary = report.summary()
        assert summary["total_input"] == 3
        assert summary["total_output"] == 2
        assert summary["duplicates_removed"] == 1
        assert "PMID_EXACT" in summary["by_match_level"]

    def test_merge_preserves_better_values(self):
        """Merge should prefer richer data from duplicate records."""
        source_a = [
            make_paper(
                pmid="1",
                doi="10.1/a",
                title="Short",
                source="pubmed",
            )
        ]
        source_b = [
            make_paper(
                pmid="1",
                doi="10.1/a",
                title="Longer Title with More Detail",
                source="openalex",
            )
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([source_a, source_b])

        assert len(results) == 1
        # Should prefer longer title (from FIELD_PREFERENCES)
        assert results[0]["title"] == "Longer Title with More Detail"

    def test_legacy_merge_method(self):
        """The merge() convenience method should work."""
        papers = [make_paper(pmid="1"), make_paper(pmid="1")]
        merger = LiteratureMerger()
        result = merger.merge(papers)
        assert len(result) == 1


# ===========================================================================
# SOURCE_PRIORITY
# ===========================================================================

class TestSourcePriority:
    def test_pubmed_highest(self):
        assert SOURCE_PRIORITY["pubmed"] == 100
        assert SOURCE_PRIORITY["pubmed"] > SOURCE_PRIORITY["crossref"]
        assert SOURCE_PRIORITY["pubmed"] > SOURCE_PRIORITY["semanticscholar"]
