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


def _expected_author_affiliations(document):
    """The <aff> elements of the article's own front matter, editors' aside.

    An editor's affiliation is cited by the editor's <contrib> and by no
    author's, which is what tells the two apart at <article-meta> level; in a
    <contrib-group> of editors it is the group that says so. Every other
    affiliation belongs to the authors, including one no <xref> cites.
    """
    scope = _own_front(document)
    editors = [
        c for c in scope.findall(".//contrib") if c.get("contrib-type") not in (None, "author")
    ]
    editor_rids = {x.get("rid") for c in editors for x in c.findall(".//xref[@ref-type='aff']")}
    author_rids = {
        x.get("rid")
        for c in _expected_author_contribs(document)
        for x in c.findall(".//xref[@ref-type='aff']")
    }
    editor_groups = [
        g
        for g in scope.findall(".//contrib-group")
        if g.findall("contrib") and all(c in editors for c in g.findall("contrib"))
    ]
    in_editor_group = {id(a) for g in editor_groups for a in g.iter("aff")}
    return [
        a
        for a in scope.iter("aff")
        if id(a) not in in_editor_group
        and not (a.get("id") in editor_rids and a.get("id") not in author_rids)
    ]


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
    def test_every_author_affiliation_is_returned(self, document):
        affs = _expected_author_affiliations(document)
        if not affs:
            pytest.skip(f"{document.pmcid} has no <aff>")
        got = document.parser.extract_affiliations()
        assert [a.get("id") for a in got] == [a.get("id") for a in affs]

    def test_no_editor_or_sub_article_affiliations(self, document):
        """`.//aff` also matched the editors' and every reviewer report's.

        PMC11687933 has 8 author affiliations and returned 33: the 2 editor
        ones and 23 from the peer-review <sub-article> elements as well.
        """
        expected = _expected_author_affiliations(document)
        everything = document.root.findall(".//aff")
        if len(everything) == len(expected):
            pytest.skip(f"{document.pmcid} has no editor or sub-article <aff>")
        assert len(document.parser.extract_affiliations()) == len(expected)

    def test_affiliation_text_has_no_label_or_institution_id(self, document):
        """A ROR URL or a GRID code ran into the institution name.

        Compared with the affiliation's own text minus those subtrees, not by
        looking for the label as a substring: a label "1" also occurs in the
        postal code "Singapore 117597".
        """
        skip = {"label", "institution-id"}

        def text_without(node):
            parts = [node.text or ""]
            for child in node:
                if child.tag not in skip:
                    parts.append(text_without(child))
                parts.append(child.tail or "")
            return "".join(parts)

        checked = 0
        for aff, got in zip(
            _expected_author_affiliations(document),
            document.parser.extract_affiliations(),
            strict=True,
        ):
            if not any(e.tag in skip for e in aff.iter()):
                continue
            checked += 1
            assert squash(got.get("text")) == squash(text_without(aff)), (
                f"{document.pmcid} {aff.get('id')}: {got.get('text')!r}"
            )
        if not checked:
            pytest.skip(f"{document.pmcid} has no <label> or <institution-id> in an <aff>")

    def test_every_figure_is_returned(self, document):
        figs = document.root.findall(".//fig")
        if not figs:
            pytest.skip(f"{document.pmcid} has no <fig>")
        assert len(document.parser.extract_figures()) == len(figs)


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


class TestLicence:
    def test_licence_url_and_text_when_a_licence_is_present(self, document):
        licences = document.root.findall(".//license")
        if not licences:
            pytest.skip(f"{document.pmcid} has no <license>")
        got = document.parser.extract_license()
        assert got, f"{document.pmcid}: <license> present but nothing extracted"
        assert got.get("text"), f"{document.pmcid}: no licence text"


def _article_meta(document):
    return _own_front(document).find("./article-meta")


class TestPagination:
    """Pagination is the article's own, or absent.

    Every one of `volume`, `issue`, `fpage` and `lpage` also occurs in each
    reference, and the reference list is part of the document, so a `.//`
    search filled these fields from the bibliography whenever the article
    itself had nothing to give.
    """

    def test_pages_are_the_articles_own(self, document):
        meta = _article_meta(document)
        if meta is None:
            pytest.skip(f"{document.pmcid} has no <article-meta>")
        fpage = meta.findtext("fpage")
        lpage = meta.findtext("lpage")
        expected = f"{fpage}-{lpage}" if fpage and lpage else (fpage or None)
        assert document.parser.extract_metadata().get("pages") == expected

    def test_elocation_id_is_extracted(self, document):
        meta = _article_meta(document)
        if meta is None or meta.findtext("elocation-id") is None:
            pytest.skip(f"{document.pmcid} has no <elocation-id>")
        assert (
            document.parser.extract_metadata().get("elocation_id")
            == meta.findtext("elocation-id").strip()
        )

    def test_volume_and_issue_are_the_articles_own(self, document):
        meta = _article_meta(document)
        if meta is None:
            pytest.skip(f"{document.pmcid} has no <article-meta>")
        got = document.parser.extract_metadata()
        for field in ("volume", "issue"):
            expected = meta.findtext(field)
            assert got.get(field) == (expected.strip() if expected else None), field


class TestArticleMetadata:
    def test_article_type_is_reported(self, document):
        """`.//article` never matches: the root element is the <article>."""
        expected = document.root.get("article-type")
        if not expected:
            pytest.skip(f"{document.pmcid} has no article-type")
        assert document.parser.extract_article_categories().get("article_type") == expected

    def test_keywords_are_the_articles_own(self, document):
        """A peer-review <sub-article> tags keywords of its own."""
        expected = [
            normalise("".join(k.itertext()))
            for k in _own_front(document).iter("kwd")
            if normalise("".join(k.itertext()))
        ]
        if not expected:
            pytest.skip(f"{document.pmcid} has no <kwd>")
        assert document.parser.extract_keywords() == expected

    def test_self_uri_is_not_an_earlier_version(self, document):
        """eLife lists the preprint and each reviewed preprint first."""
        uris = list(_own_front(document).iter("self-uri"))
        if not uris:
            pytest.skip(f"{document.pmcid} has no <self-uri>")
        href = "{http://www.w3.org/1999/xlink}href"
        expected = next(
            (
                u.get(href, u.get("href"))
                for u in uris
                if u.get(href, u.get("href"))
                and "preprint" not in (u.get("content-type") or "").lower()
            ),
            None,
        )
        if expected is None:
            pytest.skip(f"{document.pmcid} has only preprint <self-uri>")
        assert document.parser.extract_metadata().get("self_uri") == expected

    def test_every_award_id_of_a_group_is_kept(self, document):
        """Only the first survived; a group routinely names several grants."""
        groups = [
            g for g in document.root.iter("award-group") if len(g.findall(".//award-id")) > 1
        ]
        if not groups:
            pytest.skip(f"{document.pmcid} has no award-group with several award IDs")
        got = document.parser.extract_metadata().get("funding") or []
        found = {tuple(entry.get("award_ids") or []) for entry in got}
        for group in groups:
            expected = tuple(
                normalise(e.text) for e in group.findall(".//award-id") if normalise(e.text)
            )
            assert expected in found, f"{document.pmcid}: {expected} missing from {found}"
