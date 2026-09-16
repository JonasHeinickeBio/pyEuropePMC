# RDF mapping skill

Convert a parsed article into an RDF knowledge graph with `build_paper_entities` and `RDFMapper`. For parsing, enrichment and conversion in one call, see the [Pipeline skill](pipeline.md); for entity fields and predicates, see [Data models and RDF mapping](../../reference/models.md).

```python
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mappers import RDFMapper

with open("PMC3258128.xml", encoding="utf-8") as fh:
    parser = FullTextXMLParser(fh.read())

# (paper, authors, sections, tables, figures, references)
entities = build_paper_entities(parser)

mapper = RDFMapper(config_path="rdf_map.yml")
graphs = mapper.convert_and_save_papers_to_rdf({"PMC3258128": entities}, output_dir="rdf_output")

graph = graphs["PMC3258128"]
print(len(graph), "triples")  # also written to rdf_output/paper_PMC3258128.ttl
turtle = mapper.serialize_graph(graph, format="turtle")
```

Key tips:
- `RDFMapper()` uses the [`rdf_map.yml`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rdf_map.yml) that ships with the package; pass `config_path` to use your own.
- `build_paper_entities()` returns six values. Unpacking five raises `ValueError`.
- `serialize_graph(graph, format=...)` accepts rdflib formats such as `turtle`, `nt`, `xml` and `json-ld`. With `destination="out.ttl"` it writes the file.
- To choose the knowledge-graph structure, call `mapper.save_rdf({"PMC3258128": {"entity": paper, "related_entities": {"authors": authors, ...}}}, output_dir="rdf_output", kg_type="metadata")`. `kg_type` is `"complete"` (the default: all entities), `"metadata"` (paper, authors, institutions) or `"content"` (sections, references, tables, figures). `save_metadata_rdf()` and `save_content_rdf()` do the same with the file prefixes `metadata_` and `content_`.
- `rdf_map.yml` is also the source of the RML file `rml_mappings.ttl` used by `RMLRDFizer`; both are in `src/pyeuropepmc/conf/`. Known limitation: the generator `examples/scripts/sync_rdf_mappings.py` stops with `TypeError: string indices must be integers` on the current `rdf_map.yml` (also when run as `make sync-rdf`), so the RML file cannot be regenerated after YAML edits.
