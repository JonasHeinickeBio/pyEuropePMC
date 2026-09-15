"""Unit tests for CORD-19-inspired deduplication features.

Covers:
- Multi-identifier deduplication (union-find over doi/pmid/pmcid/arxiv/mag/who)
- Strict conflict detection (shared id + conflicting id -> separate groups)
- Canonical metadata selection (license permissiveness + document availability)
- Non-paper entry filtering (TOC/index/front-matter)
- Deterministic group IDs (CORD UID analog)
- MergeReport.metadata field
"""

import pytest

from pyeuropepmc.features.enrich.merger import (
    DedupConfig,
    LiteratureMerger,
    MatchLevel,
    MergeReport,
    deduplicate_by_identifier,
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
# MergeReport.metadata (latent bug fix)
# ===========================================================================

class TestMergeReportMetadata:
    def test_metadata_default_factory(self):
        """MergeReport.metadata should exist by default (fixes unified_search bug)."""
        report = MergeReport()
        assert report.metadata == {}
        report.metadata["source_times"] = {"pubmed": 0.1}
        assert report.metadata["source_times"] == {"pubmed": 0.1}

    def test_merge_results_populates_metadata(self):
        """merge_results should record identifier group stats in metadata."""
        papers = [
            make_paper(pmid="1", doi="10.1234/abc"),
            make_paper(pmid="1", doi="10.1234/abc"),
        ]
        merger = LiteratureMerger()
        _, report = merger.merge_results([papers])
        assert isinstance(report.metadata, dict)
        assert "identifier_groups" in report.metadata


# ===========================================================================
# Identifier deduplication (CORD-19 multi-identifier overlap)
# ===========================================================================

class TestIdentifierDedup:
    def test_shared_doi(self):
        papers = [
            make_paper(pmid="1", doi="10.1000/xyz"),
            make_paper(pmid="2", doi="10.1000/xyz"),
        ]
        assert deduplicate_by_identifier(papers) == [[0, 1]]

    def test_shared_pmcid(self):
        papers = [
            make_paper(pmid="1", pmcid="PMC100"),
            make_paper(pmid="2", pmcid="PMC100"),
        ]
        assert deduplicate_by_identifier(papers) == [[0, 1]]

    def test_shared_arxiv(self):
        papers = [
            make_paper(pmid="1", arxiv_id="arXiv:2101.00001"),
            make_paper(pmid="2", arxiv_id="2101.00001"),
        ]
        assert deduplicate_by_identifier(papers) == [[0, 1]]

    def test_shared_mag_and_who(self):
        papers = [
            make_paper(pmid="1", mag_id="MAG42"),
            make_paper(pmid="2", mag_id="MAG42"),
            make_paper(pmid="3", who_covidence_id="WHOCVD-9"),
            make_paper(pmid="4", covidence_id="WHOCVD-9"),
        ]
        groups = deduplicate_by_identifier(papers)
        assert [0, 1] in groups
        assert [2, 3] in groups

    def test_no_shared_identifiers(self):
        papers = [
            make_paper(pmid="1", doi="10.1000/one"),
            make_paper(pmid="2", doi="10.1000/two"),
        ]
        assert deduplicate_by_identifier(papers) == [[0], [1]]

    def test_external_ids_subdict(self):
        papers = [
            {"pmid": "1", "external_ids": {"DOI": "10.1000/ext"}},
            {"pmid": "2", "external_ids": {"doi": "10.1000/ext"}},
        ]
        assert deduplicate_by_identifier(papers) == [[0, 1]]

    def test_transitive_grouping(self):
        """A--B via pmid, B--C via doi should connect A--C (union-find)."""
        papers = [
            make_paper(pmid="1", doi="10.1000/a"),
            make_paper(pmid="1", doi="10.1000/b"),  # shares pmid with A
            make_paper(pmid="2", doi="10.1000/b"),  # shares doi with B
        ]
        assert deduplicate_by_identifier(papers) == [[0, 1, 2]]

    def test_invalid_doi_ignored(self):
        """An unresolvable DOI should not be used as a grouping key."""
        papers = [
            make_paper(pmid="1", doi="10.1/a"),
            make_paper(pmid="2", doi="10.1/a"),
        ]
        assert deduplicate_by_identifier(papers) == [[0], [1]]


# ===========================================================================
# Strict conflict detection (CORD-19 rule)
# ===========================================================================

class TestStrictConflicts:
    def test_conflicting_secondary_id_splits_group(self):
        """Same DOI but different PMCID -> separate groups under strict mode."""
        papers = [
            make_paper(pmid="1", doi="10.1000/xyz", pmcid="PMC100"),
            make_paper(pmid="2", doi="10.1000/xyz", pmcid="PMC200"),
        ]
        # Non-strict: merges on shared DOI
        assert deduplicate_by_identifier(papers) == [[0, 1]]
        # Strict: DOI shared but PMCID conflicts -> keep separate
        assert deduplicate_by_identifier(papers, strict_conflicts=True) == [[0], [1]]

    def test_identical_identifiers_merge_strict(self):
        """Papers with fully identical identifiers still merge in strict mode."""
        papers = [
            make_paper(pmid="1", doi="10.1000/xyz", pmcid="PMC100"),
            make_paper(pmid="1", doi="10.1000/xyz", pmcid="PMC100"),
        ]
        assert deduplicate_by_identifier(papers, strict_conflicts=True) == [[0, 1]]


# ===========================================================================
# Identifier deduplication pass in merge pipeline
# ===========================================================================

class TestIdentifierDedupPass:
    def test_pmcid_duplicate_merged(self):
        papers = [
            make_paper(pmid="1", title="Alpha paper", pmcid="PMC100"),
            make_paper(pmid="2", title="Alpha paper", pmcid="PMC100"),
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])
        assert len(results) == 1
        assert report.duplicates_removed == 1
        assert report.records[0].match_level == MatchLevel.PMCID_EXACT

    def test_arxiv_duplicate_merged(self):
        papers = [
            make_paper(pmid="1", title="Beta paper", arxiv_id="2101.00001"),
            make_paper(pmid="2", title="Beta paper", arxiv_id="2101.00001"),
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])
        assert len(results) == 1
        assert report.records[0].match_level == MatchLevel.ARXIV_EXACT

    def test_dedup_id_assigned(self):
        papers = [
            make_paper(pmid="1", doi="10.1000/cid", title="Same paper"),
            make_paper(pmid="2", doi="10.1000/cid", title="Same paper"),
        ]
        merger = LiteratureMerger()
        results, _ = merger.merge_results([papers])
        assert len(results) == 1
        assert results[0]["dedup_id"].startswith("CORD-")
        assert len(results[0]["dedup_id"]) == 21  # CORD- + 16 hex

    def test_dedup_id_deterministic(self):
        p1 = make_paper(pmid="1", doi="10.1000/det", title="Same paper")
        p2 = make_paper(pmid="2", doi="10.1000/det", title="Same paper")
        merger = LiteratureMerger()
        r1, _ = merger.merge_results([[p1, p2]])
        r2, _ = merger.merge_results([[p1, p2]])
        assert r1[0]["dedup_id"] == r2[0]["dedup_id"]

    def test_dedup_id_disabled(self):
        papers = [
            make_paper(pmid="1", doi="10.1000/nocid", title="Same paper"),
            make_paper(pmid="2", doi="10.1000/nocid", title="Same paper"),
        ]
        merger = LiteratureMerger(config=DedupConfig(persist_dedup_ids=False))
        results, _ = merger.merge_results([papers])
        assert "dedup_id" not in results[0]

    def test_grouping_disabled(self):
        """Without grouping, PMCID-only dups (distinct titles) are not caught."""
        papers = [
            make_paper(pmid="1", title="Gamma paper one", pmcid="PMC100"),
            make_paper(pmid="2", title="Gamma paper two", pmcid="PMC100"),
        ]
        merger = LiteratureMerger(config=DedupConfig(use_identifier_dedup=False))
        results, report = merger.merge_results([papers])
        # Without grouping, PMCID-only duplicates are not caught (no pmid/doi/title overlap)
        assert len(results) == 2
        assert report.duplicates_removed == 0


# ===========================================================================
# Canonical metadata selection (license + document availability)
# ===========================================================================

class TestCanonicalSelection:
    def test_oa_license_and_pmcid_wins_over_pubmed(self):
        """Crossref with open-access license + full text should be canonical."""
        source_a = [
            make_paper(
                pmid="1",
                doi="10.1000/oa",
                title="OA paper",
                source="pubmed",
            )
        ]
        source_b = [
            make_paper(
                pmid="1",
                doi="10.1000/oa",
                title="OA paper",
                source="crossref",
                license="CC-BY",
                pmcid="PMC100",
                fulltext_url="https://example.com/ft",
            )
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([source_a, source_b])
        assert len(results) == 1
        # Canonical should be the crossref copy (better license + document availability)
        assert results[0]["source"] == "crossref"
        assert results[0]["pmcid"] == "PMC100"
        assert report.records[0].match_level == MatchLevel.DOI_EXACT

    def test_prefer_open_access_disabled(self):
        """With prefer_open_access=False, pubmed source priority wins."""
        source_a = [
            make_paper(
                pmid="1",
                doi="10.1000/oa2",
                title="OA paper",
                source="pubmed",
            )
        ]
        source_b = [
            make_paper(
                pmid="1",
                doi="10.1000/oa2",
                title="OA paper",
                source="crossref",
                license="CC-BY",
                pmcid="PMC100",
                fulltext_url="https://example.com/ft",
            )
        ]
        merger = LiteratureMerger(config=DedupConfig(prefer_open_access=False))
        results, _ = merger.merge_results([source_a, source_b])
        assert len(results) == 1
        assert results[0]["source"] == "pubmed"


# ===========================================================================
# Non-paper entry filtering (CORD-19 group filtering)
# ===========================================================================

class TestNonPaperFiltering:
    @pytest.mark.parametrize(
        "title",
        [
            "Table of Contents",
            "Contents: Volume 12, Issue 3",
            "Editorial Board",
            "Instructions for Authors",
            "Information for Authors",
            "Journal Information",
            "Subject Index: 2023",
            "Cover Image",
            "Correction to: Some paper title",
        ],
    )
    def test_non_paper_titles_filtered(self, title):
        papers = [
            make_paper(pmid="1", title=title),
            make_paper(pmid="2", title="Real research paper on ME/CFS"),
        ]
        merger = LiteratureMerger()
        results, report = merger.merge_results([papers])
        assert len(results) == 1
        assert results[0]["title"] == "Real research paper on ME/CFS"
        assert report.duplicates_removed == 1
        assert report.records[0].match_level == MatchLevel.NON_PAPER

    def test_non_paper_filtering_disabled(self):
        papers = [
            make_paper(pmid="1", title="Table of Contents"),
            make_paper(pmid="2", title="Real paper"),
        ]
        merger = LiteratureMerger(config=DedupConfig(filter_non_papers=False))
        results, report = merger.merge_results([papers])
        assert len(results) == 2
        assert report.duplicates_removed == 0

    def test_real_papers_not_filtered(self):
        papers = [
            make_paper(pmid="1", title="Cognitive behavioural therapy for chronic fatigue syndrome"),
            make_paper(pmid="2", title="Gut microbiota composition in chronic fatigue syndrome"),
        ]
        merger = LiteratureMerger()
        results, _ = merger.merge_results([papers])
        assert len(results) == 2


# ===========================================================================
# Config defaults (existing behavior preserved)
# ===========================================================================

class TestConfigDefaults:
    def test_new_fields_default_on(self):
        cfg = DedupConfig()
        assert cfg.use_identifier_dedup is True
        assert cfg.strict_identifier_conflicts is False
        assert cfg.prefer_open_access is True
        assert cfg.filter_non_papers is True
        assert cfg.persist_dedup_ids is True
