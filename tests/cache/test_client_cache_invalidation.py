"""Regression tests for the client cache invalidation defaults.

``SearchClient.invalidate_search_cache()`` and
``AnnotationsClient.invalidate_annotations_cache()`` used to default to
``"search:*"`` and ``"annotations:*"``, which matched none of the keys those
clients write (they start with the data type, e.g.
``general:v1:search:<hash>``). ``FullTextClient.invalidate_fulltext_cache()``
matched any key whose ID merely started with the given one.

These tests drive the real cache backends the clients build, without making
any network request.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.cache.cache import CacheBackend, CacheConfig
from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient
from pyeuropepmc.features.literature.annotations import AnnotationsClient
from pyeuropepmc.features.literature.search import SearchClient


@pytest.fixture
def search_client(tmp_path):
    client = SearchClient(cache_config=CacheConfig(enabled=True, cache_dir=tmp_path))
    yield client
    client.close()


@pytest.fixture
def annotations_client(tmp_path):
    client = AnnotationsClient(cache_config=CacheConfig(enabled=True, cache_dir=tmp_path))
    yield client
    client.close()


class TestSearchCacheInvalidation:
    def test_default_pattern_removes_the_entries_search_writes(self, search_client):
        cache = search_client._cache
        get_key = cache._normalize_key("search", query="cancer", pageSize=25)
        post_key = cache._normalize_key("search_post", query="cancer", pageSize=25)
        cache.set(get_key, {"hitCount": 1})
        cache.set(post_key, {"hitCount": 2})

        assert search_client.invalidate_search_cache() == 2

        assert cache.get(get_key) is None
        assert cache.get(post_key) is None

    def test_default_pattern_leaves_other_clients_entries_alone(self, search_client):
        cache = search_client._cache
        search_key = cache._normalize_key("search", query="cancer")
        annotations_key = cache._normalize_key("annotations_by_ids", articleIds="MED:1")
        cache.set(search_key, {"hitCount": 1})
        cache.set(annotations_key, {"annotations": []})

        assert search_client.invalidate_search_cache() == 1

        assert cache.get(annotations_key) == {"annotations": []}

    def test_a_narrower_pattern_selects_one_endpoint(self, search_client):
        cache = search_client._cache
        get_key = cache._normalize_key("search", query="cancer")
        post_key = cache._normalize_key("search_post", query="cancer")
        cache.set(get_key, {"hitCount": 1})
        cache.set(post_key, {"hitCount": 2})

        assert search_client.invalidate_search_cache("*:search_post:*") == 1

        assert cache.get(get_key) == {"hitCount": 1}
        assert cache.get(post_key) is None


class TestAnnotationsCacheInvalidation:
    def test_default_pattern_removes_every_annotations_entry(self, annotations_client):
        cache = annotations_client._cache
        keys = [
            cache._normalize_key("annotations_by_ids", articleIds="MED:1"),
            cache._normalize_key("annotations_by_entity", entity="CHEBI"),
            cache._normalize_key("annotations_by_provider", provider="Europe PMC"),
        ]
        for key in keys:
            cache.set(key, {"annotations": []})

        assert annotations_client.invalidate_annotations_cache() == 3

        assert all(cache.get(key) is None for key in keys)

    def test_default_pattern_leaves_search_entries_alone(self, annotations_client):
        cache = annotations_client._cache
        annotations_key = cache._normalize_key("annotations_by_ids", articleIds="MED:1")
        search_key = cache._normalize_key("search", query="cancer")
        cache.set(annotations_key, {"annotations": []})
        cache.set(search_key, {"hitCount": 1})

        assert annotations_client.invalidate_annotations_cache() == 1

        assert cache.get(search_key) == {"hitCount": 1}


class TestFullTextCacheInvalidation:
    def test_one_id_does_not_remove_longer_ids(self, tmp_path):
        client = FullTextClient(cache_config=CacheConfig(enabled=True, cache_dir=tmp_path))
        try:
            cache = client._cache
            cache.set("fulltext_availability:123", {"pdf": True})
            cache.set("fulltext_availability:1234", {"pdf": False})

            assert client.invalidate_fulltext_cache("PMC123") == 1

            assert cache.get("fulltext_availability:123") is None
            assert cache.get("fulltext_availability:1234") == {"pdf": False}
        finally:
            client.close()

    def test_no_argument_removes_everything(self, tmp_path):
        client = FullTextClient(cache_config=CacheConfig(enabled=True, cache_dir=tmp_path))
        try:
            cache = client._cache
            cache.set("fulltext_availability:123", {"pdf": True})
            cache.set("fulltext_availability:1234", {"pdf": False})

            assert client.invalidate_fulltext_cache() == 2
            assert cache.get("fulltext_availability:1234") is None
        finally:
            client.close()


class TestInvalidatePatternAgainstRealKeys:
    """The patterns above have to match the documented key format."""

    def test_key_format_is_type_version_prefix_hash(self, tmp_path):
        backend = CacheBackend(CacheConfig(enabled=True, cache_dir=tmp_path))
        try:
            key = backend._normalize_key("search", query="cancer")
            head, version, prefix, digest = key.split(":")

            assert head == "general"
            assert version == "v1"
            assert prefix == "search"
            assert len(digest) == 16
        finally:
            backend.close()
