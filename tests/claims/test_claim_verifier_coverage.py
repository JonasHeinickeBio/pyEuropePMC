"""Unit tests for pyeuropepmc.claims.verifier.ClaimVerifier.

Mocks SearchClient, the article-details client, and the LLM client so no
network or real LLM calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyeuropepmc.claims.models import Claim, ClaimEvidence, ClaimSet, Verdict
from pyeuropepmc.claims.verifier import ClaimVerifier


def _verifier(llm_enabled=False, search_results=None):
    mock_llm = MagicMock()
    mock_llm.enabled = llm_enabled
    with patch("pyeuropepmc.claims.verifier.SearchClient") as mock_search_cls:
        mock_search = MagicMock()
        mock_search.search.return_value = search_results or {}
        mock_search_cls.return_value = mock_search
        v = ClaimVerifier(llm_client=mock_llm, llm_enabled=llm_enabled)
    return v


def _paper(pmid="1", title="Title", abstract="A" * 60, **extra):
    p = {"pmid": pmid, "title": title, "abstractText": abstract}
    p.update(extra)
    return p


def _claim(text="CRISPR treats disease X"):
    return Claim(id="c1", text=text, original_text=text)


class TestInit:
    def test_default_llm_disabled(self):
        v = _verifier(llm_enabled=False)
        assert v.llm_enabled is False
        assert v.search_limit == 5
        assert v.max_evidence_per_claim == 3


class TestVerifyClaim:
    def test_cache_hit(self):
        v = _verifier()
        claim = _claim()
        v._verification_cache["crispr treats disease x"] = (
            Verdict.SUPPORTED,
            "cached reasoning",
            [],
        )
        result = v.verify_claim(claim)
        assert result.verdict == Verdict.SUPPORTED
        assert result.verification_reasoning == "cached reasoning"

    def test_no_papers_found(self):
        v = _verifier(search_results={"resultList": {"result": []}})
        result = v.verify_claim(_claim())
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert "No relevant papers" in result.verification_reasoning

    def test_papers_found_but_no_evidence_extracted(self):
        v = _verifier(search_results={"resultList": {"result": [_paper()]}})
        with patch.object(v, "_extract_evidence", return_value=[]):
            result = v.verify_claim(_claim())
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert "no specific evidence" in result.verification_reasoning

    def test_llm_disabled_defaults_to_supported(self):
        v = _verifier(
            llm_enabled=False,
            search_results={"resultList": {"result": [_paper()]}},
        )
        result = v.verify_claim(_claim())
        assert result.verdict == Verdict.SUPPORTED
        assert "Found" in result.verification_reasoning

    def test_llm_enabled_uses_llm_verify(self):
        v = _verifier(
            llm_enabled=True,
            search_results={"resultList": {"result": [_paper()]}},
        )
        v.llm_client.enabled = True
        with patch.object(v, "_llm_verify", return_value=(Verdict.REFUTED, "llm said no")):
            result = v.verify_claim(_claim())
        assert result.verdict == Verdict.REFUTED
        assert result.verification_reasoning == "llm said no"

    def test_result_is_cached_after_verification(self):
        v = _verifier(search_results={"resultList": {"result": [_paper()]}})
        claim = _claim()
        v.verify_claim(claim)
        assert "crispr treats disease x" in v._verification_cache


class TestVerifyClaimSet:
    def test_verifies_all_claims_and_sets_metadata(self):
        v = _verifier(search_results={"resultList": {"result": [_paper()]}})
        claim_set = ClaimSet(source_text="text", claims=[_claim("claim one"), _claim("claim two")])
        result = v.verify_claim_set(claim_set)
        assert result.metadata["verification_complete"] is True
        assert "verification_counts" in result.metadata
        assert all(c.verdict != Verdict.NOT_CHECKED for c in result.claims)


class TestSearchEvidence:
    def test_uses_llm_generated_queries_when_available(self):
        v = _verifier(llm_enabled=True, search_results={"resultList": {"result": []}})
        v.llm_client.enabled = True
        with patch.object(v, "_llm_generate_queries", return_value=["query one", "query two"]):
            v._search_evidence("original claim text")
        calls = [c.kwargs["query"] for c in v._search_client.search.call_args_list]
        assert "query one" in calls

    def test_falls_back_to_claim_text_when_no_llm_queries(self):
        v = _verifier(llm_enabled=True, search_results={"resultList": {"result": []}})
        v.llm_client.enabled = True
        with patch.object(v, "_llm_generate_queries", return_value=None):
            v._search_evidence("original claim text")
        calls = [c.kwargs["query"] for c in v._search_client.search.call_args_list]
        assert "original claim text" in calls

    def test_non_dict_results_treated_as_no_papers(self):
        v = _verifier(search_results=None)
        v._search_client.search.return_value = None
        papers = v._search_evidence("claim")
        assert papers == []

    def test_dedup_by_pmid(self):
        v = _verifier(
            search_results={
                "resultList": {"result": [_paper(pmid="1"), _paper(pmid="1"), _paper(pmid="2")]}
            }
        )
        papers = v._search_evidence("claim")
        pmids = [p["pmid"] for p in papers if p.get("pmid")]
        assert pmids.count("1") == 1

    def test_papers_without_pmid_always_added(self):
        v = _verifier(
            search_results={"resultList": {"result": [_paper(pmid=""), _paper(pmid="")]}}
        )
        papers = v._search_evidence("claim")
        assert len(papers) == 2

    def test_search_exception_is_skipped(self):
        v = _verifier()
        v._search_client.search.side_effect = RuntimeError("boom")
        papers = v._search_evidence("claim")
        assert papers == []


class TestEnrichPapers:
    def test_paper_with_abstract_unchanged(self):
        v = _verifier()
        paper = _paper(abstract="Already has an abstract text here.")
        result = v._enrich_papers([paper])
        assert result == [paper]

    def test_enriches_paper_missing_abstract_via_pmid(self):
        v = _verifier()
        paper = {"pmid": "123", "title": "T"}
        with patch.object(
            v, "_get_article_details", return_value={"abstractText": "Full abstract", "title": "T"}
        ):
            result = v._enrich_papers([paper])
        assert result[0]["abstractText"] == "Full abstract"

    def test_enriches_paper_via_pmcid_when_no_pmid(self):
        v = _verifier()
        paper = {"pmcid": "PMC123", "title": "T"}
        with patch.object(
            v, "_get_article_details", return_value={"fullText": "Full text here"}
        ) as mock_details:
            result = v._enrich_papers([paper])
        mock_details.assert_called_once_with("PMC", "PMC123")
        assert result[0]["abstractText"] == "Full text here"

    def test_no_pmid_or_pmcid_skips_enrichment(self):
        v = _verifier()
        paper = {"title": "T"}
        result = v._enrich_papers([paper])
        assert result == [paper]

    def test_enrichment_exception_is_swallowed(self):
        v = _verifier()
        paper = {"pmid": "1", "title": "T"}
        with patch.object(v, "_get_article_details", side_effect=RuntimeError("boom")):
            result = v._enrich_papers([paper])
        assert result == [paper]

    def test_get_article_details_returns_none_leaves_paper_unchanged(self):
        v = _verifier()
        paper = {"pmid": "1", "title": "T"}
        with patch.object(v, "_get_article_details", return_value=None):
            result = v._enrich_papers([paper])
        assert "abstractText" not in result[0]


class TestIsConferenceAbstract:
    def test_no_abstract_is_conference(self):
        assert ClaimVerifier._is_conference_abstract({"title": "T", "abstractText": ""}) is True

    def test_short_abstract_is_conference(self):
        assert ClaimVerifier._is_conference_abstract({"abstractText": "short"}) is True

    def test_conference_keyword_with_short_abstract(self):
        paper = {"title": "Annual Meeting Abstract", "abstractText": "x" * 100}
        assert ClaimVerifier._is_conference_abstract(paper) is True

    def test_long_real_abstract_not_conference(self):
        paper = {"title": "A Study", "abstractText": "x" * 200}
        assert ClaimVerifier._is_conference_abstract(paper) is False


class TestFilterRelevantPapers:
    def test_filters_conference_abstracts(self):
        papers = [
            _paper(title="Congress presentation", abstract="short"),
            _paper(title="Real study", abstract="A real research finding about disease X." * 5),
        ]
        result = ClaimVerifier._filter_relevant_papers(papers, "disease X treatment")
        assert len(result) == 1
        assert result[0]["title"] == "Real study"

    def test_empty_combined_text_skipped(self):
        papers = [{"title": "", "abstractText": ""}]
        result = ClaimVerifier._filter_relevant_papers(papers, "claim")
        assert result == []

    def test_phrase_match_bonus_affects_ranking(self):
        papers = [
            _paper(
                pmid="1", title="Unrelated", abstract="Nothing relevant here at all times." * 3
            ),
            _paper(
                pmid="2",
                title="disease x treatment study",
                abstract=("CRISPR treats disease X effectively in trials. " * 3),
            ),
        ]
        result = ClaimVerifier._filter_relevant_papers(
            papers, "CRISPR treats disease X. It works well."
        )
        assert result[0]["pmid"] == "2"

    def test_max_papers_limit(self):
        papers = [
            _paper(pmid=str(i), title=f"disease x study {i}", abstract="disease x " * 30)
            for i in range(10)
        ]
        result = ClaimVerifier._filter_relevant_papers(papers, "disease x", max_papers=3)
        assert len(result) == 3

    def test_no_claim_words_zero_score(self):
        papers = [_paper(title="123 456", abstract="789 " * 30)]
        result = ClaimVerifier._filter_relevant_papers(papers, "12 34")
        assert len(result) == 1


class TestGetArticleDetails:
    def test_lazy_imports_article_client(self):
        v = _verifier()
        fake_client = MagicMock()
        fake_client.get_article_details.return_value = {"result": {"title": "T"}}
        with patch(
            "pyeuropepmc.features.literature.article.ArticleClient", return_value=fake_client
        ):
            result = v._get_article_details("MED", "123")
        assert result == {"title": "T"}
        assert v._article_client is fake_client

    def test_reuses_cached_article_client(self):
        v = _verifier()
        fake_client = MagicMock()
        fake_client.get_article_details.return_value = {"result": {}}
        v._article_client = fake_client
        v._get_article_details("MED", "123")
        fake_client.get_article_details.assert_called_once()

    def test_non_dict_response_returns_none(self):
        v = _verifier()
        fake_client = MagicMock()
        fake_client.get_article_details.return_value = "not a dict"
        v._article_client = fake_client
        assert v._get_article_details("MED", "123") is None

    def test_exception_returns_none(self):
        v = _verifier()
        fake_client = MagicMock()
        fake_client.get_article_details.side_effect = RuntimeError("boom")
        v._article_client = fake_client
        assert v._get_article_details("MED", "123") is None


class TestLlmGenerateQueries:
    def test_parses_fenced_json(self):
        v = _verifier()
        v.llm_client.generate.return_value = (
            '```json\n{"queries": ["term one two", "term three four"]}\n```'
        )
        queries = v._llm_generate_queries("claim")
        assert queries == ["term one two", "term three four"]

    def test_parses_plain_json(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"queries": ["alpha beta"]}'
        assert v._llm_generate_queries("claim") == ["alpha beta"]

    def test_empty_result_returns_none(self):
        v = _verifier()
        v.llm_client.generate.return_value = ""
        assert v._llm_generate_queries("claim") is None

    def test_invalid_json_returns_none(self):
        v = _verifier()
        v.llm_client.generate.return_value = "not json at all"
        assert v._llm_generate_queries("claim") is None

    def test_filters_short_queries(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"queries": ["one", "two words here"]}'
        assert v._llm_generate_queries("claim") == ["two words here"]

    def test_all_queries_too_short_returns_none(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"queries": ["one", "two"]}'
        assert v._llm_generate_queries("claim") is None

    def test_limits_to_three_queries(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"queries": ["a b", "c d", "e f", "g h"]}'
        assert len(v._llm_generate_queries("claim")) == 3

    def test_exception_returns_none(self):
        v = _verifier()
        v.llm_client.generate.side_effect = RuntimeError("boom")
        assert v._llm_generate_queries("claim") is None

    def test_non_list_queries_returns_none(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"queries": "not a list"}'
        assert v._llm_generate_queries("claim") is None


class TestExtractEvidence:
    def test_basic_extraction(self):
        v = _verifier()
        papers = [_paper(pmid="1", title="T", abstract="Evidence text here.", pubYear=2020)]
        evidence = v._extract_evidence(papers, "claim")
        assert len(evidence) == 1
        assert evidence[0].paper_title == "T"
        assert evidence[0].source == "1"
        assert evidence[0].source_type == "pmid"
        assert evidence[0].year == 2020

    def test_falls_back_to_title_when_no_abstract(self):
        v = _verifier()
        papers = [_paper(pmid="1", title="Fallback Title", abstract="")]
        evidence = v._extract_evidence(papers, "claim")
        assert evidence[0].text == "Fallback Title"

    def test_missing_title_and_abstract_falls_back_to_unknown_title(self):
        # title defaults to "Unknown Title" when absent/empty, so evidence_text
        # is never actually empty in practice — this exercises that fallback.
        v = _verifier()
        papers = [{"pmid": "1", "title": "", "abstractText": ""}]
        evidence = v._extract_evidence(papers, "claim")
        assert len(evidence) == 1
        assert evidence[0].text == "Unknown Title"

    def test_uses_doi_when_no_pmid(self):
        v = _verifier()
        papers = [_paper(pmid="", doi="10.1/x", title="T", abstract="text")]
        evidence = v._extract_evidence(papers, "claim")
        assert evidence[0].source == "10.1/x"
        assert evidence[0].source_type == "doi"
        assert evidence[0].url is None

    def test_exception_for_one_paper_does_not_abort_batch(self):
        v = _verifier()
        bad_paper = MagicMock()
        bad_paper.get.side_effect = RuntimeError("boom")
        good_paper = _paper(pmid="1", title="T", abstract="text")
        evidence = v._extract_evidence([bad_paper, good_paper], "claim")
        assert len(evidence) == 1

    def test_sorted_by_relevance_descending(self):
        v = _verifier()
        papers = [
            _paper(pmid="1", title="Unrelated", abstract="totally different content here"),
            _paper(pmid="2", title="disease x", abstract="disease x disease x disease x"),
        ]
        evidence = v._extract_evidence(papers, "disease x")
        assert evidence[0].relevance_score >= evidence[-1].relevance_score


class TestEstimateRelevance:
    def test_no_claim_words_returns_default(self):
        v = _verifier()
        assert v._estimate_relevance("12 34", "some evidence text") == 0.3

    def test_overlap_scoring(self):
        v = _verifier()
        score = v._estimate_relevance("disease treatment study", "disease treatment results")
        assert 0 < score <= 1.0

    def test_phrase_bonus_applied(self):
        v = _verifier()
        claim = "a" * 60
        evidence = claim.lower()
        score = v._estimate_relevance(claim, evidence)
        assert score <= 1.0

    def test_score_clamped_to_range(self):
        v = _verifier()
        score = v._estimate_relevance("word word word", "word word word word word")
        assert 0.0 <= score <= 1.0


class TestLlmVerify:
    def test_happy_path_delegates_to_parse_verdict(self):
        v = _verifier()
        v.llm_client.generate.return_value = '{"verdict": "supported", "reasoning": "ok"}'
        evidence = [ClaimEvidence(text="t", paper_title="p", authors="a", source="1")]
        verdict, reasoning = v._llm_verify("claim", evidence)
        assert verdict == Verdict.SUPPORTED
        assert reasoning == "ok"

    def test_empty_result_returns_insufficient(self):
        v = _verifier()
        v.llm_client.generate.return_value = ""
        verdict, reasoning = v._llm_verify("claim", [])
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert "empty" in reasoning.lower()

    def test_exception_returns_insufficient(self):
        v = _verifier()
        v.llm_client.generate.side_effect = RuntimeError("boom")
        verdict, reasoning = v._llm_verify("claim", [])
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert "boom" in reasoning


class TestParseVerdict:
    def test_fenced_json(self):
        v = _verifier()
        verdict, reasoning = v._parse_verdict(
            '```json\n{"verdict": "refuted", "reasoning": "no"}\n```'
        )
        assert verdict == Verdict.REFUTED
        assert reasoning == "no"

    def test_plain_json(self):
        v = _verifier()
        verdict, reasoning = v._parse_verdict('{"verdict": "supported", "reasoning": "yes"}')
        assert verdict == Verdict.SUPPORTED

    def test_keyword_fallback_supported(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("The evidence is supported by the data.")
        assert verdict == Verdict.SUPPORTED

    def test_keyword_fallback_refuted(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("This claim is refuted by the findings.")
        assert verdict == Verdict.REFUTED

    def test_keyword_fallback_contradict(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("The results contradict the claim.")
        assert verdict == Verdict.REFUTED

    def test_keyword_fallback_insufficient(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("There is insufficient evidence here.")
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE

    def test_keyword_fallback_partially(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("The claim is partially true.")
        assert verdict == Verdict.PARTIALLY_SUPPORTED

    def test_keyword_fallback_default(self):
        v = _verifier()
        verdict, _ = v._parse_verdict("Nothing conclusive can be said.")
        assert verdict == Verdict.INSUFFICIENT_EVIDENCE


class TestClearCache:
    def test_clears_cache(self):
        v = _verifier()
        v._verification_cache["x"] = (Verdict.SUPPORTED, "r", [])
        v.clear_cache()
        assert v._verification_cache == {}
