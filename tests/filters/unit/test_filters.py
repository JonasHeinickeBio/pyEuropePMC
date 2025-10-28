"""
Tests for Europe PMC filtering utilities (unit copy).
This file is a direct copy of the top-level tests for localized unit testing.
"""


import pytest
from pyeuropepmc.filters import (
	filter_pmc_papers,
	filter_pmc_papers_or,
	_meets_type_criteria,
	_meets_access_criteria,
	_extract_authors,
	_extract_keywords,
	_extract_mesh_terms,
	_has_required_mesh,
	_has_required_keywords,
	_has_required_abstract_terms,
	_has_any_required_mesh,
	_has_any_required_keywords,
	_has_any_required_abstract_terms,
	_extract_paper_metadata,
)


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
				"pubTypeList": {"pubType": ["Review", "Journal Article"]},
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
				"pubTypeList": {"pubType": "Clinical Trial"},
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
				"pubTypeList": {"pubType": "Journal Article"},
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
				"pubTypeList": {"pubType": "Systematic Review"},
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


def test_combinedfilters(sample_papers):
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


def test_nofilters(sample_papers):
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


def test_or_logic_mesh_keywords_abstract(sample_papers):
	"""Test AND-across-filters, OR-within-each filter logic for filter_pmc_papers_or."""
	# Only one paper has "immunotherapy" (id 12345), one has "diabetes" (id 67890)
	filtered = filter_pmc_papers_or(
		sample_papers, required_keywords={"immunotherapy", "diabetes"}, open_access=None
	)
	# Should return both papers, since only keywords filter is provided (OR within set)
	ids = {p["id"] for p in filtered}
	assert "12345" in ids
	assert "67890" in ids
	assert len(filtered) == 2

	# AND logic across filters: must match at least one in each provided filter
	filtered_and = filter_pmc_papers_or(
		sample_papers,
		required_keywords={"immunotherapy", "diabetes"},
		required_mesh={"neoplasms"},
		open_access=None,
	)
	# Only paper 12345 has both a required keyword and required mesh
	ids_and = {p["id"] for p in filtered_and}
	assert ids_and == {"12345"}

	# OR logic for MeSH terms only
	filtered_mesh = filter_pmc_papers_or(
		sample_papers, required_mesh={"neoplasms", "diabetes"}, open_access=None
	)
	mesh_ids = {p["id"] for p in filtered_mesh}
	assert "12345" in mesh_ids
	assert "67890" in mesh_ids
	assert len(filtered_mesh) == 2

	# OR logic for abstract terms only
	filtered_abs = filter_pmc_papers_or(
		sample_papers, required_abstract_terms={"checkpoint", "efficacy"}, open_access=None
	)
	abs_ids = {p["id"] for p in filtered_abs}
	assert "12345" in abs_ids
	assert "67890" in abs_ids
	assert "22222" in abs_ids
	assert len(filtered_abs) == 3

	# AND logic: must match at least one in each of keywords and abstract terms
	filtered_and2 = filter_pmc_papers_or(
		sample_papers,
		required_keywords={"immunotherapy", "diabetes"},
		required_abstract_terms={"checkpoint"},
		open_access=None,
	)
	# Only paper 12345 matches both
	ids_and2 = {p["id"] for p in filtered_and2}
	assert ids_and2 == {"12345"}


def test__has_any_required_mesh():
	paper = {"meshHeadingList": {"meshHeading": ["foo", {"descriptorName": "bar"}]}}
	assert _has_any_required_mesh(paper, {"foo"})
	assert _has_any_required_mesh(paper, {"bar"})
	assert _has_any_required_mesh(paper, {"ba"})
	assert _has_any_required_mesh(paper, {"foo", "baz"})
	assert not _has_any_required_mesh(paper, {"baz"})


def test__has_any_required_keywords():
	paper = {"keywordList": {"keyword": ["foo", {"keyword": "bar"}]}}
	assert _has_any_required_keywords(paper, {"foo"})
	assert _has_any_required_keywords(paper, {"bar"})
	assert _has_any_required_keywords(paper, {"ba"})
	assert _has_any_required_keywords(paper, {"foo", "baz"})
	assert not _has_any_required_keywords(paper, {"baz"})


def test__has_any_required_abstract_terms():
	paper = {"abstractText": "foo bar baz"}
	assert _has_any_required_abstract_terms(paper, {"foo"})
	assert _has_any_required_abstract_terms(paper, {"bar"})
	assert _has_any_required_abstract_terms(paper, {"baz"})
	assert _has_any_required_abstract_terms(paper, {"foo", "qux"})
	assert not _has_any_required_abstract_terms(paper, {"qux"})


def test__meets_type_criteria_various_types():
	# allowed_types empty/None disables filter
	assert _meets_type_criteria({}, ()) is True
	# Do not pass None (not allowed by type signature)
	# pubType missing
	assert _meets_type_criteria({}, ("A",)) is True
	# pubTypeList as string
	assert _meets_type_criteria({"pubTypeList": {"pubType": "Review"}}, ("Review",)) is True
	assert _meets_type_criteria({"pubTypeList": {"pubType": "Other"}}, ("Review",)) is False
	# pubTypeList as list
	assert _meets_type_criteria({"pubTypeList": {"pubType": ["Review", "Other"]}}, ("Review",)) is True
	assert _meets_type_criteria({"pubTypeList": {"pubType": ["Other"]}}, ("Review",)) is False
	# pubTypeList as int/unknown type
	assert _meets_type_criteria({"pubTypeList": {"pubType": 123}}, ("Review",)) is False


def test__meets_access_criteria_various():
	# open_access None disables filter
	assert _meets_access_criteria({}, None) is True
	# isOpenAccess missing
	assert _meets_access_criteria({}, "Y") is False
	# isOpenAccess matches
	assert _meets_access_criteria({"isOpenAccess": "Y"}, "Y") is True
	assert _meets_access_criteria({"isOpenAccess": "N"}, "Y") is False
	# isOpenAccess as bool (should not be used, but test for robustness)
	# The function expects str|None, so skip this test for type safety


def test__extract_authors_various():
	# No authorList
	assert _extract_authors({}) == []
	# Empty author list
	assert _extract_authors({"authorList": {"author": []}}) == []
	# Dict with fullName
	paper = {"authorList": {"author": [{"fullName": "A B"}, {"lastName": "C"}]}}
	assert _extract_authors(paper) == ["A B", "C"]
	# String author
	paper = {"authorList": {"author": ["D E"]}}
	assert _extract_authors(paper) == ["D E"]


def test__extract_keywords_various():
	# No keywordList
	assert _extract_keywords({}) == []
	# Empty keyword list
	assert _extract_keywords({"keywordList": {"keyword": []}}) == []
	# String keyword
	paper = {"keywordList": {"keyword": ["foo"]}}
	assert _extract_keywords(paper) == ["foo"]
	# Dict keyword with various keys
	paper = {"keywordList": {"keyword": [{"keyword": "bar"}, {"text": "baz"}, {"value": "qux"}]}}
	assert _extract_keywords(paper) == ["bar", "baz", "qux"]


def test__extract_mesh_terms_various():
	# No meshHeadingList
	assert _extract_mesh_terms({}) == []
	# Empty meshHeading list
	assert _extract_mesh_terms({"meshHeadingList": {"meshHeading": []}}) == []
	# Dict meshHeading
	paper = {"meshHeadingList": {"meshHeading": [{"descriptorName": "foo"}]}}
	assert _extract_mesh_terms(paper) == ["foo"]
	# String meshHeading
	paper = {"meshHeadingList": {"meshHeading": ["bar"]}}
	assert _extract_mesh_terms(paper) == ["bar"]


def test__has_required_mesh_edge_cases():
	# No meshHeadingList
	assert not _has_required_mesh({}, {"foo"})
	# meshHeading as string
	paper = {"meshHeadingList": {"meshHeading": ["foo"]}}
	assert _has_required_mesh(paper, {"foo"})
	# meshHeading as dict
	paper = {"meshHeadingList": {"meshHeading": [{"descriptorName": "bar"}]}}
	assert _has_required_mesh(paper, {"bar"})
	# partial match
	assert _has_required_mesh(paper, {"ba"})
	# required term not present
	assert not _has_required_mesh(paper, {"baz"})


def test__has_required_keywords_edge_cases():
	# No keywordList
	assert not _has_required_keywords({}, {"foo"})
	# keyword as string
	paper = {"keywordList": {"keyword": ["foo"]}}
	assert _has_required_keywords(paper, {"foo"})
	# keyword as dict
	paper = {"keywordList": {"keyword": [{"keyword": "bar"}]}}
	assert _has_required_keywords(paper, {"bar"})
	# partial match
	assert _has_required_keywords(paper, {"ba"})
	# required kw not present
	assert not _has_required_keywords(paper, {"baz"})


def test__has_required_abstract_terms_edge_cases():
	# No abstractText
	assert not _has_required_abstract_terms({}, {"foo"})
	# abstractText present
	paper = {"abstractText": "foo bar baz"}
	assert _has_required_abstract_terms(paper, {"foo"})
	assert _has_required_abstract_terms(paper, {"bar"})
	assert not _has_required_abstract_terms(paper, {"qux"})
	# multiple required terms
	assert _has_required_abstract_terms(paper, {"foo", "bar"})
	assert not _has_required_abstract_terms(paper, {"foo", "qux"})


def test_pubtypelist_meets_type_and_metadata():
	# paper with only pubTypeList (no pubType)
	paper = {
		"id": "PMC_TEST",
		"title": "Test paper",
		"pubYear": "2021",
		"pubTypeList": {"pubType": ["Journal Article", "Research Article"]},
		"isOpenAccess": "Y",
		"citedByCount": "5",
	}

	# allowed type includes 'Journal Article' -> should pass
	assert _meets_type_criteria(paper, ("Journal Article",)) is True

	# disallowed type -> should fail
	assert _meets_type_criteria(paper, ("Review",)) is False

	# metadata extraction should include pubType from pubTypeList
	meta = _extract_paper_metadata(paper)
	assert meta["pubType"] == ["Journal Article", "Research Article"]


def test_filter_max_pub_year():
	papers = [
		{"id": "A", "pubYear": "2018", "pubTypeList": {"pubType": ["Journal Article"]}, "citedByCount": "0", "isOpenAccess": "Y"},
		{"id": "B", "pubYear": "2022", "pubTypeList": {"pubType": ["Journal Article"]}, "citedByCount": "0", "isOpenAccess": "Y"},
	]

	# set max_pub_year to 2020, only the 2018 paper should remain
	filtered = filter_pmc_papers(papers, min_citations=0, min_pub_year=0, max_pub_year=2020, open_access=None)
	ids = [p["id"] for p in filtered]
	assert ids == ["A"]

	# same with OR variant
	filtered_or = filter_pmc_papers_or(papers, min_citations=0, min_pub_year=0, max_pub_year=2020, open_access=None)
	ids_or = [p["id"] for p in filtered_or]
	assert ids_or == ["A"]
