# Annotations skill card

Retrieve Europe PMC text-mining annotations (entities, relationships, sentences) with `AnnotationsClient` and parse them with `parse_annotations()`.

```python
from pyeuropepmc import AnnotationsClient, parse_annotations

with AnnotationsClient() as client:
    annotations = client.get_annotations_by_article_ids(
        article_ids=["PMC3359311"],
        section="abstract",  # "abstract", "fulltext" or "all"
        format="JSON-LD",
    )
    parsed = parse_annotations(annotations)
    print(f"Entities: {len(parsed['entities'])}")
    print(f"Relationships: {len(parsed['relationships'])}")

    ethanol = client.get_annotations_by_entity(entity_id="CHEBI:16236", entity_type="CHEBI")
```

Key tips:

- `get_annotations_by_article_ids(article_ids, section=None, provider=None, annotation_type=None, format="JSON-LD")` sends `PMC3359311` as `PMC:3359311`. `section=None` or `"all"` covers the whole article; `annotation_type` is sent as the `type` filter.
- `get_annotations_by_entity(entity_id, entity_type, provider=None, section=None, page=1, page_size=25, format="JSON-LD")` returns annotations for one entity across articles.
- Both methods return a dict with `entities`, `sentences`, `relationships`, `metadata`, `raw` and `valid`, plus `annotations` when the response contains them.
- Formats are `"JSON-LD"`, `"JSON"` and `"XML"`; an unknown `section` or `format` raises `ValidationError`.
- The accepted entity types, providers and annotation types are defined by the [Europe PMC Annotations API](https://europepmc.org/AnnotationsApi).
- Caching is off by default; pass `cache_config=CacheConfig(enabled=True)`. See [Caching](../../features/caching/README.md).
