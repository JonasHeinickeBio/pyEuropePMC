# Pipeline Skill

Use `PaperProcessingPipeline` to automate complex multi-step workflows (parsing → enrichment → RDF).

```python
from pyeuropepmc import PaperProcessingPipeline, PipelineConfig

config = PipelineConfig(
    enable_enrichment=True,
    enable_crossref=True,
    enable_semantic_scholar=True,
    enable_openalex=True,
    enable_ror=True,
    crossref_email="your.email@example.com",
    output_format="turtle",
    output_dir="output"
)

pipeline = PaperProcessingPipeline(config)

result = pipeline.process_paper(
    xml_content=xml,
    doi="10.1038/nature11476",
    save_rdf=True,
    filename_prefix="demo_"
)

print(f"Paper: {result['entities']['paper'].title}")
print(f"RDF triples: {result['triple_count']}")
```

Key tips:
- Single method call replaces manual parsing → enrichment → conversion chain
- Set `output_format="turtle"` or `"nt"`
- Use `progress_callback` for progress tracking
- Results include enrichment data, entities, and output file path
