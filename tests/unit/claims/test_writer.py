"""Tests for claim writer."""

from pyeuropepmc.claims.models import Claim, ClaimEvidence, ClaimSet, ClaimType, Verdict
from pyeuropepmc.claims.writer import ClaimWriter


class TestClaimWriter:
    def test_write_report_no_accepted_claims(self):
        writer = ClaimWriter(llm_enabled=False)
        cs = ClaimSet(source_text="original")
        cs.claims = [
            Claim(id="c1", text="refuted", original_text="refuted", verdict=Verdict.REFUTED),
        ]
        report = writer.write_report("original text", cs, user_decisions={"c1": False})
        assert report.improved_text == "original text"
        assert len(report.bibliography) == 0
        assert "No accepted claims" in (report.review_notes or "")

    def test_write_report_with_supported_claims(self):
        writer = ClaimWriter(llm_enabled=False)
        cs = ClaimSet(source_text="original text with claim here")
        cs.claims = [
            Claim(
                id="c1",
                text="claim statement",
                original_text="claim here",
                verdict=Verdict.SUPPORTED,
                evidence=[
                    ClaimEvidence(
                        text="supporting evidence",
                        paper_title="CRISPR Study 2023",
                        authors="Smith J",
                        source="12345",
                        source_type="pmid",
                        year=2023,
                        relevance_score=0.9,
                    ),
                ],
            ),
        ]
        report = writer.write_report("original text with claim here", cs)
        assert len(report.bibliography) == 1
        assert report.bibliography[0]["title"] == "CRISPR Study 2023"
        assert report.bibliography[0]["id"] == "ref1"

    def test_filter_accepted(self):
        writer = ClaimWriter(llm_enabled=False)
        claims = [
            Claim(id="c1", text="supported", original_text="s", verdict=Verdict.SUPPORTED),
            Claim(id="c2", text="refuted", original_text="r", verdict=Verdict.REFUTED),
            Claim(id="c3", text="insufficient", original_text="i", verdict=Verdict.INSUFFICIENT_EVIDENCE),
        ]
        accepted = writer._filter_accepted(claims, {"c1": True, "c2": False})
        # c1 explicitly accepted, c2 explicitly rejected, c3 auto-accepted (not refuted)
        assert len(accepted) == 2
        assert {c.id for c in accepted} == {"c1", "c3"}

    def test_filter_accepted_default_refuted_excluded(self):
        writer = ClaimWriter(llm_enabled=False)
        claims = [
            Claim(id="c1", text="supported", original_text="s", verdict=Verdict.SUPPORTED,
                  evidence=[ClaimEvidence(text="e", paper_title="P", authors="A", source="1")]),
            Claim(id="c2", text="refuted", original_text="r", verdict=Verdict.REFUTED),
        ]
        accepted = writer._filter_accepted(claims, {})
        assert len(accepted) == 1
        assert accepted[0].id == "c1"

    def test_build_bibliography_dedup(self):
        writer = ClaimWriter(llm_enabled=False)
        claims = [
            Claim(
                id="c1", text="claim1", original_text="c1",
                verdict=Verdict.SUPPORTED,
                evidence=[
                    ClaimEvidence(text="e1", paper_title="Paper A", authors="Author A", source="1"),
                    ClaimEvidence(text="e2", paper_title="Paper A", authors="Author A", source="1"),
                ],
            ),
        ]
        bib = writer._build_bibliography(claims)
        assert len(bib) == 1  # deduplicated by source

    def test_simple_improve_text(self):
        writer = ClaimWriter(llm_enabled=False)
        claims = [
            Claim(
                id="c1", text="claim text", original_text="claim here",
                verdict=Verdict.SUPPORTED,
                evidence=[
                    ClaimEvidence(text="e", paper_title="Paper", authors="A", source="1"),
                ],
            ),
        ]
        bib = [{"id": "ref1", "title": "Paper", "source": "1"}]
        improved = writer._simple_improve_text("original text with claim here", claims, bib)
        assert "[ref1]" in improved

    def test_convert_bibliography(self):
        writer = ClaimWriter(llm_enabled=False)
        bib = [{"id": "ref1", "type": "article", "title": "Paper", "author": "Author",
                "year": "2023", "journal": "Journal", "source": "1"}]
        # bibtex format returns as-is
        result = writer._convert_bibliography(bib, "bibtex")
        assert result == bib
