# RML mappings

`RMLRDFizer` converts entities to RDF with RML (RDF Mapping Language) mappings executed by SDM-RDFizer. It is an alternative to the YAML-driven `RDFMapper` described in [Data models and RDF mapping](models.md). This page covers installation, the configuration files, the Python API, the conversion script and troubleshooting.

## RDFMapper or RMLRDFizer

| | `RDFMapper` | `RMLRDFizer` |
|---|---|---|
| Mapping | `rdf_map.yml` | `rml_mappings.ttl`, generated from `rdf_map.yml`, plus `rdfizer_config.ini` |
| Extra package | None | `rdfizer` |
| Output | Entities with their relationships, provenance and `owl:sameAs` links; used by `PaperProcessingPipeline` | Flat properties of one entity type per call |
| Subject URIs | PubMed, DOI, PMC or `https://w3id.org/pyeuropepmc/...` URIs | `http://example.org/data/<type>/<id>` |
| Execution | In process | Each call writes JSON to a temporary directory and runs SDM-RDFizer on it, which took several seconds per call in testing |

Use `RMLRDFizer` when you need the mapping in the RML standard, for example to run it with other RML processors.

## Installation

```bash
pip install pyeuropepmc rdfizer
```

`rdfizer` (SDM-RDFizer) is neither a dependency nor an extra of pyeuropepmc. `pyeuropepmc.mappers.RDFIZER_AVAILABLE` is `True` when it can be imported. Without it, `RMLRDFizer()` raises `ImportError: rdfizer package not found. Install it with: pip install rdfizer`.

## Configuration files

Both files ship with the package ([`rml_mappings.ttl`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rml_mappings.ttl) and [`rdfizer_config.ini`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rdfizer_config.ini) in `src/pyeuropepmc/conf/`), and `RMLRDFizer()` uses them unless you pass other paths.

### rml_mappings.ttl

`examples/scripts/sync_rdf_mappings.py` generates this file from `rdf_map.yml` (see [Changing the mapping](#changing-the-mapping)). It has one triples map per entity class, and each map reads a JSON file:

```turtle
<#ScholarlyWorkEntityMap>
    rml:logicalSource [
        rml:source "scholarlywork.json" ;
        rml:referenceFormulation ql:JSONPath ;
        rml:iterator "$[*]"
    ] ;

    rr:subjectMap [
        rr:template "http://example.org/data/scholarlywork/{id}" ;
        rr:class bibo:Document
    ] ;

    rr:predicateObjectMap [
        rr:predicate dcterms:title ;
        rr:objectMap [ rml:reference "title" ; rr:datatype xsd:string ]
    ] ;
```

| `entity_type` | JSON file | Triples map |
|---|---|---|
| `paper` | `paper.json` | `PaperEntityMap` |
| `author` | `authors.json` | `AuthorEntityMap` |
| `section` | `sections.json` | `SectionEntityMap` |
| `table` | `tables.json` | `TableEntityMap` |
| `tablerow` | `table_rows.json` | `TableRowEntityMap` |
| `reference` | `references.json` | `ReferenceEntityMap` |
| `journal` | `journal.json` | `JournalEntityMap` |
| `grant` | `grant.json` | `GrantEntityMap` |
| `institution` | `institutions.json` | `InstitutionEntityMap` |
| `scholarlywork` | `scholarlywork.json` | `ScholarlyWorkEntityMap` |

Known limitation: a triples map contains only the fields listed for its own class in `rdf_map.yml`, not fields inherited from a parent class. For example, paper output from `RMLRDFizer` has no `dcterms:title`, `bibo:volume` or `bibo:pages` triples, because those fields are defined under `ScholarlyWorkEntity`.

### rdfizer_config.ini

```ini
[default]
# SDM-RDFizer Configuration for PyEuropePMC

# Main paths
main_directory: .

# Mapping file (RML mappings in Turtle format)
mapping: conf/rml_mappings.ttl

# Output configuration
output_folder: output
output_format: nt
only_printable_characters: yes

# Performance settings
number_of_datasets: 1
large_file: false
ordered: false

# Metadata
all_in_one_file: yes
name: pyeuropepmc_rdf
enrichment: yes

# Database configuration (leave empty for file-based sources)
[datasets]
remove_duplicate: no
enrichment: no
output_folder: output
all_in_one_file: yes
name: pyeuropepmc_rdf
number_of_datasets: 1
ordered: false

[dataset1]
mapping: conf/rml_mappings.ttl
name: pyeuropepmc_rdf
```

`RMLRDFizer` does not run these files as they are. For each call it copies both to a temporary directory, replaces the lines `main_directory: .`, `output_folder: output` and `mapping: conf/rml_mappings.ttl` with paths in that directory, and points the mapping's JSON sources there. The replacements match the exact text, so keep those three lines unchanged in a custom configuration. The N-Triples output is then loaded into an rdflib `Graph`.

## Python API

```python
from pyeuropepmc.mappers import RDFIZER_AVAILABLE, RMLRDFizer
from pyeuropepmc.models import PaperEntity

print(RDFIZER_AVAILABLE)

rdfizer = RMLRDFizer()  # the packaged rdfizer_config.ini and rml_mappings.ttl

paper = PaperEntity(pmcid="PMC1234567", doi="10.1234/example.2024.001", title="Example Paper")
g = rdfizer.entities_to_rdf([paper], entity_type="paper")
print(g.serialize(format="turtle"))
```

Output:

```turtle
@prefix bibo: <http://purl.org/ontology/bibo/> .
@prefix ns1: <https://w3id.org/pyeuropepmc/vocab#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/data/paper/10.1234%2Fexample.2024.001> a bibo:AcademicArticle ;
    rdfs:label "Example Paper" ;
    bibo:doi "10.1234/example.2024.001"^^xsd:anyURI ;
    ns1:pmcid "PMC1234567"^^xsd:string .
```

| Member | Description |
|---|---|
| `RMLRDFizer(config_path=None, mapping_path=None)` | `None` uses the packaged `rdfizer_config.ini` and `rml_mappings.ttl`. Raises `ImportError` without `rdfizer`, and `FileNotFoundError` (`Config file not found: <path>` or `Mapping file not found: <path>`) when a file is missing. |
| `entities_to_rdf(entities, entity_type, output_format="turtle")` | Returns an rdflib `Graph` for a list of entities of one type (see the table above). For `paper` and `scholarlywork`, an entity without `id` gets its DOI, PMCID or `pmid:<PMID>` as `id`. Known limitation: other entity types get no such fallback, and because the subject templates use `{id}`, entities without `id` produce no triples; set `id` first (see [Converting a whole article](#converting-a-whole-article)). `output_format` has no effect. |
| `convert_json_to_rdf(json_data, entity_type, output_format="turtle")` | Returns a `Graph` for a dict, or a list of dicts, shaped like `entity.to_dict()` |

SDM-RDFizer prints progress messages and writes `error.log` to the current working directory.

### Converting JSON

```python
from pyeuropepmc.mappers import RMLRDFizer

rdfizer = RMLRDFizer()

json_data = {
    "id": "PMC123",
    "pmcid": "PMC123",
    "doi": "10.1234/test",
    "keywords": ["biology", "medicine"],
}
g = rdfizer.convert_json_to_rdf(json_data, entity_type="paper")

query = """
PREFIX dct: <http://purl.org/dc/terms/>
SELECT ?keyword WHERE { ?paper dct:subject ?keyword }
"""
for row in g.query(query):
    print(row.keyword)
```

## Converting a whole article

```python
from rdflib import Graph

from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mappers import RMLRDFizer

with open("PMC3258128.xml", encoding="utf-8") as fh:
    parser = FullTextXMLParser(fh.read())

paper, authors, sections, tables, figures, references = build_paper_entities(parser)
for entity in [paper, *authors, *sections, *references]:
    entity.normalize()

# The subject templates need an id, and build_paper_entities() sets none for these entities.
for kind, entities in (("author", authors), ("section", sections), ("reference", references)):
    for number, entity in enumerate(entities, start=1):
        entity.id = f"PMC3258128-{kind}-{number}"

rdfizer = RMLRDFizer()

g = Graph()
g += rdfizer.entities_to_rdf([paper], entity_type="paper")
g += rdfizer.entities_to_rdf(authors, entity_type="author")
g += rdfizer.entities_to_rdf(sections, entity_type="section")
g += rdfizer.entities_to_rdf(references, entity_type="reference")

g.serialize("PMC3258128_rml.ttl", format="turtle")
print(f"Generated {len(g)} RDF triples")
```

## Conversion script

A source checkout includes `examples/scripts/xml_to_rdf_rml.py`, which parses an article and converts its entities with `RMLRDFizer`:

```bash
python examples/scripts/xml_to_rdf_rml.py PMC3258128.xml --output PMC3258128_rml.ttl --json entities.json -v
```

| Option | Description |
|---|---|
| `INPUT` | PMC XML file |
| `--output/-o PATH` | Turtle output file (required) |
| `--json PATH` | Also save the entities as JSON |
| `--mappings PATH` | RML mappings file (default: the packaged `rml_mappings.ttl`) |
| `--config PATH` | RDFizer configuration (default: the packaged `rdfizer_config.ini`) |
| `-v/--verbose` | Print progress |

Known limitation: the script does not set `id` on the entities, so its output contains only the paper's triples (6 for PMC3258128).

## Changing the mapping

The intended workflow is to edit `src/pyeuropepmc/conf/rdf_map.yml` and regenerate the RML file from the repository root with `python examples/scripts/sync_rdf_mappings.py`. The `--yaml` option (default `src/pyeuropepmc/conf/rdf_map.yml`) sets the input and `--rml` (default `src/pyeuropepmc/conf/rml_mappings.ttl`) the output; `--check` is not implemented and exits with status 1.

Known limitation: the script stops with `TypeError: string indices must be integers` on the current `rdf_map.yml`, because the annotation classes map fields to plain predicate strings instead of `{predicate, datatype}` entries. `make sync-rdf` also calls `scripts/sync_rdf_mappings.py`, a path that no longer exists. Until this is fixed, copy `rml_mappings.ttl`, edit the copy, and pass it to `RMLRDFizer` as `mapping_path`.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `ImportError: rdfizer package not found. Install it with: pip install rdfizer` | Install `rdfizer`. |
| `FileNotFoundError: Config file not found: ...` or `Mapping file not found: ...` | The default paths exist only in a source checkout. Pass `config_path` and `mapping_path`. |
| The graph is empty | The entities have no `id` (needed for every type except `paper` and `scholarlywork`), `entity_type` is not in the table above, the JSON keys do not match the `rml:reference` names in the mapping, or a custom configuration changed one of the three lines `RMLRDFizer` replaces. Check `error.log` in the working directory. |
| A property is missing | The field is inherited from a parent class, which the generated triples maps do not include (see [rml_mappings.ttl](#rml_mappingsttl)). |

## Resources

- [RML specification](https://rml.io/specs/rml/)
- [SDM-RDFizer](https://github.com/SDM-TIB/SDM-RDFizer)
- [R2RML](https://www.w3.org/TR/r2rml/)
