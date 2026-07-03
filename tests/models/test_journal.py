"""
Tests for models/journal.py.

Covers JournalEntity creation, validation, normalization, and factory methods.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.models.journal import JournalEntity


class TestJournalEntity:
    """Tests for JournalEntity."""

    def test_default_creation(self) -> None:
        """Journal created with defaults."""
        j = JournalEntity()
        assert j.title == ""
        assert j.types == ["bibo:Journal"]
        assert j.label == ""

    def test_creation_with_title(self) -> None:
        """Journal with title."""
        j = JournalEntity(title="Nature")
        assert j.title == "Nature"
        assert j.label == "Nature"
        assert j.types == ["bibo:Journal"]

    def test_label_fallback_order(self) -> None:
        """Label uses first non-empty field from title/abbreviations."""
        j = JournalEntity(
            title="",
            medline_abbreviation="Medline Abbr",
            iso_abbreviation="ISO Abbr",
            nlm_ta="NLM TA",
            iso_abbrev="ISO Abbrev",
        )
        assert j.label == "Medline Abbr"

    def test_label_fallback_iso_abbreviation(self) -> None:
        """Label falls back to iso_abbreviation."""
        j = JournalEntity(iso_abbreviation="ISO Abbr")
        assert j.label == "ISO Abbr"

    def test_label_fallback_iso_abbrev(self) -> None:
        """Label falls back to iso_abbrev."""
        j = JournalEntity(iso_abbrev="ISO Abbrev")
        assert j.label == "ISO Abbrev"

    def test_label_fallback_nlm_ta(self) -> None:
        """Label falls back to nlm_ta."""
        j = JournalEntity(nlm_ta="NLM TA")
        assert j.label == "NLM TA"

    def test_custom_types_preserved(self) -> None:
        """Custom types are not overwritten by defaults."""
        j = JournalEntity(types=["custom:Type"])
        assert j.types == ["custom:Type"]

    def test_custom_label_preserved(self) -> None:
        """Custom label is preserved."""
        j = JournalEntity(label="Custom Label")
        assert j.label == "Custom Label"

    def test_validate_valid(self) -> None:
        """Validation passes for valid journal."""
        j = JournalEntity(title="Nature", issn="0028-0836")
        j.validate()  # Should not raise

    def test_validate_empty_title_raises(self) -> None:
        """Validation raises for empty title."""
        j = JournalEntity(title="")
        with pytest.raises(ValueError, match="must have a title"):
            j.validate()

    def test_validate_issn_invalid_raises(self) -> None:
        """Validation raises for invalid ISSN."""
        j = JournalEntity(title="Test", issn="invalid")
        with pytest.raises(ValueError, match="Invalid ISSN"):
            j.validate()

    def test_validate_essn_invalid_raises(self) -> None:
        """Validation raises for invalid EISSN."""
        j = JournalEntity(title="Test", essn="bad")
        with pytest.raises(ValueError, match="Invalid ISSN"):
            j.validate()

    def test_validate_issn_valid_with_x(self) -> None:
        """ISSN ending with X is valid."""
        j = JournalEntity(title="Test", issn="0028-083X")
        j.validate()
        assert j.issn == "0028-083X"

    def test_validate_openalex_id(self) -> None:
        """OpenAlex ID is validated as URI."""
        j = JournalEntity(title="Test", openalex_id="https://openalex.org/J123")
        j.validate()
        assert j.openalex_id is not None

    def test_validate_wikidata_id(self) -> None:
        """Wikidata ID is validated as URI."""
        j = JournalEntity(title="Test", wikidata_id="https://www.wikidata.org/Q123")
        j.validate()
        assert j.wikidata_id is not None

    def test_validate_positive_integers(self) -> None:
        """Positive integer fields are validated."""
        j = JournalEntity(
            title="Test",
            journal_issue_id=5,
            h_index=42,
        )
        j.validate()

    def test_validate_negative_journal_issue_id_raises(self) -> None:
        """Negative journal_issue_id raises."""
        j = JournalEntity(title="Test", journal_issue_id=-1)
        with pytest.raises(ValueError):
            j.validate()

    def test_validate_impact_factor_passthrough(self) -> None:
        """Non-negative impact_factor passes through."""
        j = JournalEntity(title="Test", impact_factor=2.5)
        j.validate()
        assert j.impact_factor == 2.5

    def test_validate_sjr_passthrough(self) -> None:
        """Non-negative SJR passes through."""
        j = JournalEntity(title="Test", sjr=1.5)
        j.validate()
        assert j.sjr == 1.5

    def test_normalize_trims_title(self) -> None:
        """Normalize trims whitespace from title."""
        j = JournalEntity(title="  Nature  ")
        j.normalize()
        assert j.title == "Nature"

    def test_normalize_validates_issn(self) -> None:
        """Normalize validates ISSN format."""
        j = JournalEntity(title="Nature", issn="0028-0836")
        j.normalize()
        assert j.issn == "0028-0836"

    def test_normalize_invalid_issn_raises(self) -> None:
        """Normalize raises for invalid ISSN."""
        j = JournalEntity(title="Nature", issn="bad")
        with pytest.raises(ValueError, match="Invalid ISSN"):
            j.normalize()

    def test_normalize_with_essn(self) -> None:
        """Normalize validates EISSN format."""
        j = JournalEntity(title="Nature", essn="1476-4687")
        j.normalize()
        assert j.essn == "1476-4687"

    def test_normalize_scopus_source_id(self) -> None:
        """Normalize scopus_source_id."""
        j = JournalEntity(title="Test", scopus_source_id=" 12345 ")
        j.normalize()
        assert j.scopus_source_id == "12345"

    def test_normalize_flattened_fields(self) -> None:
        """Normalize flattened journal ID fields."""
        j = JournalEntity(
            title="Test",
            nlm_ta=" NLM TA ",
            iso_abbrev=" ISO ",
            publisher_id=" PUB ",
        )
        j.normalize()
        assert j.nlm_ta == "NLM TA"
        assert j.iso_abbrev == "ISO"
        assert j.publisher_id == "PUB"

    def test_validate_issn_format_valid(self) -> None:
        """_validate_issn_format passes valid format."""
        j = JournalEntity(title="Test")
        assert j._validate_issn_format("1234-5678") == "1234-5678"

    def test_validate_issn_format_invalid(self) -> None:
        """_validate_issn_format raises for invalid format."""
        j = JournalEntity(title="Test")
        with pytest.raises(ValueError, match="Invalid ISSN"):
            j._validate_issn_format("abc-defg")

    def test_validate_issn_format_short(self) -> None:
        """_validate_issn_format raises for too short."""
        j = JournalEntity(title="Test")
        with pytest.raises(ValueError, match="Invalid ISSN"):
            j._validate_issn_format("1234-567")

    def test_from_search_result_nested(self) -> None:
        """from_search_result with nested format."""
        journal_info = {
            "journal": {
                "title": "Nature",
                "medlineAbbreviation": "Nature",
                "isoabbreviation": "Nature",
                "nlmid": "0410462",
                "issn": "0028-0836",
                "essn": "1476-4687",
            },
            "journalIssueId": 12345,
        }
        j = JournalEntity.from_search_result(journal_info)
        assert j.title == "Nature"
        assert j.medline_abbreviation == "Nature"
        assert j.iso_abbreviation == "Nature"
        assert j.nlmid == "0410462"
        assert j.issn == "0028-0836"
        assert j.essn == "1476-4687"
        assert j.journal_issue_id == 12345

    def test_from_search_result_flat(self) -> None:
        """from_search_result with flat format."""
        journal_info = {
            "title": "Nature",
            "issn": "0028-0836",
        }
        j = JournalEntity.from_search_result(journal_info)
        assert j.title == "Nature"
        assert j.issn == "0028-0836"
        assert j.medline_abbreviation is None
        assert j.iso_abbreviation is None
        assert j.nlmid is None
        assert j.essn is None
        assert j.journal_issue_id is None

    def test_from_enrichment_dict(self) -> None:
        """from_enrichment_dict creates journal from enrichment data."""
        journal_dict = {
            "display_name": "Nature",
            "issn": "0028-0836",
            "id": "https://openalex.org/J123",
            "publisher": "Nature Publishing Group",
            "country": "GB",
            "subjects": ["Multidisciplinary"],
            "impact_factor": 50.0,
            "sjr": 15.0,
            "h_index": 1000,
        }
        j = JournalEntity.from_enrichment_dict(journal_dict)
        assert j.title == "Nature"
        assert j.issn == "0028-0836"
        assert j.openalex_id == "https://openalex.org/J123"
        assert j.publisher == "Nature Publishing Group"
        assert j.country == "GB"
        assert j.subject_areas == ["Multidisciplinary"]
        assert j.impact_factor == 50.0
        assert j.sjr == 15.0
        assert j.h_index == 1000

    def test_from_enrichment_dict_empty(self) -> None:
        """from_enrichment_dict with empty dict."""
        j = JournalEntity.from_enrichment_dict({})
        assert j.title == ""
        assert j.issn is None
        assert j.openalex_id is None
        assert j.publisher is None
        assert j.country is None
        assert j.subject_areas is None
        assert j.impact_factor is None
        assert j.sjr is None
        assert j.h_index is None

    def test_to_dict(self) -> None:
        """to_dict returns serializable dict."""
        j = JournalEntity(
            title="Nature",
            issn="0028-0836",
            publisher="Nature Publishing Group",
            journal_ids={"issn": "0028-0836"},
        )
        d = j.to_dict()
        assert d["title"] == "Nature"
        assert d["issn"] == "0028-0836"
        assert d["publisher"] == "Nature Publishing Group"
        assert d["journal_ids"] == {"issn": "0028-0836"}
