"""Who counts as an author, found by checking extracted values against the XML.

Two faults, each adding people who are not authors of the article:

* the search ran over the whole document, so the <contrib> inside every
  <sub-article> - the peer reviewers - came back as article authors.
  PMC13567752 has 9 and returned 14, the reviewer repeated once per report.
* with no <contrib contrib-type="author"> anywhere, the patterns fell through
  to a bare `.//name`, which matches the editors in a
  <contrib-group content-type="editor">. One extra author on 13 of 124
  corpus documents.

Author surnames matched the article's own front matter exactly for 102 of
124 documents before, and 124 of 124 after.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

PEER_REVIEWED = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta><contrib-group>
  <contrib contrib-type="author"><name><surname>Ankit</surname><given-names>A.</given-names></name></contrib>
  <contrib contrib-type="author"><name><surname>Kumar</surname><given-names>K.</given-names></name></contrib>
</contrib-group></article-meta></front>
<body><sec><p>Body.</p></sec></body>
<sub-article article-type="reviewer-report"><front-stub><contrib-group>
  <contrib contrib-type="author"><name><surname>Osorio</surname><given-names>R.</given-names></name></contrib>
</contrib-group></front-stub><body><p>Review one.</p></body></sub-article>
<sub-article article-type="reviewer-report"><front-stub><contrib-group>
  <contrib contrib-type="author"><name><surname>Osorio</surname><given-names>R.</given-names></name></contrib>
</contrib-group></front-stub><body><p>Review two.</p></body></sub-article>
</article>"""

GROUP_DIALECT_WITH_EDITOR = """<?xml version="1.0" encoding="UTF-8"?>
<article><front><article-meta>
<contrib-group content-type="author">
  <contrib><name><surname>Yang</surname><given-names>Y.</given-names></name></contrib>
  <contrib><name><surname>Zhou</surname><given-names>Z.</given-names></name></contrib>
</contrib-group>
<contrib-group content-type="editor">
  <contrib><name><surname>Scala</surname><given-names>E.</given-names></name></contrib>
</contrib-group>
</article-meta></front><body><sec><p>Body.</p></sec></body></article>"""


class TestReviewersAreNotAuthors:
    @pytest.fixture
    def authors(self):
        return FullTextXMLParser(PEER_REVIEWED).extract_authors_detailed()

    def test_only_the_articles_own_authors(self, authors):
        assert [a["surname"] for a in authors] == ["Ankit", "Kumar"]

    def test_reviewer_absent(self, authors):
        assert "Osorio" not in [a["surname"] for a in authors]

    def test_plain_author_list_matches(self):
        names = FullTextXMLParser(PEER_REVIEWED).extract_authors()
        assert names == ["A. Ankit", "K. Kumar"]


class TestEditorsAreNotAuthors:
    @pytest.fixture
    def authors(self):
        return FullTextXMLParser(GROUP_DIALECT_WITH_EDITOR).extract_authors_detailed()

    def test_group_level_authors_found(self, authors):
        """<contrib-group content-type="author"> with untyped contributions."""
        assert [a["surname"] for a in authors] == ["Yang", "Zhou"]

    def test_editor_group_excluded(self, authors):
        """`.//name` used to sweep the editor in as a third author."""
        assert "Scala" not in [a["surname"] for a in authors]


class TestExistingDialectsStillWork:
    def test_contrib_type_author(self):
        xml = (
            '<?xml version="1.0"?><article><front><article-meta><contrib-group>'
            '<contrib contrib-type="author"><name><surname>Solo</surname>'
            "<given-names>S.</given-names></name></contrib>"
            "</contrib-group></article-meta></front></article>"
        )
        assert [a["surname"] for a in FullTextXMLParser(xml).extract_authors_detailed()] == [
            "Solo"
        ]

    def test_fragment_without_a_front_still_parses(self):
        """The scope falls back to the root when there is no <front>."""
        xml = (
            '<?xml version="1.0"?><article>'
            '<contrib contrib-type="author"><name><surname>Bare</surname>'
            "<given-names>B.</given-names></name></contrib></article>"
        )
        assert [a["surname"] for a in FullTextXMLParser(xml).extract_authors_detailed()] == [
            "Bare"
        ]
