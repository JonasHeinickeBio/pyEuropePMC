"""Licence extraction, found by auditing 124 real Europe PMC documents.

Two independent gaps, both in `extract_license`:

* the machine-readable URL lives in <ali:license_ref>, which was never read -
  only <ext-link> was, and many articles carry no <ext-link> at all
* <license-p> text was read without `use_full_text`, so a licence paragraph
  opening with an inline element contributed nothing

Across the corpus these took licence URLs from 83 of 124 documents to 100,
and licence text from 96 to 124.
"""

import pytest

from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser

pytestmark = pytest.mark.unit

ALI = 'xmlns:ali="http://www.niso.org/schemas/ali/1.0/"'


def _article(permissions: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<article><front><article-meta>"
        f"<permissions>{permissions}</permissions>"
        "</article-meta></front></article>"
    )


class TestLicenceUrl:
    def test_url_from_ali_license_ref(self):
        """The only URL source in many articles; it was never consulted."""
        xml = _article(
            f'<license><ali:license_ref {ALI} specific-use="textmining">'
            "https://creativecommons.org/licenses/by/4.0/</ali:license_ref>"
            "<license-p>Open Access.</license-p></license>"
        )
        assert (
            FullTextXMLParser(xml).extract_license()["url"]
            == "https://creativecommons.org/licenses/by/4.0/"
        )

    def test_ext_link_still_works_without_license_ref(self):
        xml = _article(
            '<license><license-p>See <ext-link xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' xlink:href="https://example.org/licence">here</ext-link>.</license-p></license>'
        )
        assert (
            FullTextXMLParser(xml).extract_license()["url"] == "https://example.org/licence"
        )

    def test_license_ref_preferred_over_ext_link(self):
        """license_ref is the canonical machine-readable form."""
        xml = _article(
            f'<license><ali:license_ref {ALI}>https://canonical.example/by/4.0/'
            "</ali:license_ref>"
            '<license-p>See <ext-link xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' xlink:href="https://other.example/x">here</ext-link>.</license-p></license>'
        )
        assert (
            FullTextXMLParser(xml).extract_license()["url"]
            == "https://canonical.example/by/4.0/"
        )

    def test_empty_license_ref_falls_through_to_ext_link(self):
        xml = _article(
            f'<license><ali:license_ref {ALI}>   </ali:license_ref>'
            '<license-p>See <ext-link xmlns:xlink="http://www.w3.org/1999/xlink"'
            ' xlink:href="https://fallback.example/x">here</ext-link>.</license-p></license>'
        )
        assert (
            FullTextXMLParser(xml).extract_license()["url"] == "https://fallback.example/x"
        )


class TestLicenceText:
    def test_text_when_paragraph_opens_with_an_inline_element(self):
        """"<bold>Open Access</bold>This article..." read as empty before.

        Without `use_full_text` the helper takes only the element's own
        leading text, which here is the whitespace before <bold>.
        """
        xml = _article(
            "<license><license-p><bold>Open Access</bold>This article is distributed"
            " under the terms of the Creative Commons Attribution License."
            "</license-p></license>"
        )
        text = FullTextXMLParser(xml).extract_license()["text"]
        assert "Open Access" in text
        assert "Creative Commons Attribution License" in text

    def test_plain_paragraph_text_still_read(self):
        xml = _article("<license><license-p>Plain licence wording.</license-p></license>")
        assert FullTextXMLParser(xml).extract_license()["text"] == "Plain licence wording."

    def test_no_permissions_returns_empty(self):
        xml = '<?xml version="1.0"?><article><front><article-meta/></front></article>'
        assert FullTextXMLParser(xml).extract_license() == {}
