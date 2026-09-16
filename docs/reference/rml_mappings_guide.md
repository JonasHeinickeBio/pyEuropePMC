# RML mappings

`RMLRDFizer` converts entities to RDF with RML (RDF Mapping Language) mappings executed by SDM-RDFizer. It is an alternative to the YAML-driven `RDFMapper` described in [Data models and RDF mapping](models.md). This page covers installation, the configuration files, the Python API, the conversion script and troubleshooting.

## RDFMapper or RMLRDFizer

| | `RDFMapper` | `RMLRDFizer` |
|---|---|---|
| Mapping | `conf/rdf_map.yml` | `conf/rml_mappings.ttl`, generated from `rdf_map.yml`, plus `conf/rdfizer_config.ini` |
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

Both files are in the repository's `conf/` directory and are not included in the installed package. Use a source checkout, or download [`rml_mappings.ttl`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/conf/rml_mappings.ttl) and [`rdfizer_config.ini`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/conf/rdfizer_config.ini), then pass their paths.

### rml_mappings.ttl

`examples/scripts/sync_rdf_mappings.py` generates this file from `conf/rdf_map.yml` (see [Changing the mapping](#changing-the-mapping)). It has one triples map per entity class, and each map reads a JSON file:

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
| `figure` | `figures.json` | `FigureEntityMap` |
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

rdfizer = RMLRDFizer(
    config_path="conf/rdfizer_config.ini",
    mapping_path="conf/rml_mappings.ttl",
)

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
| `RMLRDFizer(config_path=None, mapping_path=None)` | `None` uses `conf/rdfizer_config.ini` and `conf/rml_mappings.ttl` of a source checkout. Raises `ImportError` without `rdfizer`, and `FileNotFoundError` (`Config file not found: <path>` or `Mapping file not found: <path>`) when a file is missing. |
| `entities_to_rdf(entities, entity_type, output_format="turtle")` | Returns an rdflib `Graph` for a list of entities of one type (see the table above). The subject templates use `{id}`, so an entity without `id` gets one: its DOI, PMCID, `pmid:<PMID>`, ORCID or ROR ID when it has one, otherwise `<entity_type>-<16 hex digits>`, a digest of its content. The digest is the same in every run, and an entity whose content repeats an earlier one in the same call gets a `-2`, `-3`… suffix, so the output does not change between runs. `output_format` has no effect. |
| `convert_json_to_rdf(json_data, entity_type, output_format="turtle")` | Returns a `Graph` for a dict, or a list of dicts, shaped like `entity.to_dict()` |

SDM-RDFizer prints progress messages and writes `error.log` to the current working directory.

### Converting JSON

```python
from pyeuropepmc.mappers import RMLRDFizer

rdfizer = RMLRDFizer(config_path="conf/rdfizer_config.ini", mapping_path="conf/rml_mappings.ttl")

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
for entity in [paper, *authors, *sections, *figures, *references]:
    entity.normalize()

rdfizer = RMLRDFizer(config_path="conf/rdfizer_config.ini", mapping_path="conf/rml_mappings.ttl")

g = Graph()
g += rdfizer.entities_to_rdf([paper], entity_type="paper")
g += rdfizer.entities_to_rdf(authors, entity_type="author")
g += rdfizer.entities_to_rdf(sections, entity_type="section")
g += rdfizer.entities_to_rdf(figures, entity_type="figure")
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
| `--mappings PATH` | RML mappings file (default: the checkout's `conf/rml_mappings.ttl`) |
| `--config PATH` | RDFizer configuration (default: the checkout's `conf/rdfizer_config.ini`) |
| `-v/--verbose` | Print progress |

For PMC3258128 the output has 342 triples, from the paper, its journal, 6 grants, 12 authors, 23 sections, 5 figures and 47 references.

## Changing the mapping

Edit `conf/rdf_map.yml` and regenerate the RML file from the repository root with `make sync-rdf` or `python examples/scripts/sync_rdf_mappings.py`. The `--yaml` option (default `conf/rdf_map.yml`) sets the input and `--rml` (default `conf/rml_mappings.ttl`) the output; `--check` is not implemented and exits with status 1. A field in the YAML may map to `{predicate, datatype}` or to a bare predicate string. The test suite checks that the committed `conf/rml_mappings.ttl` matches what the script generates.

`RMLRDFizer` points every relative `rml:source "<name>.json"` of the mapping at its temporary directory and creates an empty file for each source it has no entities for, so triples maps added to the YAML need no change to `RMLRDFizer`.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `ImportError: rdfizer package not found. Install it with: pip install rdfizer` | Install `rdfizer`. |
| `FileNotFoundError: Config file not found: ...` or `Mapping file not found: ...` | The default paths exist only in a source checkout. Pass `config_path` and `mapping_path`. |
| The graph is empty | `entity_type` is not in the table above, the JSON keys do not match the `rml:reference` names in the mapping, or a custom configuration changed one of the three lines `RMLRDFizer` replaces. Check `error.log` in the working directory. |
| A property is missing | The field is inherited from a parent class, which the generated triples maps do not include (see [rml_mappings.ttl](#rml_mappingsttl)). |

## Resources

- [RML specification](https://rml.io/specs/rml/)
- [SDM-RDFizer](https://github.com/SDM-TIB/SDM-RDFizer)
- [R2RML](https://www.w3.org/TR/r2rml/)
