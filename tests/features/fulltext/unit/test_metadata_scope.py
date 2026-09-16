"""Metadata is the article's own, found by comparing values against the XML.

Every field in <article-meta> has a namesake somewhere else in the document.
`<volume>`, `<issue>`, `<fpage>` and `<lpage>` occur in each reference, a
`<related-article>` carries the companion paper's, and a peer-review
`<sub-article>` has front matter of its own. Searched with `.//`, all of
them answered:

* an article paginated with `<elocation-id>` - which was never extracted at
  all - took the page range of its first reference. 4 of the 5 measured
  articles were affected; PMC11671585 reported "1-22" for elocation-id 354.
* PMC13567752 reported pages "e0357759-e0357759", its companion's
  elocation-id, from the `<related-article>` next to its own.
* an eLife article's author keywords ended with "Compelling" and
  "Important", the assessment vocabulary of its review `<sub-article>`.

Two more, unrelated to scope: `.//article` never matches, because the root
element *is* the `<article>`, so `article_type` was never set; and only the
first `<award-id>` of an award group survived.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

ELOCATION_ONLY = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article"><front><article-meta>
  <volume>9</volume>
  <elocation-id>354</elocation-id>
  <kwd-group><kwd>Structural biology</kwd></kwd-group>
</article-meta></front>
<body><sec><p>Body.</p></sec></body>
<back><ref-list><ref id="CR1"><element-citation>
  <source>J. Bacteriol.</source><volume>199</volume><issue>7</issue>
  <fpage>1</fpage><lpage>22</lpage>
</element-citation></ref></ref-list></back>
<sub-article article-type="editor-report"><front-stub>
  <kwd-group><kwd>Compelling</kwd><kwd>Important</kwd></kwd-group>
</front-stub><body><p>Assessment.</p></body></sub-article>
</article>"""

RELATED_ARTICLE = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article"><front><article-meta>
  <volume>21</volume><issue>9</issue>
  <elocation-id>e0357759</elocation-id>
  <related-article related-article-type="peer-reviewed-article">
    <volume>21</volume><issue>9</issue>
    <fpage>e0357759</fpage><lpage>e0357759</lpage>
  </related-article>
</article-meta></front><body><sec><p>Body.</p></sec></body></article>"""

PAGINATED = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="review-article"><front><article-meta>
  <volume>7</volume><issue>Suppl 5</issue><fpage>S7</fpage>
</article-meta></front><body><sec><p>Body.</p></sec></body></article>"""

MULTI_AWARD = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article"><front><article-meta><funding-group>
  <award-group>
    <funding-source><institution>NSFC</institution></funding-source>
    <award-id>81971974</award-id>
    <award-id>82372297</award-id>
    <award-id>32000844</award-id>
  </award-group>
</funding-group></article-meta></front><body><sec><p>Body.</p></sec></body></article>"""

VERSIONED = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article"
         xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>
  <self-uri content-type="preprint" xlink:href="https://doi.org/10.1101/2024.06.13.24308783"/>
  <self-uri content-type="reviewed-preprint" xlink:href="https://doi.org/10.7554/eLife.99323.1"/>
  <self-uri content-type="pmc-pdf" xlink:href="elife-99323.pdf"/>
</article-meta></front><body><sec><p>Body.</p></sec></body></article>"""


class TestPagination:
    def test_no_pages_when_the_article_has_none(self):
        """A reference's <fpage>/<lpage> is not this article's page range."""
        assert FullTextXMLParser(ELOCATION_ONLY).extract_metadata()["pages"] is None

    def test_elocation_id_is_extracted(self):
        assert FullTextXMLParser(ELOCATION_ONLY).extract_metadata()["elocation_id"] == "354"

    def test_pages_are_kept_when_the_article_has_them(self):
        assert FullTextXMLParser(PAGINATED).extract_metadata()["pages"] == "S7"

    def test_volume_and_issue_ignore_the_reference_list(self):
        metadata = FullTextXMLParser(ELOCATION_ONLY).extract_metadata()
        assert (metadata["volume"], metadata["issue"]) == ("9", None)
        assert metadata["journal"]["volume"] == "9"
        assert metadata["journal"]["issue"] is None

    def test_a_related_article_is_not_this_article(self):
        metadata = FullTextXMLParser(RELATED_ARTICLE).extract_metadata()
        assert metadata["pages"] is None
        assert metadata["elocation_id"] == "e0357759"


class TestKeywords:
    def test_only_the_articles_own_keywords(self):
        parser = FullTextXMLParser(ELOCATION_ONLY)
        assert parser.extract_keywords() == ["Structural biology"]

    def test_detailed_keywords_too(self):
        groups = FullTextXMLParser(ELOCATION_ONLY).metadata_parser.extract_keywords_detailed()
        assert [kwd for group in groups for kwd in group["keywords"]] == ["Structural biology"]


class TestArticleType:
    @pytest.mark.parametrize(
        ("xml", "expected"),
        [(ELOCATION_ONLY, "research-article"), (PAGINATED, "review-article")],
    )
    def test_article_type_comes_from_the_root_element(self, xml, expected):
        categories = FullTextXMLParser(xml).extract_article_categories()
        assert categories["article_type"] == expected


class TestFunding:
    def test_every_award_id_of_a_group_is_kept(self):
        funding = FullTextXMLParser(MULTI_AWARD).extract_metadata()["funding"]
        assert funding[0]["award_ids"] == ["81971974", "82372297", "32000844"]

    def test_award_id_still_names_the_first(self):
        funding = FullTextXMLParser(MULTI_AWARD).extract_metadata()["funding"]
        assert funding[0]["award_id"] == "81971974"


class TestSelfUri:
    def test_an_earlier_version_is_not_this_article(self):
        assert FullTextXMLParser(VERSIONED).extract_metadata()["self_uri"] == "elife-99323.pdf"
