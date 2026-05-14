# RDF Mapping Skill

Generate Knowledge Graphs in RDF/Turtle format using `RDFMapper` and `PaperProcessingPipeline`.

```python
from pyeuropepmc.processing.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mappers import RDFMapper

# Parse XML and build entities
parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, figures, references = build_paper_entities(parser)

# Map to RDF
mapper = RDFMapper()
triples = mapper.map_paper(paper, authors, sections, tables, figures, references)

# Export to Turtle
turtle_output = mapper.to_turtle()
```

Or use the unified pipeline:
```python
from pyeuropepmc import PaperProcessingPipeline, PipelineConfig

config = PipelineConfig(
    enable_enrichment=True,
    output_format="turtle",
    output_dir="output"
)
pipeline = PaperProcessingPipeline(config)

result = pipeline.process_paper(xml_content=xml, doi="10.xxxx/xxxx")
```

Key tips:
- Output formats: `turtle`, `nt` (N-Triples), `xml`
- KG structures: complete, metadata-only, or content-only
- RML mappings in `conf/` can be synced with `make sync-rdf`
