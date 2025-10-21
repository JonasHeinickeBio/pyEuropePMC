"""
Tests for Europe PMC filtering utilities.
"""

import pytest

from pyeuropepmc.filters import filter_pmc_papers


@pytest.fixture
def sample_papers():
    """Sample papers for testing."""
    return [
        {
            "id": "12345",
            "source": "MED",
            "pmid": "12345678",
            "doi": "10.1234/test1",
            "title": "Cancer immunotherapy review",
            "pubYear": "2022",
            "pubType": ["Review", "Journal Article"],
            "isOpenAccess": "Y",
            "citedByCount": "50",
            "abstractText": "This paper reviews cancer immunotherapy approaches including checkpoint inhibitors.",
            "authorList": {
                "author": [
                    {"fullName": "Smith J", "lastName": "Smith"},
                    {"fullName": "Johnson A", "lastName": "Johnson"},
                ]
            },
            "keywordList": {
                "keyword": ["cancer", "immunotherapy", "checkpoint inhibitors"]
            },
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Neoplasms"},
                    {"descriptorName": "Immunotherapy"},
                ]
            },
        },
        {
            "id": "67890",
            "source": "PMC",
            "pmcid": "PMC67890",
            "doi": "10.5678/test2",
            "title": "Clinical trial of diabetes treatment",
            "pubYear": "2020",
            "pubType": "Clinical Trial",
            "isOpenAccess": "N",
            "citedByCount": "25",
            "abstractText": "A randomized clinical trial evaluating efficacy and safety of a new diabetes drug.",
            "authorList": {"author": [{"fullName": "Brown B"}]},
            "keywordList": {"keyword": ["diabetes", "clinical trial", "efficacy"]},
            "meshHeadingList": {
                "meshHeading": [{"descriptorName": "Diabetes Mellitus"}]
            },
        },
        {
            "id": "11111",
            "source": "MED",
            "pmid": "11111111",
            "title": "Old study from 2005",
            "pubYear": "2005",
            "pubType": "Journal Article",
            "isOpenAccess": "Y",
            "citedByCount": "5",
            "abstractText": "An older study with limited citations.",
            "authorList": {"author": []},
            "keywordList": {"keyword": []},
            "meshHeadingList": {"meshHeading": []},
        },
        {
            "id": "22222",
            "source": "MED",
            "pmid": "22222222",
            "title": "Recent systematic review",
            "pubYear": "2023",
            "pubType": "Systematic Review",
            "isOpenAccess": "Y",
            "citedByCount": "100",
            "abstractText": "Comprehensive systematic review of treatment efficacy and safety outcomes.",
            "authorList": {"author": [{"fullName": "Taylor T"}]},
            "keywordList": {
                "keyword": ["systematic review", "meta-analysis", "efficacy", "safety"]
            },
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Systematic Review"},
                    {"descriptorName": "Meta-Analysis"},
                ]
            },
        },
    ]


def test_filter_by_citations(sample_papers):
    """Test filtering by minimum citations."""
    # Filter for papers with at least 30 citations
    filtered = filter_pmc_papers(sample_papers, min_citations=30)

    assert len(filtered) == 2
    assert all(paper["citedByCount"] >= 30 for paper in filtered)
    assert filtered[0]["id"] == "12345"
    assert filtered[1]["id"] == "22222"


def test_filter_by_year(sample_papers):
    """Test filtering by publication year."""
    # Filter for papers from 2020 onwards (note: default open_access="Y" filters one out)
    filtered = filter_pmc_papers(sample_papers, min_pub_year=2020, open_access=None)

    assert len(filtered) == 3
    assert all(int(paper["pubYear"]) >= 2020 for paper in filtered)


def test_filter_by_type(sample_papers):
    """Test filtering by publication type."""
    # Filter for only reviews
    filtered = filter_pmc_papers(
        sample_papers, allowed_types=("Review", "Systematic Review")
    )

    assert len(filtered) == 2
    # Check that returned papers have review types
    for paper in filtered:
        pub_type = paper["pubType"]
        if isinstance(pub_type, list):
            assert any("Review" in pt for pt in pub_type)
        else:
            assert "Review" in pub_type


def test_filter_by_open_access(sample_papers):
    """Test filtering by open access status."""
    # Filter for open access papers (note: old 2005 paper filtered by default min_pub_year=2010)
    filtered = filter_pmc_papers(sample_papers, min_pub_year=2000, open_access="Y")

    assert len(filtered) == 3
    assert all(paper["isOpenAccess"] == "Y" for paper in filtered)

    # Filter for non-open access papers
    filtered_closed = filter_pmc_papers(sample_papers, open_access="N")
    assert len(filtered_closed) == 1
    assert filtered_closed[0]["id"] == "67890"


def test_filter_by_mesh_terms(sample_papers):
    """Test filtering by MeSH terms with partial matching."""
    # Filter for papers with "Neoplasms" MeSH term
    filtered = filter_pmc_papers(sample_papers, required_mesh={"neoplasms"})

    assert len(filtered) == 1
    assert filtered[0]["id"] == "12345"

    # Test partial matching (case-insensitive)
    filtered_partial = filter_pmc_papers(sample_papers, required_mesh={"immuno"})
    assert len(filtered_partial) == 1
    assert filtered_partial[0]["id"] == "12345"


def test_filter_by_keywords(sample_papers):
    """Test filtering by keywords with partial matching."""
    # Filter for papers with "immunotherapy" keyword
    filtered = filter_pmc_papers(sample_papers, required_keywords={"immunotherapy"})

    assert len(filtered) == 1
    assert filtered[0]["id"] == "12345"

    # Test partial matching (only systematic review has efficacy keyword since clinical trial not open access by default)
    filtered_partial = filter_pmc_papers(sample_papers, required_keywords={"efficacy"}, open_access=None)
    assert len(filtered_partial) == 2


def test_filter_by_abstract_terms(sample_papers):
    """Test filtering by abstract terms with partial matching."""
    # Filter for papers with "checkpoint" in abstract
    filtered = filter_pmc_papers(
        sample_papers, required_abstract_terms={"checkpoint"}
    )

    assert len(filtered) == 1
    assert filtered[0]["id"] == "12345"

    # Test multiple required terms (clinical trial not open access by default, so need to set None)
    filtered_multi = filter_pmc_papers(
        sample_papers, required_abstract_terms={"efficacy", "safety"}, open_access=None
    )
    assert len(filtered_multi) == 2
    assert filtered_multi[0]["id"] == "67890"
    assert filtered_multi[1]["id"] == "22222"


def test_combined_filters(sample_papers):
    """Test combining multiple filters."""
    # Combine: min citations, year, open access, and keywords
    filtered = filter_pmc_papers(
        sample_papers,
        min_citations=20,
        min_pub_year=2020,
        open_access="Y",
        required_keywords={"efficacy"},
    )

    assert len(filtered) == 1
    assert filtered[0]["id"] == "22222"


def test_metadata_extraction(sample_papers):
    """Test that filtered papers contain expected metadata."""
    filtered = filter_pmc_papers(sample_papers, min_citations=0)

    for paper in filtered:
        # Check all expected fields are present
        assert "title" in paper
        assert "authors" in paper
        assert "pubYear" in paper
        assert "pubType" in paper
        assert "isOpenAccess" in paper
        assert "citedByCount" in paper
        assert "keywords" in paper
        assert "meshHeadings" in paper
        assert "abstractText" in paper
        assert "id" in paper
        assert "source" in paper

        # Check types
        assert isinstance(paper["authors"], list)
        assert isinstance(paper["keywords"], list)
        assert isinstance(paper["meshHeadings"], list)
        assert isinstance(paper["citedByCount"], int)


def test_no_filters(sample_papers):
    """Test with no filters (should return all papers)."""
    filtered = filter_pmc_papers(sample_papers, min_citations=0, min_pub_year=2000, open_access=None)

    assert len(filtered) == 4


def test_empty_input():
    """Test with empty paper list."""
    filtered = filter_pmc_papers([])

    assert len(filtered) == 0


def test_missing_fields():
    """Test handling of papers with missing fields."""
    papers_with_missing = [
        {
            "id": "99999",
            "title": "Minimal paper",
            "citedByCount": "10",
            "isOpenAccess": "Y",  # Need this since default filter is open_access="Y"
            # Missing many other fields
        }
    ]

    filtered = filter_pmc_papers(papers_with_missing, min_citations=5, min_pub_year=2000)

    assert len(filtered) == 1
    assert filtered[0]["id"] == "99999"
    assert filtered[0]["authors"] == []
    assert filtered[0]["keywords"] == []
    assert filtered[0]["meshHeadings"] == []


def test_partial_mesh_matching_case_insensitive(sample_papers):
    """Test that MeSH matching is case-insensitive and partial."""
    # Use various casings
    filtered_lower = filter_pmc_papers(sample_papers, required_mesh={"neoplasm"})
    filtered_upper = filter_pmc_papers(sample_papers, required_mesh={"NEOPLASM"})
    filtered_mixed = filter_pmc_papers(sample_papers, required_mesh={"NeOpLaSm"})

    assert len(filtered_lower) == 1
    assert len(filtered_upper) == 1
    assert len(filtered_mixed) == 1
    assert filtered_lower[0]["id"] == filtered_upper[0]["id"] == filtered_mixed[0]["id"]


def test_partial_keyword_matching_case_insensitive(sample_papers):
    """Test that keyword matching is case-insensitive and partial."""
    # Use various casings for partial match
    filtered_lower = filter_pmc_papers(sample_papers, required_keywords={"immuno"})
    filtered_upper = filter_pmc_papers(sample_papers, required_keywords={"IMMUNO"})
    filtered_mixed = filter_pmc_papers(sample_papers, required_keywords={"ImmUno"})

    assert len(filtered_lower) == 1
    assert len(filtered_upper) == 1
    assert len(filtered_mixed) == 1


def test_partial_abstract_matching_case_insensitive(sample_papers):
    """Test that abstract matching is case-insensitive and partial."""
    # Use various casings
    filtered_lower = filter_pmc_papers(
        sample_papers, required_abstract_terms={"checkpoint"}
    )
    filtered_upper = filter_pmc_papers(
        sample_papers, required_abstract_terms={"CHECKPOINT"}
    )
    filtered_mixed = filter_pmc_papers(
        sample_papers, required_abstract_terms={"ChEcKpOiNt"}
    )

    assert len(filtered_lower) == 1
    assert len(filtered_upper) == 1
    assert len(filtered_mixed) == 1


def test_all_required_terms_must_match(sample_papers):
    """Test that ALL required terms must be present (AND logic)."""
    # This paper has "immunotherapy" but not "diabetes"
    filtered = filter_pmc_papers(
        sample_papers, required_keywords={"immunotherapy", "diabetes"}
    )

    # Should be empty because no single paper has both
    assert len(filtered) == 0

    # But if we only require one term, we should get results
    filtered_single = filter_pmc_papers(
        sample_papers, required_keywords={"immunotherapy"}
    )
    assert len(filtered_single) == 1
