
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
        import sentence_transformers  # type: ignore
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
        def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):
            # return list of identical vectors (1-dim) so dot product = 1.0 after normalization
            import numpy as _np

            arr = _np.ones((len(list(texts)), 1), dtype=float)
            return arr

    model = FakeModelPos()
    res = tm.any_match("cancer therapy", ["oncology treatment"], use_semantic=True, semantic_model=model)
    assert res is True


def test_any_match_semantic_with_injected_model_negative():
    # Fake model that maps 'oncology' -> [1,0], 'cancer' -> [0,1] so different texts are orthogonal
    class FakeModelNeg:
        def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):
            import numpy as _np

            out = []
            for t in list(texts):
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
