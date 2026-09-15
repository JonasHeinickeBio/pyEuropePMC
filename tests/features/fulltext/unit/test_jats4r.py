"""Unit tests for pyeuropepmc.features.fulltext.extensions.jats4r."""

from __future__ import annotations

import defusedxml.ElementTree as DefusedET
import pytest

from pyeuropepmc.features.fulltext.extensions.jats4r import (
    JATS4RValidator,
    ValidationFinding,
    ValidationReport,
)


def _validator(xml: str) -> JATS4RValidator:
    return JATS4RValidator(root=DefusedET.fromstring(xml))


def _rule_ids(report: ValidationReport) -> set[str]:
    return {f.rule_id for f in report.findings}


class TestValidationFinding:
    def test_to_dict(self):
        finding = ValidationFinding(
            rule_id="X-01", severity="error", message="m", category="c", suggestion="s"
        )
        d = finding.to_dict()
        assert d["rule_id"] == "X-01"
        assert d["severity"] == "error"


class TestValidationReport:
    def test_no_findings_perfect_score(self):
        report = ValidationReport()
        assert report.score == 1.0

    def test_score_decreases_with_findings(self):
        report = ValidationReport()
        report.add_finding(ValidationFinding(rule_id="X", severity="error", message="m"))
        assert report.score < 1.0

    def test_score_never_negative(self):
        report = ValidationReport()
        for _ in range(50):
            report.add_finding(ValidationFinding(rule_id="X", severity="error", message="m"))
        assert report.score == 0.0

    def test_categories_grouped(self):
        report = ValidationReport()
        report.add_finding(
            ValidationFinding(rule_id="X", severity="info", message="m", category="authors")
        )
        assert "authors" in report.categories
        assert len(report.categories["authors"]) == 1

    def test_to_dict_counts_by_severity(self):
        report = ValidationReport()
        report.add_finding(ValidationFinding(rule_id="A", severity="error", message="m"))
        report.add_finding(ValidationFinding(rule_id="B", severity="warning", message="m"))
        report.add_finding(ValidationFinding(rule_id="C", severity="info", message="m"))
        d = report.to_dict()
        assert d["errors"] == 1
        assert d["warnings"] == 1
        assert d["infos"] == 1
        assert d["total_findings"] == 3


class TestValidateOverall:
    def test_no_root_raises(self):
        validator = JATS4RValidator()
        with pytest.raises(Exception):  # noqa: B017
            validator.validate()

    def test_fully_compliant_article_has_few_findings(self):
        xml = """<article>
          <front>
            <article-meta>
              <contrib-group>
                <contrib contrib-type="author" id="a1">
                  <contrib-id contrib-id-type="orcid">0000-0002-1825-0097</contrib-id>
                  <xref ref-type="corresp"/>
                </contrib>
                <aff id="aff1">
                  <institution>MIT</institution>
                  <country>USA</country>
                </aff>
              </contrib-group>
              <abstract>
                <p>An abstract paragraph.</p>
              </abstract>
              <funding-group>
                <award-group>
                  <funding-source>NIH</funding-source>
                  <award-id>R01-12345</award-id>
                </award-group>
              </funding-group>
            </article-meta>
          </front>
          <back>
            <sec sec-type="data-availability">
              <title>Data Availability</title>
              <p>Data is available upon request.</p>
            </sec>
            <ref-list>
              <ref id="r1">
                <element-citation>
                  <pub-id pub-id-type="doi">10.1234/x</pub-id>
                </element-citation>
              </ref>
            </ref-list>
          </back>
        </article>"""
        validator = _validator(xml)
        report = validator.validate()
        assert report.score > 0.8

    def test_empty_article_has_many_findings(self):
        validator = _validator("<article/>")
        report = validator.validate()
        ids = _rule_ids(report)
        assert "AUTH-01" in ids
        assert "AFF-01" in ids
        assert "ABST-01" in ids
        assert "FUND-01" in ids
        assert "CITE-01" in ids
        assert "DATA-01" in ids
        assert report.score < 1.0


class TestValidateAuthors:
    def test_missing_authors(self):
        report = ValidationReport()
        _validator("<article/>")._validate_authors(report)
        assert "AUTH-01" in _rule_ids(report)

    def test_missing_orcid_flagged(self):
        xml = '<article><contrib contrib-type="author" id="a1"/></article>'
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-02" in _rule_ids(report)

    def test_orcid_present_not_flagged(self):
        xml = """<article><contrib contrib-type="author" id="a1">
            <contrib-id contrib-id-type="orcid">0000-0002-1825-0097</contrib-id>
        </contrib></article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-02" not in _rule_ids(report)

    def test_group_level_author_type_not_flagged(self):
        """<contrib-group content-type="author"> is a valid authorship form.

        It was the majority dialect in the sampled Europe PMC corpus (550 of
        1,000 files) and produced 550 of AUTH-01's 553 fires (#203).
        """
        xml = """<article><contrib-group content-type="author">
            <contrib><name><surname>Doe</surname><given-names>J</given-names></name></contrib>
        </contrib-group></article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-01" not in _rule_ids(report)

    def test_group_level_authors_reach_auth02(self):
        """AUTH-01 returned early, so the majority dialect never saw AUTH-02."""
        xml = """<article><contrib-group content-type="author">
            <contrib id="a1"><name><surname>Doe</surname></name></contrib>
        </contrib-group></article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-02" in _rule_ids(report)

    def test_mixed_dialects_counted_once_each(self):
        """Both forms in one document: two authors, not three and not one."""
        xml = """<article>
            <contrib-group><contrib contrib-type="author" id="a1"/></contrib-group>
            <contrib-group content-type="author"><contrib id="a2"/></contrib-group>
        </article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert [f.rule_id for f in report.findings].count("AUTH-02") == 2

    def test_explicit_editor_in_author_group_is_not_an_author(self):
        """A contrib carrying its own contrib-type keeps it, group regardless."""
        xml = """<article><contrib-group content-type="author">
            <contrib contrib-type="editor"><name><surname>E</surname></name></contrib>
        </contrib-group></article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-01" in _rule_ids(report)

    def test_orcid_via_ext_link_not_flagged(self):
        xml = """<article><contrib contrib-type="author" id="a1">
            <ext-link ext-link-type="orcid">0000-0002-1825-0097</ext-link>
        </contrib></article>"""
        report = ValidationReport()
        _validator(xml)._validate_authors(report)
        assert "AUTH-02" not in _rule_ids(report)


class TestValidateAffiliations:
    def test_missing_affiliations(self):
        report = ValidationReport()
        _validator("<article/>")._validate_affiliations(report)
        assert "AFF-01" in _rule_ids(report)

    def test_missing_institution(self):
        xml = '<article><aff id="a1"><country>USA</country></aff></article>'
        report = ValidationReport()
        _validator(xml)._validate_affiliations(report)
        assert "AFF-02" in _rule_ids(report)

    def test_missing_country(self):
        xml = '<article><aff id="a1"><institution>MIT</institution></aff></article>'
        report = ValidationReport()
        _validator(xml)._validate_affiliations(report)
        assert "AFF-03" in _rule_ids(report)

    def test_complete_affiliation_not_flagged(self):
        xml = """<article><aff id="a1">
            <institution>MIT</institution><country>USA</country>
        </aff></article>"""
        report = ValidationReport()
        _validator(xml)._validate_affiliations(report)
        assert "AFF-02" not in _rule_ids(report)
        assert "AFF-03" not in _rule_ids(report)


class TestValidateAbstract:
    def test_missing_abstract(self):
        report = ValidationReport()
        _validator("<article/>")._validate_abstract(report)
        assert "ABST-01" in _rule_ids(report)

    def test_abstract_without_paragraphs(self):
        xml = "<article><abstract/></article>"
        report = ValidationReport()
        _validator(xml)._validate_abstract(report)
        assert "ABST-02" in _rule_ids(report)

    def test_structured_abstract_without_sections(self):
        xml = '<article><abstract abstract-type="structured"><p>x</p></abstract></article>'
        report = ValidationReport()
        _validator(xml)._validate_abstract(report)
        assert "ABST-03" in _rule_ids(report)

    def test_structured_abstract_with_sections_not_flagged(self):
        xml = (
            '<article><abstract abstract-type="structured">'
            "<sec><title>Background</title><p>x</p></sec>"
            "</abstract></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_abstract(report)
        assert "ABST-03" not in _rule_ids(report)


class TestValidateFunding:
    def test_no_funding(self):
        report = ValidationReport()
        _validator("<article/>")._validate_funding(report)
        assert "FUND-01" in _rule_ids(report)

    def test_missing_award_id(self):
        xml = "<article><funding-group><funding-source>NIH</funding-source></funding-group></article>"
        report = ValidationReport()
        _validator(xml)._validate_funding(report)
        assert "FUND-02" in _rule_ids(report)

    def test_missing_funding_source(self):
        xml = "<article><funding-group><award-id>1</award-id></funding-group></article>"
        report = ValidationReport()
        _validator(xml)._validate_funding(report)
        assert "FUND-03" in _rule_ids(report)

    def test_funder_name_satisfies_source_check(self):
        xml = (
            "<article><funding-group><funder-name>NIH</funder-name>"
            "<award-id>1</award-id></funding-group></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_funding(report)
        assert "FUND-03" not in _rule_ids(report)


class TestValidateCitations:
    def test_no_references(self):
        report = ValidationReport()
        _validator("<article/>")._validate_citations(report)
        assert "CITE-01" in _rule_ids(report)

    def test_missing_citation_element(self):
        xml = '<article><ref id="r1"/></article>'
        report = ValidationReport()
        _validator(xml)._validate_citations(report)
        assert "CITE-02" in _rule_ids(report)

    def test_missing_doi_or_pmid(self):
        xml = '<article><ref id="r1"><element-citation/></ref></article>'
        report = ValidationReport()
        _validator(xml)._validate_citations(report)
        assert "CITE-03" in _rule_ids(report)

    def test_pmid_satisfies_identifier_check(self):
        xml = (
            '<article><ref id="r1"><element-citation>'
            '<pub-id pub-id-type="pmid">123</pub-id>'
            "</element-citation></ref></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_citations(report)
        assert "CITE-03" not in _rule_ids(report)

    def test_mixed_citation_type_recognized(self):
        xml = (
            '<article><ref id="r1"><mixed-citation>'
            '<pub-id pub-id-type="doi">10.1/x</pub-id>'
            "</mixed-citation></ref></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_citations(report)
        assert "CITE-02" not in _rule_ids(report)
        assert "CITE-03" not in _rule_ids(report)


class TestValidateDataAvailability:
    def test_missing(self):
        report = ValidationReport()
        _validator("<article/>")._validate_data_availability(report)
        assert "DATA-01" in _rule_ids(report)

    def test_found_via_section_title(self):
        xml = "<article><sec><title>Data Availability Statement</title></sec></article>"
        report = ValidationReport()
        _validator(xml)._validate_data_availability(report)
        assert "DATA-01" not in _rule_ids(report)

    def test_found_via_fn_type(self):
        xml = '<article><fn fn-type="data-availability">x</fn></article>'
        report = ValidationReport()
        _validator(xml)._validate_data_availability(report)
        assert "DATA-01" not in _rule_ids(report)

    def test_found_via_sec_type(self):
        xml = '<article><sec sec-type="data-availability"/></article>'
        report = ValidationReport()
        _validator(xml)._validate_data_availability(report)
        assert "DATA-01" not in _rule_ids(report)


class TestValidateOrcid:
    def test_valid_format_not_flagged(self):
        xml = (
            '<article><contrib-id contrib-id-type="orcid">'
            "0000-0002-1825-0097</contrib-id></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_orcid(report)
        assert "ORCID-01" not in _rule_ids(report)

    def test_invalid_format_flagged(self):
        xml = '<article><contrib-id contrib-id-type="orcid">not-an-orcid</contrib-id></article>'
        report = ValidationReport()
        _validator(xml)._validate_orcid(report)
        assert "ORCID-01" in _rule_ids(report)

    def test_x_checksum_digit_accepted(self):
        xml = (
            '<article><contrib-id contrib-id-type="orcid">'
            "0000-0002-1825-009X</contrib-id></article>"
        )
        report = ValidationReport()
        _validator(xml)._validate_orcid(report)
        assert "ORCID-01" not in _rule_ids(report)


class TestValidatePeerReview:
    def test_no_sub_articles_no_findings(self):
        report = ValidationReport()
        _validator("<article/>")._validate_peer_review(report)
        assert report.findings == []

    def test_recognized_review_type_not_flagged(self):
        xml = '<article><sub-article article-type="referee-report"/></article>'
        report = ValidationReport()
        _validator(xml)._validate_peer_review(report)
        assert "REV-01" not in _rule_ids(report)

    def test_unrecognized_type_flagged(self):
        xml = '<article><sub-article article-type="commentary"/></article>'
        report = ValidationReport()
        _validator(xml)._validate_peer_review(report)
        assert "REV-01" in _rule_ids(report)


class TestGetElemText:
    def test_none_returns_empty(self):
        assert JATS4RValidator._get_elem_text(None) == ""

    def test_extracts_nested_text(self):
        elem = DefusedET.fromstring("<p>Hello <b>world</b>!</p>")
        text = JATS4RValidator._get_elem_text(elem)
        assert "Hello" in text and "world" in text and "!" in text
