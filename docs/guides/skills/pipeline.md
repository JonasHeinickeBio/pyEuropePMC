# Pipeline skill

`PaperProcessingPipeline` parses a full-text XML article, enriches its metadata and converts the entities to RDF in one call. For the entities and the RDF mapping, see [Data models and RDF mapping](../../reference/models.md); for RDF conversion without the pipeline, see the [RDF mapping skill](rdf_mapping.md).

```python
from pyeuropepmc import FullTextClient, PaperProcessingPipeline, PipelineConfig

config = PipelineConfig(
    enable_enrichment=True,
    crossref_email="you@example.org",
    rdf_config_path="rdf_map.yml",
    output_format="turtle",
    output_dir="output",
)

with FullTextClient() as fulltext:
    xml = fulltext.get_fulltext_content("PMC3258128", format_type="xml")

with PaperProcessingPipeline(config) as pipeline:
    result = pipeline.process_paper(
        xml_content=xml,
        doi="10.1093/nar/gkr715",
        save_rdf=True,
        filename_prefix="demo_",
    )

print(f"Paper: {result['entities']['paper'].title}")
print(f"RDF triples: {result['triple_count']}")
print(f"Saved to: {result['output_file']}")
```

`PipelineConfig` parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `enable_cache` | `bool` | `True` | Cache API responses in memory |
| `cache_size_mb` | `int` | `500` | Cache size limit |
| `enable_enrichment` | `bool` | `True` | Run `PaperEnricher` for the paper's DOI or PMCID |
| `enable_crossref`, `enable_semantic_scholar`, `enable_openalex`, `enable_ror` | `bool` | `True` | Enrichment sources. Europe PMC and iCite always run when enrichment is on; Unpaywall and DataCite never do. |
| `crossref_email` | `str \| None` | `None` | Email for the CrossRef polite pool |
| `rdf_config_path` | `str \| None` | `None` | Path to `rdf_map.yml` |
| `output_format` | `str` | `"turtle"` | `turtle`, `nt`, `xml` or `json-ld` |
| `output_dir` | `str` | `"output"` | Output directory, created when the pipeline is constructed |

Key tips:
- `rdf_config_path`: the installed package does not include the mapping file `conf/rdf_map.yml`. Download it from the [repository](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/conf/rdf_map.yml) and pass its path. Without it, the constructor raises `FileNotFoundError` outside a source checkout.
- `process_paper(pmcid="PMC3258128")` without `xml_content` downloads the XML itself.
- The RDF file is named `<filename_prefix><identifier>.<ext>`, with `/`, `.` and `:` in the identifier replaced by `_`. The extension is `.ttl` for `turtle` and the format name otherwise (`.nt`, `.xml`, `.json-ld`).
- The result has `entities` (a dict with `paper`, `authors`, `sections`, `tables`, `figures`, `references`), `enrichment_data` (the `PaperEnricher.enrich_paper()` result, or `None`), `rdf_graph` (`rdflib.Graph`), `triple_count` and `output_file` (`Path`, or `None` when `save_rdf=False`).
- For several papers, use `pipeline.process_papers({"PMC3258128": xml, ...})`. It returns a dict of results and stores failures as `{"error": "..."}`. There is no progress callback.
- Known limitation: enrichment values are returned in `enrichment_data` but are not copied into the entities or the RDF graph. Citation counts in the graph come from Europe PMC search data.
- Known limitation: `entities["figures"]` is always an empty list, because the entity builder does not extract figures yet.
