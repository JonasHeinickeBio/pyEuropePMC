# Annotations Skill

Retrieve and parse text-mining annotations (entities, relationships, sentences) from Europe PMC.

```python
from pyeuropepmc import AnnotationsClient
from pyeuropepmc.processing.annotation_parser import parse_annotations

client = AnnotationsClient()

# Get annotations for articles
annotations = client.get_annotations_by_article_ids(
    article_ids=["PMC3359311"],
    section="abstract",  # or "fulltext", "all"
    format="JSON-LD"
)

# Parse to structured data
parsed = parse_annotations(annotations)
print(f"Entities: {len(parsed['entities'])}")
print(f"Relationships: {len(parsed['relationships'])}")

# Search by entity
entity_annotations = client.get_annotations_by_entity(
    entity_id="CHEBI:16236",
    entity_type="CHEBI"
)
```

Key tips:
- Entity types: `CHEBI`, `GO`, `TAX`, `CHEM`, `GOT`, `TAXN`
- Sections: `"abstract"`, `"fulltext"`, `"all"`
- Cache with `cache_config` for repeated queries
