"""Unit tests for quality metrics functions."""

from types import SimpleNamespace
from typing import Any

import pytest

from pyeuropepmc.mappers.quality_metrics import (
    calculate_author_quality_score,
    calculate_institution_quality_score,
    calculate_paper_quality_score,
    get_confidence_level,
)


class TestCalculatePaperQualityScore:
    """Tests for calculate_paper_quality_score."""

    def test_base_score_only(self):
        paper = SimpleNamespace(doi=None, pmid=None, title=None, cited_by_count=0)
        score = calculate_paper_quality_score(paper)
        assert score == 0.5

    def test_doi_bonus(self):
        paper = SimpleNamespace(doi="10.1234/test", pmid=None, title=None, cited_by_count=0)
        assert calculate_paper_quality_score(paper) == 0.7

    def test_pmid_bonus(self):
        paper = SimpleNamespace(doi=None, pmid="12345", title=None, cited_by_count=0)
        assert calculate_paper_quality_score(paper) == 0.6

    def test_title_bonus(self):
        paper = SimpleNamespace(doi=None, pmid=None, title="A Test Title", cited_by_count=0)
        assert calculate_paper_quality_score(paper) == 0.6

    def test_cited_by_count_bonus(self):
        paper = SimpleNamespace(doi=None, pmid=None, title=None, cited_by_count=5)
        assert calculate_paper_quality_score(paper) == 0.6

    def test_all_bonuses(self):
        paper = SimpleNamespace(doi="10.1234/test", pmid="12345", title="A Test Title", cited_by_count=5)
        score = calculate_paper_quality_score(paper)
        assert score == pytest.approx(1.0)

    def test_capped_at_one_point_zero(self):
        paper = SimpleNamespace(doi="10.1234/test", pmid="12345", title="A Test Title", cited_by_count=3)
        score = calculate_paper_quality_score(paper)
        assert score == pytest.approx(1.0)

    def test_empty_string_attributes(self):
        paper = SimpleNamespace(doi="", pmid="", title="", cited_by_count=0)
        assert calculate_paper_quality_score(paper) == 0.5

    def test_missing_attribute(self):
        paper = SimpleNamespace()
        assert calculate_paper_quality_score(paper) == 0.5

    def test_cited_by_count_zero_no_bonus(self):
        paper = SimpleNamespace(doi="10.1234/test", pmid="12345", title="A Title", cited_by_count=0)
        assert calculate_paper_quality_score(paper) == pytest.approx(0.9)


class TestCalculateAuthorQualityScore:
    """Tests for calculate_author_quality_score."""

    def test_base_score_only(self):
        author = SimpleNamespace(orcid=None, affiliation_text=None, full_name=None)
        assert calculate_author_quality_score(author) == 0.5

    def test_orcid_bonus(self):
        author = SimpleNamespace(orcid="0000-0001-2345-6789", affiliation_text=None, full_name=None)
        assert calculate_author_quality_score(author) == 0.7

    def test_affiliation_text_bonus(self):
        author = SimpleNamespace(orcid=None, affiliation_text="University of Test", full_name=None)
        assert calculate_author_quality_score(author) == 0.6

    def test_full_name_bonus(self):
        author = SimpleNamespace(orcid=None, affiliation_text=None, full_name="John Doe")
        assert calculate_author_quality_score(author) == 0.7

    def test_all_bonuses(self):
        author = SimpleNamespace(
            orcid="0000-0001-2345-6789", affiliation_text="University of Test", full_name="John Doe"
        )
        assert calculate_author_quality_score(author) == 1.0

    def test_capped_at_one_point_zero(self):
        author = SimpleNamespace(
            orcid="0000-0001-2345-6789", affiliation_text="University of Test", full_name="John Doe"
        )
        score = calculate_author_quality_score(author)
        assert score == 1.0

    def test_empty_string_attributes(self):
        author = SimpleNamespace(orcid="", affiliation_text="", full_name="")
        assert calculate_author_quality_score(author) == 0.5

    def test_missing_attribute(self):
        author = SimpleNamespace()
        assert calculate_author_quality_score(author) == 0.5

    def test_orcid_and_full_name_only(self):
        author = SimpleNamespace(orcid="0000-0001-2345-6789", affiliation_text=None, full_name="Jane Doe")
        assert calculate_author_quality_score(author) == pytest.approx(0.9)


class TestCalculateInstitutionQualityScore:
    """Tests for calculate_institution_quality_score."""

    def test_base_score_only(self):
        assert calculate_institution_quality_score({}) == 0.5

    def test_country_bonus(self):
        assert calculate_institution_quality_score({"country": "US"}) == 0.6

    def test_type_bonus(self):
        assert calculate_institution_quality_score({"type": "university"}) == 0.6

    def test_name_longer_than_ten_bonus(self):
        assert calculate_institution_quality_score({"name": "University of Testing"}) == 0.6

    def test_name_ten_chars_no_bonus(self):
        assert calculate_institution_quality_score({"name": "1234567890"}) == 0.5

    def test_name_shorter_no_bonus(self):
        assert calculate_institution_quality_score({"name": "Test"}) == 0.5

    def test_member_count_positive_bonus(self):
        assert calculate_institution_quality_score({"member_count": 5}) == 0.6

    def test_member_count_zero_no_bonus(self):
        assert calculate_institution_quality_score({"member_count": 0}) == 0.5

    def test_all_bonuses(self):
        inst = {"country": "US", "type": "university", "name": "University of Testing", "member_count": 100}
        assert calculate_institution_quality_score(inst) == pytest.approx(0.9)

    def test_capped_at_one_point_zero(self):
        inst = {"country": "US", "type": "university", "name": "University of Testing", "member_count": 1}
        score = calculate_institution_quality_score(inst)
        assert score == pytest.approx(0.9)

    def test_missing_name_key(self):
        assert calculate_institution_quality_score({"country": "US"}) == 0.6

    def test_empty_string_values(self):
        inst = {"country": "", "type": "", "name": ""}
        assert calculate_institution_quality_score(inst) == 0.5


class TestGetConfidenceLevel:
    """Tests for get_confidence_level."""

    def test_high_at_zero_point_eight(self):
        assert get_confidence_level(0.8) == "high"

    def test_high_above_zero_point_eight(self):
        assert get_confidence_level(1.0) == "high"

    def test_medium_at_zero_point_six(self):
        assert get_confidence_level(0.6) == "medium"

    def test_medium_below_zero_point_eight(self):
        assert get_confidence_level(0.7) == "medium"

    def test_low_below_zero_point_six(self):
        assert get_confidence_level(0.5) == "low"

    def test_low_zero(self):
        assert get_confidence_level(0.0) == "low"

    def test_low_just_below_zero_point_six(self):
        assert get_confidence_level(0.59) == "low"
