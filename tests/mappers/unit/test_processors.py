"""Unit tests for data processing functions in pyeuropepmc.mappers.processors."""

from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.mappers.processors import (
    _convert_search_author_to_entity,
    _convert_search_author_simple,
    _create_author_entities,
    _create_enrichment_author_entities,
    _create_enrichment_paper_entity,
    _create_figure_entities,
    _create_grant_entities,
    _create_institution_entities,
    _create_journal_entity,
    _create_paper_entity,
    _create_paper_entity_from_search_result,
    _create_reference_entities,
    _create_section_entities,
    _create_table_entities,
    _determine_enrichment_data_structure,
    _extract_author_full_name,
    _extract_authors_from_search_result,
    _extract_entities_from_enrichment,
    _extract_entities_from_xml,
    _extract_mesh_headings,
    _extract_mesh_terms,
    _parse_author_string_to_authors,
    _process_single_search_result,
    _resolve_affiliation_text,
    _resolve_author_institutions,
    process_annotations_data,
    process_enrichment_data,
    process_search_results,
    process_xml_data,
)
from pyeuropepmc.models import (
    AuthorEntity,
    FigureEntity,
    GrantEntity,
    InstitutionEntity,
    JournalEntity,
    PaperEntity,
    ReferenceEntity,
)
from pyeuropepmc.models.section import SectionEntity
from pyeuropepmc.models.table import TableEntity


# =============================================================================
# _convert_search_author_to_entity
# =============================================================================

class TestConvertSearchAuthorToEntity:
    """Tests for _convert_search_author_to_entity."""

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_basic_conversion(self, mock_parser_class):
        """Test basic author dict conversion."""
        mock_parser = mock_parser_class.parse_affiliation_string
        inst_entity = InstitutionEntity(display_name="University of Testing")
        mock_parser.return_value = inst_entity

        author_dict = {
            "fullName": "Smith J",
            "firstName": "John",
            "lastName": "Smith",
            "initials": "J",
            "authorAffiliationDetailsList": {
                "authorAffiliation": [
                    {"affiliation": "University of Testing, City"}
                ]
            },
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.full_name == "Smith J"
        assert entity.first_name == "John"
        assert entity.last_name == "Smith"
        assert entity.initials == "J"
        assert entity.affiliation_text == "University of Testing, City"
        assert entity.orcid is None
        assert len(entity.institutions) == 1
        assert entity.institutions[0].display_name == "University of Testing"

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_with_orcid(self, mock_parser_class):
        """Test with ORCID identifier."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="University")

        author_dict = {
            "fullName": "Jane D",
            "authorId": {"type": "ORCID", "value": "0000-0002-1825-0097"},
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.full_name == "Jane D"
        assert entity.orcid == "0000-0002-1825-0097"

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_orcid_wrong_type(self, mock_parser_class):
        """Test when authorId has a type other than ORCID."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorId": {"type": "OTHER", "value": "12345"},
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.orcid is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_orcid_missing_type_key(self, mock_parser_class):
        """Test when authorId dict does not have a 'type' key."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorId": {"value": "12345"},
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.orcid is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_author_id_is_not_dict(self, mock_parser_class):
        """Test when authorId is a string instead of dict."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorId": "12345",
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.orcid is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_empty_affiliations(self, mock_parser_class):
        """Test with empty affiliations list."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="Test Inst")

        author_dict = {
            "fullName": "Test",
            "authorAffiliationDetailsList": {"authorAffiliation": []},
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.affiliation_text is None
        assert entity.institutions is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_affiliation_details_not_dict(self, mock_parser_class):
        """Test when authorAffiliationDetailsList is not a dict."""
        mock_parser = mock_parser_class.parse_affiliation_string

        author_dict = {
            "fullName": "Test",
            "authorAffiliationDetailsList": "invalid",
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.affiliation_text is None
        assert entity.institutions is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_missing_affiliation_details(self, mock_parser_class):
        """Test with missing authorAffiliationDetailsList."""
        mock_parser = mock_parser_class.parse_affiliation_string

        author_dict = {"fullName": "Test"}

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.affiliation_text is None
        assert entity.institutions is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_affiliation_without_str(self, mock_parser_class):
        """Test affiliation entry with missing 'affiliation' key."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorAffiliationDetailsList": {
                "authorAffiliation": [{"other": "data"}]
            },
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.affiliation_text is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_affiliations_not_list(self, mock_parser_class):
        """Test when authorAffiliation is not a list."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorAffiliationDetailsList": {
                "authorAffiliation": "single_string"
            },
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.institutions is None
        assert entity.affiliation_text is None

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_multiple_affiliations(self, mock_parser_class):
        """Test with multiple affiliations."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="Some University")

        author_dict = {
            "fullName": "Multi",
            "authorAffiliationDetailsList": {
                "authorAffiliation": [
                    {"affiliation": "Univ A"},
                    {"affiliation": "Univ B"},
                ]
            },
        }

        entity = _convert_search_author_to_entity(author_dict)
        assert entity.affiliation_text == "Univ A"
        assert len(entity.institutions) == 2

    @patch("pyeuropepmc.features.literature.search_parser.EuropePMCParser")
    def test_parse_returns_empty_display_name(self, mock_parser_class):
        """Test when parse_affiliation_string returns empty display_name."""
        mock_parser = mock_parser_class.parse_affiliation_string
        mock_parser.return_value = InstitutionEntity(display_name="")

        author_dict = {
            "fullName": "Test",
            "authorAffiliationDetailsList": {
                "authorAffiliation": [{"affiliation": "Some Dept"}]
            },
        }

        entity = _convert_search_author_to_entity(author_dict)
        # empty display_name -> not appended -> institutions list empty -> None
        assert entity.institutions is None


# =============================================================================
# _convert_search_author_simple
# =============================================================================

class TestConvertSearchAuthorSimple:
    """Tests for _convert_search_author_simple."""

    def test_basic(self):
        """Test basic simple conversion."""
        author_dict = {
            "fullName": "Smith J",
            "firstName": "John",
            "lastName": "Smith",
            "initials": "J",
        }
        entity = _convert_search_author_simple(author_dict)
        assert entity.full_name == "Smith J"
        assert entity.first_name == "John"
        assert entity.last_name == "Smith"
        assert entity.initials == "J"
        assert entity.affiliation_text is None
        assert entity.institutions is None
        assert entity.orcid is None

    def test_with_orcid(self):
        """Test with ORCID."""
        author_dict = {
            "fullName": "Jane D",
            "authorId": {"type": "ORCID", "value": "0000-0002-1825-0097"},
        }
        entity = _convert_search_author_simple(author_dict)
        assert entity.orcid == "0000-0002-1825-0097"

    def test_orcid_not_dict(self):
        """Test when authorId is not a dict."""
        author_dict = {
            "fullName": "Test",
            "authorId": "string_id",
        }
        entity = _convert_search_author_simple(author_dict)
        assert entity.orcid is None

    def test_orcid_wrong_type(self):
        """Test when authorId type is not ORCID."""
        author_dict = {
            "fullName": "Test",
            "authorId": {"type": "OTHER", "value": "12345"},
        }
        entity = _convert_search_author_simple(author_dict)
        assert entity.orcid is None

    def test_orcid_missing_type(self):
        """Test when authorId dict has no 'type' key."""
        author_dict = {
            "fullName": "Test",
            "authorId": {"value": "12345"},
        }
        entity = _convert_search_author_simple(author_dict)
        assert entity.orcid is None

    def test_minimal(self):
        """Test with minimal fields."""
        entity = _convert_search_author_simple({})
        assert entity.full_name == ""
        assert entity.first_name is None
        assert entity.last_name is None


# =============================================================================
# _parse_author_string_to_authors
# =============================================================================

class TestParseAuthorStringToAuthors:
    """Tests for _parse_author_string_to_authors."""

    def test_empty_string(self):
        """Test empty string."""
        assert _parse_author_string_to_authors("") == []

    def test_none_string(self):
        """Test None-like empty values (empty string, not None)."""
        assert _parse_author_string_to_authors("") == []

    def test_comma_separated(self):
        """Test comma-separated author names."""
        result = _parse_author_string_to_authors("Smith J, Johnson A, Brown K")
        assert result == ["Smith J", "Johnson A", "Brown K"]

    def test_semicolon_separated(self):
        """Test semicolon-separated author names."""
        result = _parse_author_string_to_authors("Smith J; Johnson A; Brown K")
        assert result == ["Smith J", "Johnson A", "Brown K"]

    def test_and_separated(self):
        """Test 'and'-separated author names."""
        result = _parse_author_string_to_authors("Smith J and Johnson A")
        assert result == ["Smith J", "Johnson A"]

    def test_mixed_separators(self):
        """Test mixed comma and 'and' separators."""
        result = _parse_author_string_to_authors("Smith J, Johnson A and Brown K")
        assert result == ["Smith J", "Johnson A", "Brown K"]

    def test_trailing_periods(self):
        """Test trailing periods are removed."""
        result = _parse_author_string_to_authors("Smith J., Johnson A.")
        assert result == ["Smith J", "Johnson A"]

    def test_extra_whitespace(self):
        """Test extra whitespace is normalized."""
        result = _parse_author_string_to_authors("  Smith  J  ,  Johnson  A  ")
        assert result == ["Smith J", "Johnson A"]

    def test_single_author(self):
        """Test single author."""
        result = _parse_author_string_to_authors("Smith J")
        assert result == ["Smith J"]

    def test_only_whitespace(self):
        """Test string with only whitespace."""
        result = _parse_author_string_to_authors("   ")
        result2 = _parse_author_string_to_authors(", ,,")
        assert result == []
        assert result2 == []

    def test_and_variations(self):
        """Test case-insensitive 'and'."""
        result = _parse_author_string_to_authors("A AND B")
        assert result == ["A", "B"]


# =============================================================================
# _extract_mesh_terms
# =============================================================================

class TestExtractMeshTerms:
    """Tests for _extract_mesh_terms."""

    def test_basic(self):
        """Test basic MeSH extraction."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Humans"},
                    {"descriptorName": "Neoplasms"},
                ]
            }
        }
        terms = _extract_mesh_terms(result)
        assert terms == ["Humans", "Neoplasms"]

    def test_empty_mesh(self):
        """Test with no MeSH headings."""
        result = {"meshHeadingList": {"meshHeading": []}}
        assert _extract_mesh_terms(result) == []

    def test_missing_mesh_heading_list(self):
        """Test with missing meshHeadingList key."""
        assert _extract_mesh_terms({}) == []

    def test_missing_descriptor_name(self):
        """Test heading without descriptorName."""
        result = {
            "meshHeadingList": {
                "meshHeading": [{"descriptorName": "Humans"}, {"other": "data"}]
            }
        }
        terms = _extract_mesh_terms(result)
        assert terms == ["Humans"]

    def test_nested_empty_dicts(self):
        """Test with empty dict inside meshHeadingList."""
        result = {"meshHeadingList": {}}
        assert _extract_mesh_terms(result) == []


# =============================================================================
# _extract_mesh_headings
# =============================================================================

class TestExtractMeshHeadings:
    """Tests for _extract_mesh_headings."""

    def test_basic(self):
        """Test extraction of structured MeSH headings."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {
                        "descriptorName": "Neoplasms",
                        "majorTopic_YN": "Y",
                    },
                    {
                        "descriptorName": "Humans",
                        "majorTopic_YN": "N",
                    },
                ]
            }
        }
        headings = _extract_mesh_headings(result)
        assert len(headings) == 2
        assert headings[0].descriptor_name == "Neoplasms"
        assert headings[0].major_topic is True
        assert headings[1].descriptor_name == "Humans"
        assert headings[1].major_topic is False

    def test_with_qualifiers(self):
        """Test extraction with qualifiers."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {
                        "descriptorName": "Neoplasms",
                        "majorTopic_YN": "Y",
                        "meshQualifierList": {
                            "meshQualifier": [
                                {
                                    "qualifierName": "therapy",
                                    "abbreviation": "TH",
                                    "majorTopic_YN": "N",
                                }
                            ]
                        },
                    }
                ]
            }
        }
        headings = _extract_mesh_headings(result)
        assert len(headings) == 1
        assert len(headings[0].qualifiers) == 1
        assert headings[0].qualifiers[0].qualifier_name == "therapy"
        assert headings[0].qualifiers[0].abbreviation == "TH"

    def test_empty_mesh_heading_list(self):
        """Test with empty meshHeading list."""
        result = {"meshHeadingList": {"meshHeading": []}}
        assert _extract_mesh_headings(result) == []

    def test_missing_mesh_heading_list(self):
        """Test with missing meshHeadingList."""
        assert _extract_mesh_headings({}) == []

    def test_mesh_heading_list_not_list(self):
        """Test when meshHeading is not a list."""
        result = {"meshHeadingList": {"meshHeading": "not_a_list"}}
        assert _extract_mesh_headings(result) == []

    def test_malformed_heading_skipped(self):
        """Test that malformed headings are still created (from_dict doesn't raise)."""
        result = {
            "meshHeadingList": {
                "meshHeading": [
                    {"descriptorName": "Valid"},
                    {"bad": "data"},
                ]
            }
        }
        headings = _extract_mesh_headings(result)
        assert len(headings) == 2
        assert headings[0].descriptor_name == "Valid"
        assert headings[1].descriptor_name == ""


# =============================================================================
# _extract_authors_from_search_result
# =============================================================================

class TestExtractAuthorsFromSearchResult:
    """Tests for _extract_authors_from_search_result."""

    def test_author_list_dict(self):
        """Test authorList as dict with author key."""
        result = {
            "authorList": {
                "author": [
                    {"fullName": "Smith J", "firstName": "John"},
                ]
            }
        }
        authors = _extract_authors_from_search_result(result)
        assert len(authors) == 1
        assert authors[0].full_name == "Smith J"

    def test_authors_as_list(self):
        """Test 'authors' key as a list."""
        result = {
            "authors": [
                {"fullName": "Doe J"},
            ]
        }
        authors = _extract_authors_from_search_result(result)
        assert len(authors) == 1
        assert authors[0].full_name == "Doe J"

    def test_author_list_precedence(self):
        """Test authorList takes precedence over authors."""
        result = {
            "authorList": {
                "author": [{"fullName": "From AuthorList"}]
            },
            "authors": [{"fullName": "From Authors"}],
        }
        authors = _extract_authors_from_search_result(result)
        assert len(authors) == 1
        assert authors[0].full_name == "From AuthorList"

    def test_fallback_to_author_string(self):
        """Test fallback to authorString when no structured data."""
        result = {"authorString": "Smith J, Johnson A"}
        authors = _extract_authors_from_search_result(result)
        assert len(authors) == 2
        assert isinstance(authors[0], AuthorEntity)
        # authorString creates string-based AuthorEntity
        assert authors[0].full_name == "Smith J"

    def test_no_authors(self):
        """Test with no author data at all."""
        result = {}
        authors = _extract_authors_from_search_result(result)
        assert authors == []

    def test_author_list_not_dict_or_list(self):
        """Test when authorList is neither dict nor list."""
        result = {"authorList": "invalid"}
        authors = _extract_authors_from_search_result(result)
        assert authors == []

    def test_author_list_dict_no_author_key(self):
        """Test when authorList dict has no 'author' key."""
        result = {"authorList": {"something": "else"}}
        authors = _extract_authors_from_search_result(result)
        assert authors == []

    def test_author_list_is_list(self):
        """Test when authorList is directly a list."""
        result = {
            "authorList": [
                {"fullName": "Direct List"},
            ]
        }
        authors = _extract_authors_from_search_result(result)
        assert len(authors) == 1
        assert authors[0].full_name == "Direct List"


# =============================================================================
# _create_paper_entity_from_search_result
# =============================================================================

class TestCreatePaperEntityFromSearchResult:
    """Tests for _create_paper_entity_from_search_result."""

    def test_basic(self):
        """Test basic paper entity creation."""
        journal = JournalEntity(title="Test Journal")
        authors = [AuthorEntity(full_name="Smith J")]
        result = {
            "doi": "10.1234/test",
            "pmcid": "PMC1234567",
            "pmid": "12345678",
            "title": "Test Paper",
            "abstractText": "An abstract here",
            "pubYear": 2024,
            "keywordList": ["keyword1", "keyword2"],
        }
        entity = _create_paper_entity_from_search_result(result, journal, authors, ["Humans"])
        assert entity.doi == "10.1234/test"
        assert entity.pmcid == "PMC1234567"
        assert entity.pmid == "12345678"
        assert entity.title == "Test Paper"
        assert entity.abstract == "An abstract here"
        assert entity.publication_year == 2024
        assert entity.journal is journal
        assert entity.keywords == ["keyword1", "keyword2"]
        assert entity.mesh_terms == ["Humans"]

    def test_missing_fields(self):
        """Test with missing optional fields."""
        entity = _create_paper_entity_from_search_result({}, None, [], [])
        assert entity.doi is None
        assert entity.pmcid is None
        assert entity.pmid is None
        assert entity.title is None
        assert entity.abstract is None
        assert entity.publication_year is None
        assert entity.journal is None
        assert entity.keywords == []
        assert entity.mesh_terms == []

    def test_keyword_list_missing(self):
        """Test when 'keywordList' is missing from result."""
        result = {"title": "Test"}
        entity = _create_paper_entity_from_search_result(result, None, [], [])
        assert entity.keywords == []


# =============================================================================
# _process_single_search_result
# =============================================================================

class TestProcessSingleSearchResult:
    """Tests for _process_single_search_result."""

    def test_basic(self):
        """Test basic single result processing."""
        result = {
            "doi": "10.1234/test",
            "title": "Test Paper",
            "journalTitle": "Test Journal",
            "pubYear": 2024,
            "authorList": {
                "author": [{"fullName": "Smith J"}]
            },
            "meshHeadingList": {
                "meshHeading": [{"descriptorName": "Humans"}]
            },
        }
        entities_data = _process_single_search_result(result)
        assert len(entities_data) == 2  # paper + 1 author

        paper_entry = entities_data[0]
        assert isinstance(paper_entry["entity"], PaperEntity)
        assert paper_entry["entity"].title == "Test Paper"
        assert paper_entry["entity"].journal.title == "Test Journal"
        assert paper_entry["entity"].publication_year == 2024
        assert paper_entry["entity"].mesh_terms == ["Humans"]
        assert len(paper_entry["related_entities"]["authors"]) == 1

        author_entry = entities_data[1]
        assert isinstance(author_entry["entity"], AuthorEntity)
        assert author_entry["entity"].full_name == "Smith J"

    def test_no_journal(self):
        """Test without journal title."""
        result = {"title": "Test"}
        entities_data = _process_single_search_result(result)
        assert len(entities_data) >= 1
        assert entities_data[0]["entity"].journal is None

    def test_no_authors(self):
        """Test with no authors."""
        result = {"title": "Test"}
        entities_data = _process_single_search_result(result)
        assert len(entities_data) == 1  # only paper

    def test_multiple_authors(self):
        """Test with multiple authors."""
        result = {
            "title": "Test",
            "authorList": {
                "author": [
                    {"fullName": "Smith J"},
                    {"fullName": "Doe J"},
                ]
            },
        }
        entities_data = _process_single_search_result(result)
        assert len(entities_data) == 3  # paper + 2 authors
        paper_entry = entities_data[0]
        assert len(paper_entry["related_entities"]["authors"]) == 2


# =============================================================================
# process_search_results
# =============================================================================

class TestProcessSearchResults:
    """Tests for process_search_results."""

    def test_single_dict(self):
        """Test processing single dict."""
        search_data = {
            "doi": "10.1234/test",
            "title": "Test Paper",
            "journalTitle": "Test Journal",
        }
        entities_data = process_search_results(search_data)
        assert len(entities_data) >= 1
        assert isinstance(entities_data[0]["entity"], PaperEntity)
        assert entities_data[0]["entity"].doi == "10.1234/test"

    def test_list_of_dicts(self):
        """Test processing list of dicts."""
        search_data = [
            {"doi": "10.1234/one", "title": "Paper 1"},
            {"doi": "10.1234/two", "title": "Paper 2"},
        ]
        entities_data = process_search_results(search_data)
        assert len(entities_data) >= 2
        assert entities_data[0]["entity"].doi == "10.1234/one"
        assert entities_data[1]["entity"].doi == "10.1234/two"

    def test_empty_list(self):
        """Test with empty list."""
        assert process_search_results([]) == []

    def test_error_in_result_skipped(self):
        """Test that a bad result is skipped."""
        search_data = [
            {"title": "Good"},
            None,  # This will cause an error when processed
            {"title": "Also Good"},
        ]
        # Use patch to make the second result raise
        with patch(
            "pyeuropepmc.mappers.processors._process_single_search_result",
            side_effect=[["paper1"], Exception("Boom"), ["paper2"]],
        ):
            entities_data = process_search_results(search_data)
            assert len(entities_data) == 2


# =============================================================================
# process_xml_data
# =============================================================================

class TestProcessXmlData:
    """Tests for process_xml_data."""

    def test_basic(self):
        """Test basic XML data processing."""
        xml_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "publication_year": 2024,
            },
            "authors": [{"full_name": "John Doe"}],
        }
        entities_data = process_xml_data(xml_data, include_content=True)
        assert len(entities_data) == 1
        entity_data = entities_data[0]
        assert isinstance(entity_data["entity"], PaperEntity)
        assert entity_data["entity"].doi == "10.1234/test"

    def test_empty_xml(self):
        """Test with empty XML data."""
        assert process_xml_data({}) == []

    def test_exclude_content(self):
        """Test with include_content=False."""
        xml_data = {
            "paper": {"title": "Test"},
            "sections": [{"title": "Intro", "content": "Text"}],
            "tables": [{"caption": "Table 1"}],
        }
        entities_data = process_xml_data(xml_data, include_content=False)
        assert len(entities_data) == 1
        related = entities_data[0]["related_entities"]
        assert related["sections"] == []
        assert related["tables"] == []
        assert related["figures"] == []


# =============================================================================
# process_enrichment_data
# =============================================================================

class TestProcessEnrichmentData:
    """Tests for process_enrichment_data."""

    def test_paper_level(self):
        """Test with paper-level enrichment data."""
        enrichment_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": "Test Journal",
            },
            "authors": [{"full_name": "John Doe"}],
        }
        entities_data = process_enrichment_data(enrichment_data)
        assert len(entities_data) == 1
        assert isinstance(entities_data[0]["entity"], PaperEntity)
        assert entities_data[0]["entity"].doi == "10.1234/test"

    def test_author_level(self):
        """Test with author-level enrichment data."""
        enrichment_data = {
            "authors": [
                {"full_name": "John Doe", "orcid": "0000-0002-1825-0097"},
            ]
        }
        entities_data = process_enrichment_data(enrichment_data)
        assert len(entities_data) == 1
        assert isinstance(entities_data[0]["entity"], AuthorEntity)
        assert entities_data[0]["entity"].full_name == "John Doe"
        assert entities_data[0]["entity"].orcid == "0000-0002-1825-0097"

    def test_empty_data(self):
        """Test with empty enrichment data."""
        assert process_enrichment_data({}) == []

    def test_merged_format(self):
        """Test with merged enrichment format."""
        enrichment_data = {
            "merged": {
                "title": "Merged Paper",
                "doi": "10.1234/merged",
            },
            "authors": [{"name": "Author One"}],
        }
        entities_data = process_enrichment_data(enrichment_data)
        assert len(entities_data) == 1
        assert entities_data[0]["entity"].title == "Merged Paper"

    def test_semantic_scholar_format(self):
        """Test with semantic_scholar enrichment format."""
        enrichment_data = {
            "semantic_scholar": {
                "title": "SS Paper",
                "doi": "10.1234/ss",
            },
        }
        entities_data = process_enrichment_data(enrichment_data)
        assert len(entities_data) == 1
        assert entities_data[0]["entity"].title == "SS Paper"


# =============================================================================
# process_annotations_data
# =============================================================================

class TestProcessAnnotationsData:
    """Tests for process_annotations_data."""

    def _get_patches(self):
        """Get the real modules for patching (shadowed by __init__.py)."""
        import sys as _sys
        _ann_mod = _sys.modules["pyeuropepmc.features.literature.annotations_to_rdf"]
        _par_mod = _sys.modules["pyeuropepmc.features.fulltext.annotation_parser"]
        return (
            patch.object(_par_mod, "parse_annotations"),
            patch.object(_par_mod, "normalize_annotations_response"),
            patch.object(_ann_mod, "annotations_to_entities"),
        )

    def test_dict_with_entities_key(self):
        """Test with dict containing 'entities' key."""
        mock_parse, mock_norm, mock_a2e = self._get_patches()
        with mock_parse as m_parse, mock_norm as m_norm, mock_a2e as m_a2e:
            m_norm.return_value = {"normalized": True}
            m_a2e.return_value = [MagicMock(), MagicMock()]

            data = {"entities": [{"id": 1}], "other": "data"}
            result = process_annotations_data(data)

        assert len(result) == 2
        assert "entity" in result[0]
        m_parse.assert_not_called()

    def test_list_of_articles_with_annotations(self):
        """Test with list of articles each having annotations."""
        mock_parse, mock_norm, mock_a2e = self._get_patches()
        with mock_parse as m_parse, mock_norm as m_norm, mock_a2e as m_a2e:
            m_parse.return_value = {"parsed": True}
            m_norm.return_value = {"normalized": True}
            m_a2e.return_value = [MagicMock(), MagicMock()]

            data = [
                {
                    "annotations": [{"text": "gene"}],
                    "pmcid": "PMC123",
                    "source": "MED",
                    "extId": "12345",
                }
            ]
            result = process_annotations_data(data)
        assert len(result) == 2

    def test_plain_list(self):
        """Test with a plain list (no article wrappers)."""
        mock_parse, mock_norm, mock_a2e = self._get_patches()
        with mock_parse as m_parse, mock_norm as m_norm, mock_a2e as m_a2e:
            m_parse.return_value = {"parsed": True}
            m_norm.return_value = {"normalized": True}
            m_a2e.return_value = [MagicMock()]

            data = [{"text": "annotation"}]
            result = process_annotations_data(data)
        assert len(result) == 1

    def test_empty_list(self):
        """Test with empty list."""
        mock_parse, mock_norm, mock_a2e = self._get_patches()
        with mock_parse as m_parse, mock_norm as m_norm, mock_a2e as m_a2e:
            m_parse.return_value = {"parsed": True}
            m_norm.return_value = {"normalized": True}
            m_a2e.return_value = []

            result = process_annotations_data([])
        assert result == []

    def test_string_value(self):
        """Test with non-dict/non-list value."""
        mock_parse, mock_norm, mock_a2e = self._get_patches()
        with mock_parse as m_parse, mock_norm as m_norm, mock_a2e as m_a2e:
            m_parse.return_value = {"parsed": True}
            m_norm.return_value = {"normalized": True}
            m_a2e.return_value = []

            result = process_annotations_data("invalid")
        assert result == []


# =============================================================================
# _create_journal_entity
# =============================================================================

class TestCreateJournalEntity:
    """Tests for _create_journal_entity."""

    def test_dict_with_title(self):
        """Test dict with 'title' key."""
        journal = _create_journal_entity({"title": "Nature", "issn": "0028-0836"})
        assert isinstance(journal, JournalEntity)
        assert journal.title == "Nature"
        assert journal.issn == "0028-0836"

    def test_dict_with_name(self):
        """Test dict with 'name' key."""
        journal = _create_journal_entity({"name": "Science", "issn_print": "0036-8075"})
        assert journal.title == "Science"
        assert journal.issn == "0036-8075"

    def test_dict_with_journal_title(self):
        """Test dict with 'journal_title' key."""
        journal = _create_journal_entity({"journal_title": "PLOS ONE"})
        assert journal.title == "PLOS ONE"

    def test_dict_with_extra_fields(self):
        """Test dict with all optional fields."""
        journal = _create_journal_entity({
            "title": "Test Journal",
            "issn": "1234-5678",
            "issn_electronic": "8765-4321",
            "nlm_ta": "Test J",
            "iso_abbrev": "Test J",
            "publisher": "Test Pub",
            "country": "US",
        })
        assert journal.title == "Test Journal"
        assert journal.issn == "1234-5678"
        assert journal.essn == "8765-4321"
        assert journal.medline_abbreviation == "Test J"
        assert journal.iso_abbreviation == "Test J"
        assert journal.publisher == "Test Pub"
        assert journal.country == "US"

    def test_string(self):
        """Test string input."""
        journal = _create_journal_entity("Nature")
        assert isinstance(journal, JournalEntity)
        assert journal.title == "Nature"

    def test_none(self):
        """Test None input."""
        assert _create_journal_entity(None) is None

    def test_empty_dict(self):
        """Test empty dict."""
        journal = _create_journal_entity({})
        assert isinstance(journal, JournalEntity)
        assert journal.title == ""


# =============================================================================
# _create_paper_entity
# =============================================================================

class TestCreatePaperEntity:
    """Tests for _create_paper_entity."""

    def test_basic(self):
        """Test basic paper entity creation."""
        journal = JournalEntity(title="Test Journal")
        paper_data = {
            "doi": "10.1234/test",
            "pmcid": "PMC1234567",
            "pmid": "12345678",
            "title": "Test Paper",
            "abstract": "Abstract text",
            "publication_year": 2024,
            "keywords": ["kw1", "kw2"],
            "mesh_terms": ["Humans"],
            "license": {"type": "cc-by"},
            "publisher": {"name": "Test Publisher"},
        }
        entity = _create_paper_entity(paper_data, journal)
        assert entity.doi == "10.1234/test"
        assert entity.pmcid == "PMC1234567"
        assert entity.pmid == "12345678"
        assert entity.title == "Test Paper"
        assert entity.abstract == "Abstract text"
        assert entity.publication_year == 2024
        assert entity.journal is journal
        assert entity.keywords == ["kw1", "kw2"]
        assert entity.mesh_terms == ["Humans"]
        assert entity.license == {"type": "cc-by"}
        assert entity.publisher == "Test Publisher"

    def test_identifiers_fallback(self):
        """Test identifiers from 'identifiers' dict."""
        paper_data = {
            "identifiers": {"doi": "10.1234/fallback", "pmcid": "PMC999"},
        }
        entity = _create_paper_entity(paper_data, None)
        assert entity.doi == "10.1234/fallback"
        assert entity.pmcid == "PMC999"

    def test_none_journal(self):
        """Test with None journal."""
        entity = _create_paper_entity({"title": "Test"}, None)
        assert entity.journal is None

    def test_funding_as_grants(self):
        """Test funding data is transformed into grants."""
        paper_data = {
            "title": "Test",
            "funding": [
                {"fundref_doi": "10.13039/123", "funding_source": "NIH", "award_id": "R01"}
            ],
        }
        entity = _create_paper_entity(paper_data, None)
        assert entity.grants is not None
        assert len(entity.grants) == 1
        assert entity.grants[0].fundref_doi == "10.13039/123"

    def test_empty_publisher(self):
        """Test with empty publisher dict."""
        entity = _create_paper_entity({"publisher": {}}, None)
        assert entity.publisher is None


# =============================================================================
# _extract_author_full_name
# =============================================================================

class TestExtractAuthorFullName:
    """Tests for _extract_author_full_name."""

    def test_full_name_key(self):
        """Test with 'full_name' key."""
        name = _extract_author_full_name({"full_name": "John Smith"})
        assert name == "John Smith"

    def test_name_key(self):
        """Test with 'name' key."""
        name = _extract_author_full_name({"name": "Jane Doe"})
        assert name == "Jane Doe"

    def test_given_and_surname(self):
        """Test with given_names and surname keys."""
        name = _extract_author_full_name({"given_names": "John", "surname": "Smith"})
        assert name == "John Smith"

    def test_given_names_only(self):
        """Test with only given_names."""
        name = _extract_author_full_name({"given_names": "John"})
        assert name == "John"

    def test_surname_only(self):
        """Test with only surname."""
        name = _extract_author_full_name({"surname": "Smith"})
        assert name == "Smith"

    def test_no_matching_keys(self):
        """Test with no matching keys."""
        name = _extract_author_full_name({"other": "data"})
        assert name == ""

    def test_empty_dict(self):
        """Test with empty dict."""
        name = _extract_author_full_name({})
        assert name == ""

    def test_all_keys_full_name_takes_precedence(self):
        """Test full_name takes precedence over other keys."""
        name = _extract_author_full_name({
            "full_name": "Priority",
            "name": "Fallback",
            "given_names": "John",
            "surname": "Smith",
        })
        assert name == "Priority"

    def test_name_takes_precedence_over_given_surname(self):
        """Test 'name' takes precedence over given+surname."""
        name = _extract_author_full_name({
            "name": "Name Only",
            "given_names": "John",
            "surname": "Smith",
        })
        assert name == "Name Only"


# =============================================================================
# _resolve_affiliation_text
# =============================================================================

class TestResolveAffiliationText:
    """Tests for _resolve_affiliation_text."""

    def test_direct_affiliation(self):
        """Test direct affiliation text."""
        result = _resolve_affiliation_text(
            {"affiliation": "University of Testing"}, None
        )
        assert result == "University of Testing"

    def test_affiliation_empty_refs_no_lookup(self):
        """Test empty affiliation with no refs and no lookup."""
        result = _resolve_affiliation_text(
            {"affiliation": "", "affiliation_refs": []}, None
        )
        assert result == ""

    def test_affiliation_refs_with_lookup(self):
        """Test resolving refs with lookup."""
        result = _resolve_affiliation_text(
            {"affiliation_refs": ["ref1", "ref2"]},
            {"ref1": "Univ A", "ref2": "Univ B"},
        )
        assert result == "Univ A; Univ B"

    def test_affiliation_refs_partial_lookup(self):
        """Test refs with only some matching."""
        result = _resolve_affiliation_text(
            {"affiliation_refs": ["ref1", "ref_missing"]},
            {"ref1": "Univ A"},
        )
        assert result == "Univ A"

    def test_affiliation_refs_no_lookup(self):
        """Test refs without lookup (falls back to raw refs)."""
        result = _resolve_affiliation_text(
            {"affiliation_refs": ["ref1", "ref2"]}, None
        )
        assert result == "ref1, ref2"

    def test_affiliation_refs_empty_lookup(self):
        """Test refs with empty lookup (empty dict is falsy, returns raw refs)."""
        result = _resolve_affiliation_text(
            {"affiliation_refs": ["ref1"]}, {}
        )
        assert result == "ref1"

    def test_affiliation_text_takes_precedence(self):
        """Test direct affiliation text takes precedence over refs."""
        result = _resolve_affiliation_text(
            {"affiliation": "Direct", "affiliation_refs": ["ref1"]},
            {"ref1": "Resolved"},
        )
        assert result == "Direct"


# =============================================================================
# _resolve_author_institutions
# =============================================================================

class TestResolveAuthorInstitutions:
    """Tests for _resolve_author_institutions."""

    def test_resolve_with_mapping(self):
        """Test resolving with affiliation mapping."""
        inst_a = InstitutionEntity(display_name="Univ A")
        inst_b = InstitutionEntity(display_name="Univ B")
        mapping = {"ref1": inst_a, "ref2": inst_b}

        result = _resolve_author_institutions(
            {"affiliation_refs": ["ref1", "ref2"]}, mapping
        )
        assert len(result) == 2
        assert result[0].display_name == "Univ A"
        assert result[1].display_name == "Univ B"

    def test_no_mapping(self):
        """Test with no mapping (None)."""
        result = _resolve_author_institutions(
            {"affiliation_refs": ["ref1"]}, None
        )
        assert result == []

    def test_empty_mapping(self):
        """Test with empty dict mapping."""
        result = _resolve_author_institutions(
            {"affiliation_refs": ["ref1"]}, {}
        )
        assert result == []

    def test_partial_mapping(self):
        """Test when some refs not in mapping."""
        mapping = {"ref1": InstitutionEntity(display_name="Univ A")}
        result = _resolve_author_institutions(
            {"affiliation_refs": ["ref1", "ref_missing"]}, mapping
        )
        assert len(result) == 1
        assert result[0].display_name == "Univ A"

    def test_no_affiliation_refs(self):
        """Test with no affiliation_refs key."""
        mapping = {"ref1": InstitutionEntity(display_name="Univ A")}
        result = _resolve_author_institutions({}, mapping)
        assert result == []


# =============================================================================
# _create_author_entities
# =============================================================================

class TestCreateAuthorEntities:
    """Tests for _create_author_entities."""

    def test_dict_author(self):
        """Test dict-based author."""
        result = _create_author_entities([{"full_name": "John Smith", "orcid": "0000-0002-1825-0097"}])
        assert len(result) == 1
        assert result[0].full_name == "John Smith"
        assert result[0].orcid == "0000-0002-1825-0097"

    def test_string_author(self):
        """Test string-based author."""
        result = _create_author_entities(["John Smith"])
        assert len(result) == 1
        assert result[0].full_name == "John Smith"

    def test_invalid_type_skipped(self):
        """Test that invalid types are skipped."""
        result = _create_author_entities(["Valid", 123, None, {"full_name": "Also Valid"}])
        assert len(result) == 2
        assert result[0].full_name == "Valid"
        assert result[1].full_name == "Also Valid"

    def test_with_affiliation_resolution(self):
        """Test with affiliation lookup."""
        result = _create_author_entities(
            [{"full_name": "John", "affiliation_refs": ["ref1"]}],
            affiliations_lookup={"ref1": "Univ A"},
        )
        assert len(result) == 1
        assert result[0].affiliation_text == "Univ A"

    def test_with_institution_resolution(self):
        """Test with institution resolution."""
        inst = InstitutionEntity(display_name="Univ A")
        result = _create_author_entities(
            [{"full_name": "John", "affiliation_refs": ["ref1"]}],
            affiliations_id_to_entity={"ref1": inst},
        )
        assert len(result) == 1
        assert len(result[0].institutions) == 1
        assert result[0].institutions[0].display_name == "Univ A"

    def test_empty_list(self):
        """Test empty input list."""
        assert _create_author_entities([]) == []

    def test_error_in_item_skipped(self):
        """Test that items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors._extract_author_full_name",
            side_effect=[Exception("Boom")],
        ):
            result = _create_author_entities([{"bad": "data"}])
            assert result == []


# =============================================================================
# _create_reference_entities
# =============================================================================

class TestCreateReferenceEntities:
    """Tests for _create_reference_entities."""

    def test_basic(self):
        """Test basic reference creation."""
        refs = [
            {
                "title": "Ref 1",
                "source": "Journal A",
                "year": "2024",
                "volume": "10",
                "pages": "100-110",
                "doi": "10.1234/ref1",
                "pmid": "12345678",
                "authors": "Smith J, Doe J",
            }
        ]
        result = _create_reference_entities(refs)
        assert len(result) == 1
        assert result[0].title == "Ref 1"
        assert result[0].journal == "Journal A"
        assert result[0].publication_year == 2024
        assert result[0].volume == "10"
        assert result[0].pages == "100-110"
        assert result[0].doi == "10.1234/ref1"
        assert result[0].pmid == "12345678"
        assert result[0].authors == "Smith J, Doe J"

    def test_none_year(self):
        """Test with None year."""
        refs = [{"title": "Ref", "year": None}]
        result = _create_reference_entities(refs)
        assert result[0].publication_year is None

    def test_invalid_type_skipped(self):
        """Test that non-dicts are skipped."""
        refs = [{"title": "Valid"}, "string", 123]
        result = _create_reference_entities(refs)
        assert len(result) == 1

    def test_error_in_item_skipped(self):
        """Test that items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.int",
            side_effect=[ValueError("Boom")],
        ):
            refs = [{"year": "bad"}]
            result = _create_reference_entities(refs)
            assert result == []

    def test_empty_list(self):
        """Test empty list."""
        assert _create_reference_entities([]) == []

    def test_minimal(self):
        """Test minimal reference data."""
        refs = [{"title": "Minimal"}]
        result = _create_reference_entities(refs)
        assert len(result) == 1
        assert result[0].title == "Minimal"


# =============================================================================
# _create_institution_entities
# =============================================================================

class TestCreateInstitutionEntities:
    """Tests for _create_institution_entities."""

    def test_basic(self):
        """Test basic institution creation."""
        affiliations = [
            {
                "institution": "University of Testing",
                "institution_ids": {"ROR": "https://ror.org/abc123"},
                "country": "US",
                "city": "Test City",
            }
        ]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1
        assert result[0].display_name == "University of Testing"
        assert result[0].ror_id == "https://ror.org/abc123"
        assert result[0].country == "US"
        assert result[0].city == "Test City"

    def test_with_text_fallback(self):
        """Test fallback to 'text' key for name."""
        affiliations = [
            {
                "text": "Some University",
                "institution_ids": {"GRID": "grid.12345"},
            }
        ]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1
        assert result[0].display_name == "Some University"
        assert result[0].grid_id == "grid.12345"

    def test_dedup_by_ror(self):
        """Test deduplication by ROR ID."""
        affiliations = [
            {"institution": "Univ A", "institution_ids": {"ROR": "ror1"}},
            {"institution": "Univ A (dup)", "institution_ids": {"ROR": "ror1"}},
        ]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1

    def test_dedup_by_grid(self):
        """Test deduplication by GRID ID."""
        affiliations = [
            {"institution": "Inst A", "institution_ids": {"GRID": "grid.1"}},
            {"institution": "Inst A (dup)", "institution_ids": {"GRID": "grid.1"}},
        ]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1

    def test_dedup_by_name(self):
        """Test deduplication by name when no IDs."""
        affiliations = [
            {"institution": "Same Name"},
            {"institution": "Same Name"},
        ]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1

    def test_no_ids_or_name_skipped(self):
        """Test entry with no IDs or name is skipped."""
        affiliations = [{"institution": "Valid"}, {"other": "data"}]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1

    def test_non_dict_skipped(self):
        """Test non-dict entries are skipped."""
        affiliations = [{"institution": "Valid"}, "string", 123]
        result = _create_institution_entities(affiliations)
        assert len(result) == 1

    def test_isni_id(self):
        """Test ISNI ID."""
        affiliations = [
            {"institution": "Univ", "institution_ids": {"ISNI": "0000-0001-2345-6789"}}
        ]
        result = _create_institution_entities(affiliations)
        assert result[0].isni == "0000-0001-2345-6789"

    def test_empty_list(self):
        """Test empty list."""
        assert _create_institution_entities([]) == []

    def test_error_skipped(self):
        """Test that an item causing error is skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.InstitutionEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_institution_entities([{"institution": "Bad"}])
            assert result == []


# =============================================================================
# _create_grant_entities
# =============================================================================

class TestCreateGrantEntities:
    """Tests for _create_grant_entities."""

    def test_basic(self):
        """Test basic grant creation."""
        funding = [
            {
                "fundref_doi": "10.13039/123",
                "award_id": "R01-GM12345",
                "funding_source": "NIH",
            }
        ]
        result = _create_grant_entities(funding)
        assert result is not None
        assert len(result) == 1
        assert result[0].fundref_doi == "10.13039/123"
        assert result[0].award_id == "R01-GM12345"
        assert result[0].funding_source == "NIH"

    def test_with_recipients(self):
        """Test with recipients list."""
        funding = [
            {
                "fundref_doi": "10.13039/123",
                "recipients": [
                    {"full_name": "John Smith", "given_names": "John", "surname": "Smith"},
                    {"full_name": "Jane Doe"},
                ],
            }
        ]
        result = _create_grant_entities(funding)
        assert result is not None
        assert len(result[0].recipients) == 2
        assert result[0].recipients[0].full_name == "John Smith"
        assert result[0].recipients[0].first_name == "John"
        assert result[0].recipients[0].last_name == "Smith"
        assert result[0].recipients[1].full_name == "Jane Doe"

    def test_with_deprecated_recipient_fields(self):
        """Test with deprecated recipient fields."""
        funding = [
            {
                "recipient_full": "John Smith",
                "recipient_name": "Jane Doe",
            }
        ]
        result = _create_grant_entities(funding)
        assert result is not None
        assert result[0].recipient == "John Smith"  # recipient_full takes precedence

    def test_none_funding(self):
        """Test with None funding."""
        assert _create_grant_entities(None) is None

    def test_empty_list_funding(self):
        """Test with empty list."""
        assert _create_grant_entities([]) is None

    def test_non_dict_skipped(self):
        """Test that non-dict funders are skipped."""
        funding = [{"funding_source": "Valid"}, "string", 123]
        result = _create_grant_entities(funding)
        assert result is not None
        assert len(result) == 1

    def test_error_skipped(self):
        """Test that items causing errors are skipped."""
        funding = [{"bad": "data"}]
        with patch(
            "pyeuropepmc.mappers.processors.GrantEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_grant_entities(funding)
            assert result is None

    def test_recipient_without_full_name_skipped(self):
        """Test recipient without full_name is skipped (recipients becomes None)."""
        funding = [
            {
                "recipients": [{"given_names": "John"}],  # No full_name
            }
        ]
        result = _create_grant_entities(funding)
        assert result is not None
        assert result[0].recipients is None


# =============================================================================
# _create_section_entities
# =============================================================================

class TestCreateSectionEntities:
    """Tests for _create_section_entities."""

    def test_dict_with_title_content(self):
        """Test dict with title and content."""
        sections = [{"title": "Introduction", "content": "Text here."}]
        result = _create_section_entities(sections)
        assert len(result) == 1
        assert result[0].title == "Introduction"
        assert result[0].content == "Text here."

    def test_dict_with_heading_text(self):
        """Test dict with heading and text keys."""
        sections = [{"heading": "Methods", "text": "Methods here."}]
        result = _create_section_entities(sections)
        assert len(result) == 1
        assert result[0].title == "Methods"
        assert result[0].content == "Methods here."

    def test_no_content_skipped(self):
        """Test section with no content is skipped."""
        sections = [{"title": "Empty"}, {"title": "Has", "content": "Yes"}]
        result = _create_section_entities(sections)
        assert len(result) == 1
        assert result[0].title == "Has"

    def test_section_entity_passthrough(self):
        """Test SectionEntity objects are passed through."""
        existing = SectionEntity(title="Existing", content="Content")
        sections = [existing, {"title": "New", "content": "New content"}]
        result = _create_section_entities(sections)
        assert len(result) == 2
        assert result[0] is existing

    def test_error_skipped(self):
        """Test items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.SectionEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_section_entities([{"title": "Bad", "content": "Bad"}])
            assert result == []

    def test_empty_list(self):
        """Test empty list."""
        assert _create_section_entities([]) == []


# =============================================================================
# _create_table_entities
# =============================================================================

class TestCreateTableEntities:
    """Tests for _create_table_entities."""

    def test_dict_with_label_caption(self):
        """Test dict with label and caption."""
        tables = [{"label": "Table 1", "caption": "Caption text"}]
        result = _create_table_entities(tables)
        assert len(result) == 1
        assert result[0].table_label == "Table 1"
        assert result[0].caption == "Caption text"

    def test_dict_with_table_label_title(self):
        """Test dict with table_label and title."""
        tables = [{"table_label": "T1", "title": "Title text"}]
        result = _create_table_entities(tables)
        assert len(result) == 1
        assert result[0].table_label == "T1"
        assert result[0].caption == "Title text"

    def test_table_entity_passthrough(self):
        """Test TableEntity objects are passed through."""
        existing = TableEntity(table_label="Existing", caption="Caption")
        tables = [existing]
        result = _create_table_entities(tables)
        assert len(result) == 1
        assert result[0] is existing

    def test_error_skipped(self):
        """Test items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.TableEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_table_entities([{"label": "Bad"}])
            assert result == []

    def test_empty_list(self):
        """Test empty list."""
        assert _create_table_entities([]) == []


# =============================================================================
# _create_figure_entities
# =============================================================================

class TestCreateFigureEntities:
    """Tests for _create_figure_entities."""

    def test_basic(self):
        """Test basic figure creation."""
        figures = [{"label": "Figure 1", "caption": "A scatter plot"}]
        result = _create_figure_entities(figures)
        assert len(result) == 1
        assert result[0].figure_label == "Figure 1"
        assert result[0].caption == "A scatter plot"

    def test_minimal(self):
        """Test figure with minimal data."""
        figures = [{}]
        result = _create_figure_entities(figures)
        assert len(result) == 1
        assert result[0].figure_label is None
        assert result[0].caption is None

    def test_non_dict_skipped(self):
        """Test non-dict entries are skipped."""
        figures = [{"label": "Fig 1"}, "string"]
        result = _create_figure_entities(figures)
        assert len(result) == 1

    def test_error_skipped(self):
        """Test items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.FigureEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_figure_entities([{"label": "Bad"}])
            assert result == []

    def test_empty_list(self):
        """Test empty list."""
        assert _create_figure_entities([]) == []


# =============================================================================
# _extract_entities_from_xml
# =============================================================================

class TestExtractEntitiesFromXml:
    """Tests for _extract_entities_from_xml."""

    def test_basic(self):
        """Test basic XML extraction."""
        xml_data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
                "journal": {"title": "Test Journal", "issn": "1234-5678"},
                "publication_year": 2024,
            },
            "authors": [{"full_name": "John Doe"}],
            "affiliations": [
                {
                    "id": "aff1",
                    "institution": "Univ of Testing",
                    "institution_ids": {"ROR": "https://ror.org/test"},
                    "country": "US",
                }
            ],
            "references": [
                {"title": "Ref 1", "source": "Journal", "year": "2023"}
            ],
            "sections": [{"title": "Intro", "content": "Text"}],
            "tables": [{"label": "T1", "caption": "Data"}],
            "figures": [{"label": "F1", "caption": "Plot"}],
        }
        result = _extract_entities_from_xml(xml_data, include_content=True)
        assert len(result) == 1
        entry = result[0]
        assert isinstance(entry["entity"], PaperEntity)
        assert entry["entity"].doi == "10.1234/test"
        assert entry["entity"].journal.title == "Test Journal"

        related = entry["related_entities"]
        assert len(related["authors"]) == 1
        assert len(related["institutions"]) == 1
        assert len(related["references"]) == 1
        assert len(related["sections"]) == 1
        assert len(related["tables"]) == 1
        assert len(related["figures"]) == 1

    def test_no_paper_key(self):
        """Test with no 'paper' key."""
        assert _extract_entities_from_xml({"sections": []}, True) == []

    def test_include_content_false(self):
        """Test with include_content=False."""
        xml_data = {
            "paper": {"title": "Test"},
            "sections": [{"title": "Intro", "content": "Text"}],
            "tables": [{"label": "T1", "caption": "Data"}],
            "figures": [{"label": "F1", "caption": "Plot"}],
            "references": [{"title": "Ref"}],
        }
        result = _extract_entities_from_xml(xml_data, include_content=False)
        related = result[0]["related_entities"]
        assert related["sections"] == []
        assert related["tables"] == []
        assert related["figures"] == []
        assert related["references"] == []

    def test_journal_string(self):
        """Test with journal as string."""
        xml_data = {
            "paper": {
                "title": "Test",
                "journal": "Nature",
            }
        }
        result = _extract_entities_from_xml(xml_data, True)
        assert result[0]["entity"].journal.title == "Nature"

    def test_affiliations_with_ids(self):
        """Test affiliations are used to build institution mapping."""
        xml_data = {
            "paper": {"title": "Test"},
            "affiliations": [
                {
                    "id": "aff1",
                    "institution": "Univ A",
                    "institution_ids": {"ROR": "ror1"},
                }
            ],
        }
        result = _extract_entities_from_xml(xml_data, True)
        related = result[0]["related_entities"]
        assert len(related["institutions"]) == 1
        assert related["institutions"][0].display_name == "Univ A"

    def test_affiliations_without_id_skipped(self):
        """Test affiliations without ID are skipped in mapping."""
        xml_data = {
            "paper": {"title": "Test"},
            "affiliations": [
                {"id": "aff1", "institution": "Univ A", "institution_ids": {"ROR": "ror1"}},
                {"institution": "No ID", "institution_ids": {"ROR": "ror2"}},
            ],
        }
        result = _extract_entities_from_xml(xml_data, True)
        related = result[0]["related_entities"]
        assert len(related["institutions"]) == 2  # Both still added as InstitutionEntities

    def test_affiliations_without_id_skipped_in_mapping(self):
        """Test affiliations without ID are skipped in mapping but still in entities."""
        xml_data = {
            "paper": {"title": "Test"},
            "affiliations": [
                {"institution": "No ID", "institution_ids": {"ROR": "ror2"}},
                {"id": "aff1", "institution": "Univ A", "institution_ids": {"ROR": "ror1"}},
            ],
        }
        result = _extract_entities_from_xml(xml_data, True)
        related = result[0]["related_entities"]
        assert len(related["institutions"]) == 2

    def test_affiliation_with_no_ids_or_name_skipped(self):
        """Test affiliation without IDs or name is skipped."""
        xml_data = {
            "paper": {"title": "Test"},
            "affiliations": [
                {"id": "aff1", "other": "data"},
            ],
        }
        result = _extract_entities_from_xml(xml_data, True)
        related = result[0]["related_entities"]
        assert len(related["institutions"]) == 0

    def test_multiple_author_keys(self):
        """Test fallback through author keys."""
        xml_data = {
            "paper": {"title": "Test"},
            "authors_detailed": [{"full_name": "Detailed Author"}],
        }
        result = _extract_entities_from_xml(xml_data, True)
        assert len(result[0]["related_entities"]["authors"]) == 1
        assert result[0]["related_entities"]["authors"][0].full_name == "Detailed Author"

    def test_authors_simple_fallback(self):
        """Test fallback to authors_simple."""
        xml_data = {
            "paper": {"title": "Test"},
            "authors_simple": [{"full_name": "Simple Author"}],
        }
        result = _extract_entities_from_xml(xml_data, True)
        assert len(result[0]["related_entities"]["authors"]) == 1

    def test_no_authors(self):
        """Test with no author keys."""
        xml_data = {"paper": {"title": "Test"}}
        result = _extract_entities_from_xml(xml_data, True)
        assert result[0]["related_entities"]["authors"] == []


# =============================================================================
# _determine_enrichment_data_structure
# =============================================================================

class TestDetermineEnrichmentDataStructure:
    """Tests for _determine_enrichment_data_structure."""

    def test_paper_key(self):
        """Test with direct 'paper' key."""
        data = {"paper": {"title": "Test"}, "authors": [{"name": "Author"}]}
        paper, authors = _determine_enrichment_data_structure(data)
        assert paper == {"title": "Test"}
        assert authors == [{"name": "Author"}]

    def test_merged_format(self):
        """Test with 'merged' key."""
        data = {"merged": {"title": "Merged"}}
        paper, authors = _determine_enrichment_data_structure(data)
        assert paper == {"title": "Merged"}
        assert authors == []

    def test_semantic_scholar_fallback(self):
        """Test with semantic_scholar key (when no merged)."""
        data = {"semantic_scholar": {"title": "SS"}}
        paper, authors = _determine_enrichment_data_structure(data)
        assert paper == {"title": "SS"}
        assert authors == []

    def test_merged_with_authors(self):
        """Test merged data with authors key (falls to else, returns None)."""
        data = {"merged": {"title": "Merged", "authors": [{"name": "Auth"}]}}
        paper, authors = _determine_enrichment_data_structure(data)
        assert paper is None
        assert authors == []

    def test_no_data(self):
        """Test with no matching keys."""
        paper, authors = _determine_enrichment_data_structure({"other": "data"})
        assert paper is None
        assert authors == []

    def test_paper_takes_precedence(self):
        """Test 'paper' key takes precedence over 'merged'."""
        data = {
            "paper": {"title": "Paper"},
            "merged": {"title": "Merged"},
        }
        paper, _ = _determine_enrichment_data_structure(data)
        assert paper == {"title": "Paper"}

    def test_empty_merged(self):
        """Test with empty merged."""
        data = {"merged": {}}
        paper, _ = _determine_enrichment_data_structure(data)
        assert paper is None


# =============================================================================
# _create_enrichment_paper_entity
# =============================================================================

class TestCreateEnrichmentPaperEntity:
    """Tests for _create_enrichment_paper_entity."""

    def test_basic(self):
        """Test basic enrichment paper entity."""
        paper_data = {
            "doi": "10.1234/test",
            "pmcid": "PMC1234567",
            "title": "Test Paper",
            "abstract": "Abstract",
            "year": 2024,
            "keywords": ["kw1"],
            "mesh_terms": ["Humans"],
            "topics": [{"id": "topic1"}],
        }
        enrichment_data = {}
        entity = _create_enrichment_paper_entity(paper_data, enrichment_data)
        assert entity.doi == "10.1234/test"
        assert entity.pmcid == "PMC1234567"
        assert entity.title == "Test Paper"
        assert entity.abstract == "Abstract"
        assert entity.publication_year == 2024
        assert entity.keywords == ["kw1"]
        assert entity.mesh_terms == ["Humans"]
        assert entity.topics == [{"id": "topic1"}]

    def test_with_journal_dict(self):
        """Test with journal as dict."""
        paper_data = {
            "title": "Test",
            "journal": {"name": "Nature", "issn": "0028-0836", "publisher": "NPG"},
        }
        entity = _create_enrichment_paper_entity(paper_data, {})
        assert entity.journal.title == "Nature"
        assert entity.journal.issn == "0028-0836"
        assert entity.journal.publisher == "NPG"

    def test_with_journal_biblio(self):
        """Test with biblio as journal info."""
        paper_data = {
            "title": "Test",
            "biblio": {"name": "Science", "issn": "0036-8075"},
        }
        entity = _create_enrichment_paper_entity(paper_data, {})
        assert entity.journal.title == "Science"

    def test_with_journal_string(self):
        """Test with journal as string."""
        paper_data = {"title": "Test", "journal": "Nature"}
        entity = _create_enrichment_paper_entity(paper_data, {})
        assert entity.journal.title == "Nature"

    def test_journal_not_dict_or_str(self):
        """Test with journal as unexpected type."""
        paper_data = {"title": "Test", "journal": 123}
        entity = _create_enrichment_paper_entity(paper_data, {})
        assert entity.journal is None

    def test_doi_from_enrichment_fallback(self):
        """Test DOI falls back to enrichment_data."""
        paper_data = {}
        enrichment_data = {"doi": "10.1234/fallback"}
        entity = _create_enrichment_paper_entity(paper_data, enrichment_data)
        assert entity.doi == "10.1234/fallback"

    def test_pmid_from_external_ids(self):
        """Test pmid from external_ids."""
        paper_data = {"external_ids": {"pmid": "12345678"}}
        entity = _create_enrichment_paper_entity(paper_data, {})
        assert entity.pmid == "12345678"


# =============================================================================
# _create_enrichment_author_entities
# =============================================================================

class TestCreateEnrichmentAuthorEntities:
    """Tests for _create_enrichment_author_entities."""

    def test_dict_author(self):
        """Test dict-based author."""
        result = _create_enrichment_author_entities([
            {"name": "John Smith", "orcid": "0000-0002-1825-0097", "affiliation": "Univ A"}
        ])
        assert len(result) == 1
        assert result[0].full_name == "John Smith"
        assert result[0].orcid == "0000-0002-1825-0097"
        assert result[0].affiliation_text == "Univ A"

    def test_dict_with_full_name(self):
        """Test dict with full_name key."""
        result = _create_enrichment_author_entities([
            {"full_name": "Jane Doe"}
        ])
        assert result[0].full_name == "Jane Doe"

    def test_string_author(self):
        """Test string author."""
        result = _create_enrichment_author_entities(["John Smith"])
        assert len(result) == 1
        assert result[0].full_name == "John Smith"
        assert result[0].orcid is None
        assert result[0].affiliation_text is None

    def test_invalid_type_skipped(self):
        """Test invalid types skipped."""
        result = _create_enrichment_author_entities(["Valid", 123, None, {"name": "Also Valid"}])
        assert len(result) == 2

    def test_empty_list(self):
        """Test empty list."""
        assert _create_enrichment_author_entities([]) == []

    def test_error_skipped(self):
        """Test items causing errors are skipped."""
        with patch(
            "pyeuropepmc.mappers.processors.AuthorEntity",
            side_effect=[Exception("Boom")],
        ):
            result = _create_enrichment_author_entities([{"name": "Bad"}])
            assert result == []


# =============================================================================
# _extract_entities_from_enrichment
# =============================================================================

class TestExtractEntitiesFromEnrichment:
    """Tests for _extract_entities_from_enrichment."""

    def test_paper_level(self):
        """Test paper-level extraction."""
        data = {
            "paper": {
                "doi": "10.1234/test",
                "title": "Test Paper",
            },
            "authors": [{"name": "John Doe"}],
        }
        result = _extract_entities_from_enrichment(data)
        assert len(result) == 1
        assert isinstance(result[0]["entity"], PaperEntity)
        assert result[0]["entity"].doi == "10.1234/test"
        assert len(result[0]["related_entities"]["authors"]) == 1

    def test_author_level(self):
        """Test author-level extraction."""
        data = {
            "authors": [
                {"full_name": "John Doe", "orcid": "0000-0002-1825-0097"},
            ]
        }
        result = _extract_entities_from_enrichment(data)
        assert len(result) == 1
        assert isinstance(result[0]["entity"], AuthorEntity)
        assert result[0]["entity"].full_name == "John Doe"
        assert result[0]["entity"].orcid == "0000-0002-1825-0097"

    def test_author_level_error_skipped(self):
        """Test author-level with error skipped."""
        data = {
            "authors": [
                {"full_name": "Good"},
                None,  # Will cause error when entity is created
            ]
        }
        result = _extract_entities_from_enrichment(data)
        assert len(result) == 1
        assert result[0]["entity"].full_name == "Good"

    def test_empty_data(self):
        """Test with empty data."""
        assert _extract_entities_from_enrichment({}) == []

    def test_no_authors_key_when_no_paper(self):
        """Test with neither paper nor authors."""
        data = {"other": "data"}
        result = _extract_entities_from_enrichment(data)
        assert result == []
