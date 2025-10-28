"""
Text matching helpers: normalization, token matching, fuzzy matching and optional semantic scoring.

This module provides small, dependency-light helpers (RapidFuzz) and an
optional sentence-transformers based semantic scorer. Functions are written
to be reusable and small so filters can call them with sensible defaults.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
import re
from typing import Any, Protocol, cast
import unicodedata

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """Lowercase, remove diacritics and punctuation, collapse whitespace."""
    if not text:
        return ""
    s = str(text).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    logger.debug("normalize: %r -> %r", text, s)
    return s


def tokens(text: str) -> list[str]:
    """Return whitespace tokens from normalized text."""
    n = normalize(text)
    return n.split() if n else []


def token_jaccard(a: str, b: str) -> float:
    """Jaccard overlap of token sets between a and b (0..1)."""
    A = set(tokens(a))
    B = set(tokens(b))
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def token_fuzzy_score(a: str, b: str) -> float:
    """Token-aware fuzzy score (0..100) using RapidFuzz token_set_ratio."""
    score = fuzz.token_set_ratio(normalize(a), normalize(b))
    logger.debug("token_fuzzy_score: %r vs %r = %s", a, b, score)
    return float(score)


class SemanticModelProtocol(Protocol):
    """Protocol describing the minimal interface we need from a semantic model.

    This mirrors sentence-transformers' SentenceTransformer.encode signature at a
    high level without importing the package at runtime.
    """

    def encode(
        self,
        sentences: Iterable[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = False,
        convert_to_tensor: bool = False,
        device: Any | None = None,
        normalize_embeddings: bool = False,
    ) -> Any:
        """Encode sentences into embeddings.

        The signature intentionally mirrors SentenceTransformer.encode so a
        real SentenceTransformer instance will conform to this Protocol.
        Implementations (including tests) may accept a smaller subset of
        parameters; callers should only rely on the common ones used here.
        """
        ...


class SemanticModel:
    """Adapter around a sentence-transformers backend that implements the
    runtime API callers expect.

    The class lazily imports and instantiates the SentenceTransformer (or a
    provided backend) and exposes an ``encode`` method compatible with the
    :class:`SemanticModelProtocol` Protocol. It also delegates other attribute
    access to the underlying model once loaded.
    """

    # In-process cache for loaded models: (backend, model_name, cache_folder) -> model_instance
    _MODEL_CACHE: dict[tuple[int, str, str | None], Any] = {}

    def __init__(
        self,
        model: Any | None = None,
        *,
        model_name_or_path: str | None = None,
        backend: Any | None = None,
        show_load_logs: bool = True,
        cache_folder: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        model : Any | None
            Pre-instantiated model (optional).
        model_name_or_path : str | None
            Model name or path to load (default: 'all-MiniLM-L6-v2').
        backend : Any | None
            Model backend class (default: SentenceTransformer).
        show_load_logs : bool
            Whether to log model loading events.
        cache_folder : str | None
            Optional directory for file system cache of downloaded models.
            If provided, will be passed to SentenceTransformer as cache_folder.
        """
        self._model = model
        self._model_name = model_name_or_path
        self._backend = backend
        self._show_load_logs = bool(show_load_logs)
        self._cache_folder = cache_folder

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return

        backend = self._backend
        if backend is None:
            # Import here to avoid requiring sentence-transformers at module import time.
            from sentence_transformers import SentenceTransformer

            backend = SentenceTransformer

        model_name = self._model_name or "all-MiniLM-L6-v2"
        cache_key = (id(backend), model_name, self._cache_folder)
        if cache_key in self._MODEL_CACHE:
            self._model = self._MODEL_CACHE[cache_key]
            if self._show_load_logs:
                logger.info(
                    "SemanticModel: loaded model %r from cache using backend %r (cache_folder=%r)",
                    model_name,
                    getattr(backend, "__name__", backend),
                    self._cache_folder,
                )
            return

        if self._show_load_logs:
            logger.info(
                "SemanticModel: loading model %r using backend %r (cache_folder=%r)",
                model_name,
                getattr(backend, "__name__", backend),
                self._cache_folder,
            )
        try:
            # Pass cache_folder to SentenceTransformer if provided
            if self._cache_folder is not None:
                model_instance = backend(model_name, cache_folder=self._cache_folder)
            else:
                model_instance = backend(model_name)
            self._MODEL_CACHE[cache_key] = model_instance
            self._model = model_instance
        except Exception:
            logger.exception("SemanticModel: failed to load model %r", model_name)
            raise

    def encode(
        self,
        sentences: Iterable[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = False,
        convert_to_tensor: bool = False,
        device: Any | None = None,
        normalize_embeddings: bool = False,
    ) -> Any:
        self._ensure_model_loaded()
        if self._model is None:  # pragma: no cover - defensive check after _ensure_model_loaded
            raise RuntimeError("Model failed to load")
        kwargs = {
            "batch_size": batch_size,
            "show_progress_bar": show_progress_bar,
            "convert_to_numpy": convert_to_numpy,
            "convert_to_tensor": convert_to_tensor,
            "device": device,
            "normalize_embeddings": normalize_embeddings,
        }
        return cast(Any, self._model).encode(sentences, **kwargs)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - delegation
        self._ensure_model_loaded()
        if self._model is None:  # pragma: no cover - defensive check after _ensure_model_loaded
            raise RuntimeError("Model failed to load")
        return getattr(self._model, name)


def any_match(
    needle: str,
    hay_values: Iterable[str],
    *,
    fuzz_threshold: int = 85,
    jaccard_threshold: float = 0.5,
    use_semantic: bool = False,
    semantic_threshold: float = 0.7,
    semantic_model: SemanticModelProtocol | None = None,
) -> bool:
    """Return True if the needle matches any of the hay_values.

    Strategy (fast -> slow): substring -> fuzzy -> jaccard -> optional semantic
    """
    if not needle:
        return False
    n = normalize(needle)
    hay = [hv for hv in hay_values if hv]
    if not hay:
        return False

    # 1) quick substring checks
    for h in hay:
        hn = normalize(h)
        if n in hn or hn in n:
            logger.debug("any_match: substring match needle=%r hay=%r", needle, h)
            return True

    # 2) fuzzy and 3) jaccard checks
    for h in hay:
        if token_fuzzy_score(n, h) >= fuzz_threshold:
            logger.debug(
                "any_match: fuzzy match needle=%r hay=%r score=%s thresh=%s",
                needle,
                h,
                token_fuzzy_score(n, h),
                fuzz_threshold,
            )
            return True
        if token_jaccard(n, h) >= jaccard_threshold:
            logger.debug(
                "any_match: jaccard match needle=%r hay=%r score=%s thresh=%s",
                needle,
                h,
                token_jaccard(n, h),
                jaccard_threshold,
            )
            return True

    # 4) semantic fallback (optional)
    if not use_semantic:
        logger.debug("any_match: semantic disabled for needle=%r", needle)
        return False

    logger.debug("any_match: attempting semantic match for needle=%r", needle)
    return _semantic_match(
        needle,
        hay,
        semantic_threshold=semantic_threshold,
        semantic_model=semantic_model,
    )


def _semantic_match(
    needle: str,
    hay_values: Iterable[str],
    *,
    semantic_threshold: float = 0.7,
    semantic_model: SemanticModelProtocol | None = None,
) -> bool:
    """Semantic similarity match using sentence-transformers if available.

    Returns True if the maximum cosine similarity between the needle and any hay value
    (using normalized sentence-transformers embeddings) meets the threshold.

    Any import or runtime error (missing dependency, model load failure) is treated
    as a non-match and returns False so the caller can continue gracefully.
    """
    # Use the score function and compare to threshold for boolean result.
    score = semantic_score(needle, hay_values, semantic_model=semantic_model)
    if score is None:
        return False
    return float(score) >= float(semantic_threshold)


def semantic_score(
    needle: str,
    hay_values: Iterable[str],
    *,
    semantic_model: SemanticModelProtocol | None = None,
) -> float | None:
    """Return the maximum cosine similarity between needle and any hay value.

    Returns a float in [0.0, 1.0] or None if semantic matching is not available
    (missing dependency, model failure, or other error).
    """
    try:
        # Import lazily to avoid heavy import at module import time
        import numpy as _np
        from numpy.typing import NDArray

        model = semantic_model or SemanticModel()
        logger.debug("semantic_score: using model %r", getattr(model, "__class__", model))

        # Try to obtain numpy arrays from the model output. Accept numpy or
        # torch tensors (user-provided models/tests may return either).
        vecs_h = _np.asarray(
            model.encode(
                list(hay_values),
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        )
        vec_n = _np.asarray(
            model.encode(
                [needle],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        )

        # Ensure shapes: vecs_h -> (N, D), vec_n -> (1, D) or (D,)
        if vec_n.ndim == 1:
            vec_n = vec_n.reshape(1, -1)

        # Normalize to unit vectors (safety) unless already normalized
        def _safe_normalize(x: NDArray[Any]) -> NDArray[Any]:
            norms = _np.linalg.norm(x, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            result: NDArray[Any] = x / norms
            return result

        vecs_h = _safe_normalize(vecs_h)
        vec_n = _safe_normalize(vec_n)

        sims = (vecs_h @ vec_n.T).ravel()
        max_sim = float(sims.max()) if sims.size else 0.0
        logger.debug(
            "semantic_score: needle=%r max_sim=%s",
            needle,
            max_sim,
        )
        # Clamp to [0,1]
        max_sim = max(0.0, min(1.0, max_sim))
        return max_sim
    except Exception as exc:  # pragma: no cover - defensive logging on runtime errors
        logger.exception("semantic scoring failed: %s", exc)
        # Missing dependency, model failure, or other runtime error: return None
        return None


def all_needles_match(
    needles: Iterable[str],
    hay_values: Iterable[str],
    *,
    fuzz_threshold: int = 85,
    jaccard_threshold: float = 0.5,
    use_semantic: bool = False,
    semantic_threshold: float = 0.7,
    semantic_model: SemanticModelProtocol | None = None,
) -> bool:
    """Return True if ALL needles match (each needle matches any hay value)."""
    hay_list = list(hay_values)
    for n in needles:
        if not any_match(
            n,
            hay_list,
            fuzz_threshold=fuzz_threshold,
            jaccard_threshold=jaccard_threshold,
            use_semantic=use_semantic,
            semantic_threshold=semantic_threshold,
            semantic_model=semantic_model,
        ):
            return False
    return True


def any_needles_match(
    needles: Iterable[str],
    hay_values: Iterable[str],
    *,
    fuzz_threshold: int = 85,
    jaccard_threshold: float = 0.5,
    use_semantic: bool = False,
    semantic_threshold: float = 0.7,
    semantic_model: SemanticModelProtocol | None = None,
) -> bool:
    """Return True if ANY needle matches any hay value."""
    hay_list = list(hay_values)
    for n in needles:
        if any_match(
            n,
            hay_list,
            fuzz_threshold=fuzz_threshold,
            jaccard_threshold=jaccard_threshold,
            use_semantic=use_semantic,
            semantic_threshold=semantic_threshold,
            semantic_model=semantic_model,
        ):
            return True
    return False


def split_to_sentences(text: str) -> list[str]:
    """Split text into sentence-like chunks using a simple regexp.

    This is intentionally light-weight (no heavy NLP dependency). It returns
    non-empty stripped sentences. Callers can further chunk sentences if
    desired.
    """
    if not text:
        return []
    # Basic sentence splitter: split on punctuation that commonly ends sentences.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [p.strip() for p in parts if p and p.strip()]
    logger.debug("split_to_sentences: %d sentences", len(sentences))
    return sentences


def semantic_chunk_match(
    needle: str,
    abstract: str,
    *,
    semantic_model: SemanticModelProtocol | None = None,
    semantic_threshold: float = 0.72,
    sentence_chunker: Callable[[str], list[str]] | None = None,
) -> bool:
    """Semantic match where abstract is split into sentence chunks.

    The function splits `abstract` into sentence chunks (via `sentence_chunker` or
    `split_to_sentences`), encodes each chunk and the `needle`, and returns True
    if the maximum similarity >= `semantic_threshold`.

    Returns False if semantic scoring is unavailable or on error.
    """
    if not needle or not abstract:
        return False

    chunker = sentence_chunker or split_to_sentences
    chunks = chunker(abstract)
    if not chunks:
        return False

    score = semantic_score(needle, chunks, semantic_model=semantic_model)
    if score is None:
        return False
    logger.debug(
        "semantic_chunk_match: needle=%r max_score=%s thresh=%s",
        needle,
        score,
        semantic_threshold,
    )
    return float(score) >= float(semantic_threshold)


def as_semantic_model(x: Any) -> SemanticModelProtocol:
    """Cast an object to ``SemanticModelProtocol`` for use in typed APIs.

    This is a convenience for callers who want to pass a third-party model
    (for example a raw SentenceTransformer instance) to functions that are
    annotated with ``SemanticModelProtocol``. It performs a typing.cast only
    and does not perform runtime validation.
    """
    return cast(SemanticModelProtocol, x)


__all__ = [
    "normalize",
    "tokens",
    "token_jaccard",
    "token_fuzzy_score",
    "any_match",
    "all_needles_match",
    "any_needles_match",
    "semantic_score",
    "semantic_chunk_match",
    "SemanticModel",
    "as_semantic_model",
    "split_to_sentences",
]
