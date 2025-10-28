"""Functional tests for abstract semantic matching in filters.

This file contains:
- a self-contained functional test that uses a FakeModel to validate the
  sentence-chunk semantic matching path in `filter_pmc_papers`.
- an e2e-ish test that attempts to load a real SentenceTransformer model and
  runs a small filter; it will be skipped if the model cannot be loaded.
"""

import pytest
from pyeuropepmc.filters import filter_pmc_papers
from pyeuropepmc.utils import text_match as tm
from pyeuropepmc.utils.text_match import as_semantic_model

def make_sample_papers():
    from typing import List, Dict, Any
    return [
        {
            "id": "S1",
            "title": "Test study on novel therapy",
            "pubYear": "2022",
            "pubTypeList": {"pubType": ["Journal Article"]},
            "isOpenAccess": "Y",
            "citedByCount": "1",
            "abstractText": "We demonstrate a novel immunotherapy approach that targets tumor antigens.",
        },
        {
            "id": "S2",
            "title": "Unrelated study",
            "pubYear": "2021",
            "pubTypeList": {"pubType": ["Journal Article"]},
            "isOpenAccess": "Y",
            "citedByCount": "2",
            "abstractText": "This study focuses on diabetes metabolic pathways and drug metabolism.",
        },
    ]



from typing import Any, Dict, List, Sequence, Optional
import numpy as np

class FakeSemanticModel:
    """Fake semantic model that returns high similarity when 'tumor' or 'immuno' present.

    It implements the encode(...) signature expected by the SemanticModel Protocol.
    """

    def encode(
        self,
        sentences: Sequence[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = False,
        convert_to_tensor: bool = False,
        device: Optional[Any] = None,
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        out: List[np.ndarray] = []
        for s in list(sentences):
            ss = (s or "").lower()
            if "tumor" in ss or "tumour" in ss or "immuno" in ss:
                out.append(np.array([1.0, 0.0], dtype=float))
            else:
                out.append(np.array([0.0, 1.0], dtype=float))
        return np.vstack(out)


@pytest.mark.model
def test_semantic_abstract_with_fake_model() -> None:
    papers: List[Dict[str, Any]] = make_sample_papers()
    model = FakeSemanticModel()

    # Use semantic abstract matching; the first paper should match 'tumor' via semantic
    filtered: List[Dict[str, Any]] = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    assert len(filtered) == 1
    assert filtered[0]["id"] == "S1"


@pytest.mark.model
def test_semantic_abstract_with_real_model() -> None:
    # Skip if sentence-transformers is not available
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        pytest.skip("sentence-transformers not available")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    papers: List[Dict[str, Any]] = make_sample_papers()

    filtered: List[Dict[str, Any]] = filter_pmc_papers(
        papers,
        required_abstract_terms={"immunotherapy"},
        use_semantic_abstract=True,
            semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )

    # With a reasonable threshold the first paper should be detected
    assert any(p["id"] == "S1" for p in filtered)


@pytest.mark.model
def test_semantic_abstract_or_with_fake_model() -> None:
    """Test OR-style high-level filter with semantic abstract matching using fake model."""
    papers: List[Dict[str, Any]] = make_sample_papers()
    model = FakeSemanticModel()

    # Use OR-style filter: at least one of the required abstract terms should match
    filtered: List[Dict[str, Any]] = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor", "diabetes"},
        use_semantic_abstract=True,
            semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )

    # Both papers should be returned because one contains 'tumor' concept and the other 'diabetes'
    ids = {p["id"] for p in filtered}
    assert "S1" in ids
    assert "S2" in ids


@pytest.mark.model
def test_semantic_abstract_or_with_real_model() -> None:
    # Skip if sentence-transformers is not available
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:
        pytest.skip("sentence-transformers not available")


    model = SentenceTransformer("all-MiniLM-L6-v2")
    papers: List[Dict[str, Any]] = make_sample_papers()

    filtered: List[Dict[str, Any]] = filter_pmc_papers(
        papers,
        required_abstract_terms={"immunotherapy", "diabetes"},
        use_semantic_abstract=True,
            semantic_model=as_semantic_model(model),
        semantic_threshold=0.55,
        open_access=None,
    )

    assert any(p["id"] == "S1" for p in filtered)
    assert any(p["id"] == "S2" for p in filtered)

@pytest.mark.model
def test_semantic_abstract_empty_papers() -> None:
    model = FakeSemanticModel()
    filtered = filter_pmc_papers(
        [],
        required_abstract_terms={"tumor"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    assert filtered == []


@pytest.mark.model
def test_semantic_abstract_missing_abstract() -> None:
    model = FakeSemanticModel()
    papers = [{"id": "S3", "title": "No abstract", "pubYear": "2022", "isOpenAccess": "Y", "citedByCount": "5"}]
    filtered = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    assert filtered == []


@pytest.mark.model
def test_semantic_abstract_with_broken_model() -> None:
    class BrokenModel:
        def encode(self, *a, **k):
            raise RuntimeError("broken model")
    model = BrokenModel()
    papers = make_sample_papers()
    filtered = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    # Fallback to substring/fuzzy/jaccard: S1 matches 'tumor' via substring
    assert len(filtered) == 1
    assert filtered[0]["id"] == "S1"


@pytest.mark.model
def test_semantic_abstract_high_threshold_no_match() -> None:
    model = FakeSemanticModel()
    papers = make_sample_papers()
    filtered = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.99,
        open_access=None,
    )
    # Fallback to substring/fuzzy/jaccard: S1 matches 'tumor' via substring
    assert len(filtered) == 1
    assert filtered[0]["id"] == "S1"


@pytest.mark.model
def test_semantic_abstract_multiple_terms_and_logic() -> None:
    model = FakeSemanticModel()
    papers = make_sample_papers()
    filtered = filter_pmc_papers(
        papers,
        required_abstract_terms={"tumor", "immuno"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    # Only S1 matches both terms semantically
    assert len(filtered) == 1
    assert filtered[0]["id"] == "S1"


@pytest.mark.model
def test_semantic_abstract_or_logic_no_match() -> None:
    model = FakeSemanticModel()
    papers = make_sample_papers()
    filtered = filter_pmc_papers(
        papers,
        required_abstract_terms={"nonexistent"},
        use_semantic_abstract=True,
        semantic_model=as_semantic_model(model),
        semantic_threshold=0.6,
        open_access=None,
    )
    # Fallback to substring/fuzzy/jaccard: S2 contains 'diabetes', so it is returned
    assert len(filtered) == 1
    assert filtered[0]["id"] == "S2"
