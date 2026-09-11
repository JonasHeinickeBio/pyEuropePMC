"""Unit tests for EuropePMCEnrichmentClient._build_query.

Covers the DOI-URL detection (via the actual host, not a raw substring
search — see the CodeQL "incomplete URL substring sanitization" fix) and
the DOI-extraction fix (a DOI itself contains a "/" between its prefix and
suffix, so it must not be taken as just the last "/"-segment).
"""

from __future__ import annotations

from pyeuropepmc.features.enrich.sources.europepmc import EuropePMCEnrichmentClient


class TestBuildQuery:
    def test_doi_url(self):
        assert (
            EuropePMCEnrichmentClient._build_query("https://doi.org/10.1234/test")
            == 'DOI:"10.1234/test"'
        )

    def test_dx_doi_url(self):
        assert (
            EuropePMCEnrichmentClient._build_query("http://dx.doi.org/10.1234/test")
            == 'DOI:"10.1234/test"'
        )

    def test_spoofed_host_not_treated_as_doi_url(self):
        query = EuropePMCEnrichmentClient._build_query("https://evil.example/doi.org/10.1234/fake")
        assert query != 'DOI:"10.1234/fake"'

    def test_lookalike_host_not_treated_as_doi_url(self):
        query = EuropePMCEnrichmentClient._build_query("https://doi.org.evil.example/10.1234/fake")
        assert query != 'DOI:"10.1234/fake"'

    def test_bare_doi(self):
        assert EuropePMCEnrichmentClient._build_query("10.1234/test") == 'DOI:"10.1234/test"'

    def test_pmcid(self):
        assert EuropePMCEnrichmentClient._build_query("pmc123456") == "PMCID:PMC123456"

    def test_pmid(self):
        assert EuropePMCEnrichmentClient._build_query("123456") == "EXT_ID:123456 AND SRC:MED"

    def test_free_text_passthrough(self):
        assert EuropePMCEnrichmentClient._build_query("some free text") == "some free text"
