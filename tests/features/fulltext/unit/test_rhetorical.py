"""Unit tests for pyeuropepmc.features.fulltext.rhetorical (hermetic)."""

from __future__ import annotations

import builtins
from unittest.mock import MagicMock, patch

import pytest

from pyeuropepmc.features.fulltext.rhetorical import (
    HighlightedDocument,
    RhetoricalHighlighter,
    RhetoricalRole,
    SentenceAnnotation,
    extract_text_from_pdf,
    highlight_pdf_text,
    highlight_text,
)


class TestRhetoricalRole:
    def test_display_labels_cover_all_roles(self):
        labels = RhetoricalRole.display_labels()
        assert set(labels) == set(RhetoricalRole)
        assert labels[RhetoricalRole.CLAIM] == "🔵 Claim"

    def test_hex_colors_cover_all_roles(self):
        colors = RhetoricalRole.hex_colors()
        assert set(colors) == set(RhetoricalRole)
        assert colors[RhetoricalRole.CLAIM].startswith("#")


class TestSentenceAnnotation:
    def test_to_dict(self):
        ann = SentenceAnnotation(text="hi", role=RhetoricalRole.CLAIM, confidence=0.9)
        d = ann.to_dict()
        assert d["role"] == "claim"
        assert d["confidence"] == 0.9

    def test_repr(self):
        ann = SentenceAnnotation(text="hi", role=RhetoricalRole.METHOD, confidence=0.5)
        assert "method" in repr(ann)
        assert "0.50" in repr(ann)


class TestHighlightedDocument:
    def test_group_by_role(self):
        doc = HighlightedDocument(
            sentences=[
                SentenceAnnotation(text="a", role=RhetoricalRole.CLAIM),
                SentenceAnnotation(text="b", role=RhetoricalRole.CLAIM),
                SentenceAnnotation(text="c", role=RhetoricalRole.METHOD),
            ]
        )
        grouped = doc.group_by_role()
        assert len(grouped["claim"]) == 2
        assert len(grouped["method"]) == 1

    def test_to_dict_and_json(self):
        doc = HighlightedDocument(
            sentences=[SentenceAnnotation(text="a", role=RhetoricalRole.CLAIM)],
            title="T",
        )
        d = doc.to_dict()
        assert d["title"] == "T"
        assert len(d["sentences"]) == 1
        text = doc.to_json()
        assert '"title": "T"' in text

    def test_compute_statistics_empty(self):
        doc = HighlightedDocument()
        stats = doc.compute_statistics()
        assert stats["total_sentences"] == 0
        assert stats["overall_mean_confidence"] == 0.0

    def test_compute_statistics_nonempty(self):
        doc = HighlightedDocument(
            sentences=[
                SentenceAnnotation(text="a", role=RhetoricalRole.CLAIM, confidence=0.8),
                SentenceAnnotation(text="b", role=RhetoricalRole.CLAIM, confidence=0.6),
                SentenceAnnotation(text="c", role=RhetoricalRole.METHOD, confidence=0.5),
            ]
        )
        stats = doc.compute_statistics()
        assert stats["total_sentences"] == 3
        assert stats["role_counts"]["claim"] == 2
        assert stats["role_percentages"]["claim"] == pytest.approx(200 / 3)
        assert stats["mean_confidence_per_role"]["claim"] == pytest.approx(0.7)

    def test_summary_computes_stats_if_missing(self):
        doc = HighlightedDocument(
            sentences=[SentenceAnnotation(text="a", role=RhetoricalRole.CLAIM, confidence=0.9)],
            title="My Paper",
        )
        text = doc.summary()
        assert "My Paper" in text
        assert "Sentences: 1" in text
        assert "Claim" in text

    def test_summary_uses_existing_stats(self):
        doc = HighlightedDocument(sentences=[SentenceAnnotation(text="a")])
        doc.compute_statistics()
        # mutate to prove summary() doesn't recompute
        doc.statistics["total_sentences"] = 99
        text = doc.summary()
        assert "Sentences: 99" in text

    def test_summary_no_title(self):
        doc = HighlightedDocument(sentences=[])
        assert "Title: N/A" in doc.summary()


class TestRhetoricalHighlighterRuleBased:
    def test_highlight_splits_and_classifies(self):
        rl = RhetoricalHighlighter()
        text = (
            "We show that our method achieves 95% accuracy. "
            "We used a randomly initialized network trained on ImageNet. "
            "A key limitation is that it does not account for noise."
        )
        doc = rl.highlight(text, title="T", authors="A", source="S")
        assert doc.title == "T"
        assert len(doc.sentences) == 3
        roles = [s.role for s in doc.sentences]
        assert RhetoricalRole.CLAIM in roles
        assert RhetoricalRole.METHOD in roles
        assert RhetoricalRole.LIMITATION in roles
        assert doc.statistics  # compute_statistics() called internally

    def test_highlight_empty_text(self):
        rl = RhetoricalHighlighter()
        doc = rl.highlight("")
        assert doc.sentences == []

    def test_classify_sentence_unknown_below_threshold(self):
        rl = RhetoricalHighlighter(confidence_threshold=0.9)
        role, conf = rl._classify_sentence("We show that this works.")
        assert role == RhetoricalRole.UNKNOWN

    def test_classify_sentence_no_pattern_match(self):
        rl = RhetoricalHighlighter()
        role, conf = rl._classify_sentence("Colorless green ideas sleep furiously.")
        assert role == RhetoricalRole.UNKNOWN
        assert conf == 0.0

    def test_classify_picks_highest_confidence_rule(self):
        rl = RhetoricalHighlighter()
        # "limitation" (0.6) should win over "we used" (0.5) if both present
        role, conf = rl._classify_sentence("we used a limitation-prone approach")
        assert role == RhetoricalRole.LIMITATION


class TestRhetoricalHighlighterLLM:
    def test_llm_refines_low_confidence_sentence(self):
        llm_client = MagicMock()
        llm_client.chat.return_value = (
            '{"role": "conclusion", "confidence": 0.95, "explanation": "x"}'
        )
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        role, conf = rl._classify_sentence("Something ambiguous here maybe.")
        assert role == RhetoricalRole.CONCLUSION
        assert conf == 0.95
        llm_client.chat.assert_called_once()

    def test_llm_not_used_when_rule_confidence_high(self):
        llm_client = MagicMock()
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        rl._classify_sentence("we used a specific method for this")
        llm_client.chat.assert_not_called()

    def test_llm_exception_is_caught(self):
        llm_client = MagicMock()
        llm_client.chat.side_effect = RuntimeError("api down")
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        role, conf = rl._classify_sentence("Something ambiguous here maybe.")
        assert role == RhetoricalRole.UNKNOWN

    def test_classify_with_llm_invalid_json_returns_unknown(self):
        llm_client = MagicMock()
        llm_client.chat.return_value = "not json"
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        role, conf = rl._classify_with_llm("some sentence")
        assert role == RhetoricalRole.UNKNOWN
        assert conf == 0.0

    def test_classify_with_llm_invalid_role_falls_back_to_unknown(self):
        llm_client = MagicMock()
        llm_client.chat.return_value = '{"role": "not_a_real_role", "confidence": 0.8}'
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        role, conf = rl._classify_with_llm("some sentence")
        assert role == RhetoricalRole.UNKNOWN
        assert conf == 0.8

    def test_classify_with_llm_success(self):
        llm_client = MagicMock()
        llm_client.chat.return_value = '{"role": "method", "confidence": 0.7}'
        rl = RhetoricalHighlighter(use_llm=True, llm_client=llm_client)
        role, conf = rl._classify_with_llm("some sentence")
        assert role == RhetoricalRole.METHOD
        assert conf == 0.7


class TestExtractTextFromPdf:
    def test_uses_first_available_backend(self):
        with patch(
            "pyeuropepmc.features.fulltext.rhetorical._extract_pymupdf",
            return_value="pymupdf text",
        ):
            assert extract_text_from_pdf("f.pdf") == "pymupdf text"

    def test_falls_back_on_import_error(self):
        def fake_pymupdf(path):
            raise ImportError("no fitz")

        with (
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pymupdf",
                side_effect=fake_pymupdf,
            ),
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pdfplumber",
                return_value="plumber text",
            ),
        ):
            assert extract_text_from_pdf("f.pdf") == "plumber text"

    def test_falls_back_on_generic_exception(self):
        with (
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pymupdf",
                side_effect=RuntimeError("corrupt file"),
            ),
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pdfplumber",
                side_effect=RuntimeError("also fails"),
            ),
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pdfminer",
                return_value="miner text",
            ),
        ):
            assert extract_text_from_pdf("f.pdf") == "miner text"

    def test_no_backend_available_returns_none(self):
        with (
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pymupdf",
                side_effect=ImportError,
            ),
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pdfplumber",
                side_effect=ImportError,
            ),
            patch(
                "pyeuropepmc.features.fulltext.rhetorical._extract_pdfminer",
                side_effect=ImportError,
            ),
        ):
            assert extract_text_from_pdf("f.pdf") is None


class TestPdfBackendImplementations:
    def test_extract_pymupdf(self):
        from pyeuropepmc.features.fulltext.rhetorical import _extract_pymupdf

        fake_page = MagicMock()
        fake_page.get_text.return_value = "page text"
        fake_doc = MagicMock()
        fake_doc.__iter__.return_value = iter([fake_page])
        fake_fitz = MagicMock()
        fake_fitz.open.return_value = fake_doc

        with patch.dict("sys.modules", {"fitz": fake_fitz}):
            text = _extract_pymupdf("f.pdf")
        assert text == "page text"
        fake_doc.close.assert_called_once()

    def test_extract_pdfplumber(self):
        from pyeuropepmc.features.fulltext.rhetorical import _extract_pdfplumber

        fake_page = MagicMock()
        fake_page.extract_text.return_value = "page text"
        fake_pdf = MagicMock()
        fake_pdf.pages = [fake_page]
        fake_pdf.__enter__.return_value = fake_pdf
        fake_pdf.__exit__.return_value = False
        fake_module = MagicMock()
        fake_module.open.return_value = fake_pdf

        with patch.dict("sys.modules", {"pdfplumber": fake_module}):
            text = _extract_pdfplumber("f.pdf")
        assert text == "page text"

    def test_extract_pdfminer(self):
        from pyeuropepmc.features.fulltext.rhetorical import _extract_pdfminer

        fake_module = MagicMock()
        fake_module.extract_text.return_value = "miner text"

        with patch.dict("sys.modules", {"pdfminer.high_level": fake_module}):
            text = _extract_pdfminer("f.pdf")
        assert text == "miner text"


class TestModuleFunctions:
    def test_highlight_pdf_text_success(self):
        with patch(
            "pyeuropepmc.features.fulltext.rhetorical.extract_text_from_pdf",
            return_value="We show that this works.",
        ):
            doc = highlight_pdf_text("f.pdf", title="T", authors="A")
        assert doc is not None
        assert doc.source == "f.pdf"
        assert doc.title == "T"

    def test_highlight_pdf_text_no_text_returns_none(self):
        with patch(
            "pyeuropepmc.features.fulltext.rhetorical.extract_text_from_pdf",
            return_value=None,
        ):
            assert highlight_pdf_text("f.pdf") is None

    def test_highlight_text(self):
        doc = highlight_text("We show that this works.", title="T")
        assert doc.title == "T"
        assert len(doc.sentences) == 1
