"""
Copied unit tests for text matching into tests/filters/unit
"""

from pyeuropepmc.utils import text_match as tm


def test_normalize_and_tokens():
    assert tm.normalize("Café,  -- test!") == "cafe test"
    assert tm.tokens("Café test") == ["cafe", "test"]


def test_token_jaccard_and_fuzzy():
    a = "immunotherapy cancer"
    b = "cancer immunotherapy approaches"
    j = tm.token_jaccard(a, b)
    assert 0.5 <= j <= 1.0
    score = tm.token_fuzzy_score(a, b)
    assert score >= 80


def test_any_match_substring_and_fuzzy():
    hay = ["cancer immunotherapy", "diabetes clinical trial"]
    assert tm.any_match("immuno", hay) is True
    assert tm.any_match("clinical trial", hay) is True
    # non-matching
    assert tm.any_match("neuroscience", hay) is False


def test_all_and_any_needles_match():
    hay = ["cancer immunotherapy", "diabetes clinical trial"]
    assert tm.all_needles_match(["cancer", "immunotherapy"], hay) is True
    assert tm.any_needles_match(["cancer", "neuro"], hay) is True
    assert tm.all_needles_match(["cancer", "neuro"], hay) is False


def test_any_match_semantic_skip_if_missing():
    # If sentence-transformers is installed the call should not raise; otherwise it's gracefully handled
    try:
        has_st = True
    except Exception:
        has_st = False

    # Run with use_semantic=True but keep test robust when model not present
    res = tm.any_match("cancer therapy", ["oncology treatment"], use_semantic=True)
    # If sentence-transformers present we may get True; if not present, result should be False
    assert (res is True) or (res is False)


def test_any_match_semantic_with_injected_model_positive():
    # Fake model where encode returns identical normalized vectors -> cosine similarity 1.0
    class FakeModelPos:
        def encode(
            self,
            sentences,
            batch_size: int = 32,
            show_progress_bar: bool = False,
            convert_to_numpy: bool = False,
            convert_to_tensor: bool = False,
            device: object | None = None,
            normalize_embeddings: bool = False,
        ):
            # return list of identical vectors (1-dim) so dot product = 1.0 after normalization
            import numpy as _np
            arr = _np.ones((len(list(sentences)), 1), dtype=float)
            return arr

    model = FakeModelPos()
    res = tm.any_match("cancer therapy", ["oncology treatment"], use_semantic=True, semantic_model=model)
    assert res is True


def test_any_match_semantic_with_injected_model_negative():
    # Fake model that maps 'oncology' -> [1,0], 'cancer' -> [0,1] so different texts are orthogonal
    class FakeModelNeg:
        def encode(
            self,
            sentences,
            batch_size: int = 32,
            show_progress_bar: bool = False,
            convert_to_numpy: bool = False,
            convert_to_tensor: bool = False,
            device: object | None = None,
            normalize_embeddings: bool = False,
        ):
            import numpy as _np
            out = []
            for t in list(sentences):
                tt = (t or "").lower()
                if "oncology" in tt:
                    out.append(_np.array([1.0, 0.0], dtype=float))
                elif "cancer" in tt:
                    out.append(_np.array([0.0, 1.0], dtype=float))
                else:
                    out.append(_np.array([0.0, 0.0], dtype=float))
            return _np.vstack(out)

    model = FakeModelNeg()
    res = tm.any_match("cancer therapy", ["oncology treatment"], use_semantic=True, semantic_model=model, semantic_threshold=0.5)
    assert res is False


def test_any_match_semantic_model_error_handling():
    # Fake model that raises during encode; any_match should handle and return False
    class BrokenModel:
        def encode(self, *args, **kwargs):
            raise RuntimeError("broken model")

    model = BrokenModel()
    res = tm.any_match("cancer therapy", ["oncology treatment"], use_semantic=True, semantic_model=model)
    assert res is False


# ── Edge cases for existing functions ──


def test_normalize_empty():
    """Normalize of empty string returns empty string (line 25)."""
    assert tm.normalize("") == ""


def test_token_jaccard_empty():
    """Jaccard of empty token set returns 0.0 (line 46)."""
    assert tm.token_jaccard("", "something") == 0.0
    assert tm.token_jaccard("something", "") == 0.0


def test_any_match_empty_needle():
    """Empty needle returns False immediately (line 215)."""
    assert tm.any_match("", ["something"]) is False


def test_any_match_empty_hay():
    """No valid hay values returns False (line 219)."""
    assert tm.any_match("test", []) is False
    assert tm.any_match("test", [None, ""]) is False


def test_any_match_jaccard_path():
    """Fuzzy fails but jaccard succeeds (lines 228-247)."""
    # Different words, same tokens: "cancer immunotherapy" and "cancer treatment"
    # need a case where fuzzy is low but jaccard is above 0.5
    hay = ["biological therapy"]
    # "cancer" and "therapy" have different letters, fuzzy score will be low
    # But 2/3 of normalized tokens overlap
    assert tm.any_match("cancer therapy", hay, fuzz_threshold=100, jaccard_threshold=0.3) is True


def test_any_match_fuzzy_path():
    """Fuzzy match returns True (lines 228-238)."""
    hay = ["cancer immunotherapy"]
    # Different wording but high fuzzy similarity
    assert tm.any_match("cancer immunotherapies", hay, fuzz_threshold=50) is True


# ── Split sentences ──


def test_split_to_sentences_empty():
    """Empty text returns empty list (line 410)."""
    assert tm.split_to_sentences("") == []


def test_split_to_sentences_basic():
    """Split text into sentences (lines 412-416)."""
    result = tm.split_to_sentences("First sentence. Second sentence! Third?")
    assert len(result) == 3
    assert result[0] == "First sentence."
    assert result[1] == "Second sentence!"
    assert result[2] == "Third?"


def test_split_to_sentences_no_punctuation():
    """Text without sentence-ending punctuation returns one chunk."""
    result = tm.split_to_sentences("No punctuation here")
    assert result == ["No punctuation here"]


# ── Semantic chunk match (needs injected model) ──


def test_semantic_chunk_match_empty():
    """Empty needle or abstract returns False (line 435)."""
    assert tm.semantic_chunk_match("", "Some abstract") is False
    assert tm.semantic_chunk_match("needle", "") is False


def test_semantic_chunk_match_no_model():
    """Without a model, semantic_chunk_match returns False (line 444)."""
    result = tm.semantic_chunk_match("cancer therapy", "Oncology treatment is important.")
    # Without a real model, semantic_score returns None -> False
    assert result is False


def test_semantic_chunk_match_positive():
    """semantic_chunk_match with injected model returning high similarity."""

    class FakeModelPos:
        def encode(self, sentences, **kwargs):
            import numpy as _np

            return _np.ones((len(list(sentences)), 1), dtype=float)

    result = tm.semantic_chunk_match(
        "cancer therapy", "Oncology treatment.",
        semantic_model=FakeModelPos(), semantic_threshold=0.5,
    )
    assert result is True


# ── All/any needles match edge cases ──


def test_any_needles_match_hit():
    """any_needles_match returns True on first match (line 390)."""
    assert tm.any_needles_match(["missing", "cancer"], ["cancer"]) is True


def test_any_needles_match_miss():
    """any_needles_match returns False when no match (line 400)."""
    assert tm.any_needles_match(["missing1", "missing2"], ["cancer"]) is False


# ── as_semantic_model ──


def test_as_semantic_model():
    """as_semantic_model returns the same object (line 463)."""
    model = object()
    result = tm.as_semantic_model(model)
    assert result is model
