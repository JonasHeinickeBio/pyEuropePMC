"""Extracted values must match what the document actually says.

Coverage tests - "is the field populated?" - passed on every one of these
documents while the values were wrong. References reported the second and
third authors as the title and journal (#226); the author list included the
peer reviewers, once per report, and the editors (#227). Both were invisible
until the values themselves were compared against the XML.

Expectations are derived from the article's own front matter, never from the
whole document: `.//article-meta` also matches the metadata of every
<sub-article>, so an unscoped expectation counts reviewers too and agrees
with a parser that is wrong in the same way.
"""

from __future__ import annotations

import re

import pytest

from .conftest import normalise, squash

pytestmark = [pytest.mark.unit]

ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


def _own_front(document):
    front = document.root.find("./front")
    return front if front is not None else document.root


def _expected_author_contribs(document):
    scope = _own_front(document)
    contribs = [
        c
        for c in scope.findall(".//contrib[@contrib-type='author']")
        if c.find(".//surname") is not None
    ]
    if not contribs:
        contribs = [
            c
            for group in scope.findall(".//contrib-group[@content-type='author']")
            for c in group.findall("contrib")
            if c.find(".//surname") is not None
        ]
    return contribs


class TestTitle:
    def test_matches_the_article_title_element(self, document):
        """Exact, not merely non-empty: `PM<sub>2.5</sub>` read as "PM 2.5"."""
        element = document.root.find(".//article-meta//article-title")
        if element is None:
            pytest.skip(f"{document.pmcid} has no <article-title>")
        expected = normalise("".join(element.itertext()))
        assert normalise(document.parser.extract_metadata().get("title")) == expected


class TestAuthors:
    def test_surnames_match_the_front_matter_in_order(self, document):
        contribs = _expected_author_contribs(document)
        if not contribs:
            pytest.skip(f"{document.pmcid} has no tagged authors")
        expected = [normalise(c.findtext(".//surname")) for c in contribs]
        got = [normalise(a.get("surname")) for a in document.parser.extract_authors_detailed()]
        assert got == expected

    def test_no_reviewers_from_sub_articles(self, document):
        """A peer-review <sub-article> carries its own <contrib> elements."""
        reviewers = {
            normalise(c.findtext(".//surname"))
            for sub in document.root.findall(".//sub-article")
            for c in sub.findall(".//contrib")
            if c.find(".//surname") is not None
        }
        expected = {
            normalise(c.findtext(".//surname")) for c in _expected_author_contribs(document)
        }
        only_reviewers = reviewers - expected
        if not only_reviewers:
            pytest.skip(f"{document.pmcid} has no reviewer-only surnames to confuse")
        got = {normalise(a.get("surname")) for a in document.parser.extract_authors_detailed()}
        assert not (got & only_reviewers)

    def test_orcids_are_bare_identifiers(self, document):
        """Not the https://orcid.org/... URL the XML carries."""
        found = [
            a.get("orcid") for a in document.parser.extract_authors_detailed() if a.get("orcid")
        ]
        if not found:
            pytest.skip(f"{document.pmcid} has no ORCIDs")
        assert all(ORCID.match(o.strip()) for o in found), found


class TestAffiliationsAndFigures:
    def test_every_affiliation_is_returned(self, document):
        affs = document.root.findall(".//article-meta//aff")
        if not affs:
            pytest.skip(f"{document.pmcid} has no <aff>")
        assert len(document.parser.extract_affiliations()) == len(affs)

    def test_every_figure_is_returned(self, document):
        figs = document.root.findall(".//fig")
        if not figs:
            pytest.skip(f"{document.pmcid} has no <fig>")
        assert len(document.parser.extract_figures()) == len(figs)


XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _citations(document):
    """(ref, citation) for each <ref> of the article's own reference list."""
    for ref_elem in document.root.findall("./back//ref"):
        for tag in ("element-citation", "mixed-citation", "nlm-citation", "citation"):
            citation = ref_elem.find(f".//{tag}")
            if citation is not None:
                yield ref_elem, citation
                break


class TestReferences:
    def test_structured_citations_keep_their_own_title(self, document):
        """A <mixed-citation> with structure was regex-guessed and mangled."""
        checked = 0
        for ref_elem in document.root.findall(".//ref"):
            citation = ref_elem.find("mixed-citation")
            if citation is None:
                continue
            article_title = citation.find(".//article-title")
            if article_title is None:
                continue
            expected = normalise("".join(article_title.itertext())).rstrip(".").lower()
            match = next(
                (
                    r
                    for r in document.parser.extract_references()
                    if r.get("id") == ref_elem.get("id")
                ),
                None,
            )
            if match is None:
                continue
            checked += 1
            assert normalise(match.get("title")).rstrip(".").lower() == expected, (
                f"{document.pmcid} ref {ref_elem.get('id')}: "
                f"got {match.get('title')!r}, expected {expected!r}"
            )
        if not checked:
            pytest.skip(f"{document.pmcid} has no structured <mixed-citation>")

    def test_all_authors_of_a_structured_citation_are_kept(self, document):
        """Only the first survived; the rest landed in title and source."""
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem in document.root.findall(".//ref"):
            citation = ref_elem.find("mixed-citation")
            if citation is None:
                continue
            names = citation.findall(".//person-group[@person-group-type='author']/name")
            if len(names) < 2:
                continue
            got = references.get(ref_elem.get("id"), {}).get("authors") or ""
            checked += 1
            for name in names:
                surname = normalise(name.findtext("surname"))
                if surname:
                    assert squash(surname) in squash(got), (
                        f"{document.pmcid} ref {ref_elem.get('id')}: {surname!r} missing"
                    )
        if not checked:
            pytest.skip(f"{document.pmcid} has no multi-author structured citation")

    def test_surname_and_given_names_are_kept_apart(self, document):
        """PLOS lists bare <name> children, which came back as "NewtonSI"."""
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem, citation in _citations(document):
            name = next(
                (
                    n
                    for n in citation.iter("name")
                    if n.findtext("surname") and n.findtext("given-names")
                ),
                None,
            )
            if name is None:
                continue
            checked += 1
            expected = (
                f"{normalise(name.findtext('surname'))}, {normalise(name.findtext('given-names'))}"
            )
            got = references.get(ref_elem.get("id"), {}).get("authors") or ""
            assert expected in normalise(got), (
                f"{document.pmcid} ref {ref_elem.get('id')}: {got!r}"
            )
        if not checked:
            pytest.skip(f"{document.pmcid} has no citation with a <name>")

    def test_tagged_pages_and_identifiers_are_not_overwritten(self, document):
        """The text pass replaced "385-430" with "385" and ran a DOI into its PMID."""
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem, citation in _citations(document):
            got = references.get(ref_elem.get("id"), {})
            fpage, lpage = citation.findtext(".//fpage"), citation.findtext(".//lpage")
            if fpage:
                checked += 1
                expected = f"{normalise(fpage)}-{normalise(lpage)}" if lpage else normalise(fpage)
                assert got.get("pages") == expected, f"{document.pmcid} {ref_elem.get('id')}"
            for kind in ("doi", "pmid"):
                tagged = citation.findtext(f".//pub-id[@pub-id-type='{kind}']")
                if tagged:
                    checked += 1
                    assert got.get(kind) == normalise(tagged), (
                        f"{document.pmcid} {ref_elem.get('id')}"
                    )
        if not checked:
            pytest.skip(f"{document.pmcid} has no tagged pages or identifiers in its references")

    def test_identifiers_in_ext_link_targets_are_read(self, document):
        """BMC puts a PMID only in <ext-link xlink:href>; 0 of 45 were found."""
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem, citation in _citations(document):
            for link in citation.iter("ext-link"):
                kind = {"pmid": "pmid", "pmcid": "pmcid", "doi": "doi"}.get(
                    link.get("ext-link-type") or ""
                )
                if kind is None or citation.find(f".//pub-id[@pub-id-type='{kind}']") is not None:
                    continue
                target = normalise(link.text) or normalise(link.get(XLINK_HREF))
                if not target:
                    continue
                checked += 1
                got = references.get(ref_elem.get("id"), {}).get(kind)
                assert got == target, f"{document.pmcid} {ref_elem.get('id')} {kind}: {got!r}"
        if not checked:
            pytest.skip(f"{document.pmcid} has no identifier <ext-link> in its references")

    def test_collaboration_authors_are_kept(self, document):
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem, citation in _citations(document):
            for collab in citation.findall(".//person-group[@person-group-type='author']/collab"):
                checked += 1
                got = references.get(ref_elem.get("id"), {}).get("authors") or ""
                assert normalise("".join(collab.itertext())) in normalise(got)
        if not checked:
            pytest.skip(f"{document.pmcid} has no <collab> author in its references")

    def test_software_and_data_are_titled_by_their_data_title(self, document):
        """The title came back as the repository: "GitHub", "CRAN"."""
        checked = 0
        references = {r.get("id"): r for r in document.parser.extract_references()}
        for ref_elem, citation in _citations(document):
            data_title = citation.find(".//data-title")
            if data_title is None or citation.find(".//article-title") is not None:
                continue
            checked += 1
            got = references.get(ref_elem.get("id"), {}).get("title")
            assert normalise(got) == normalise("".join(data_title.itertext()))
        if not checked:
            pytest.skip(f"{document.pmcid} has no <data-title> citation")


class TestLicence:
    def test_licence_url_and_text_when_a_licence_is_present(self, document):
        licences = document.root.findall(".//license")
        if not licences:
            pytest.skip(f"{document.pmcid} has no <license>")
        got = document.parser.extract_license()
        assert got, f"{document.pmcid}: <license> present but nothing extracted"
        assert got.get("text"), f"{document.pmcid}: no licence text"
