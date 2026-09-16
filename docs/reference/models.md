# Data models and RDF mapping

The data models wrap the output of `FullTextXMLParser` in typed entity classes that you can normalise, validate, export as dictionaries and convert to RDF. This page covers the entity classes, the builder that creates them from a parsed article, `RDFMapper` and its mapping file, the conversion scripts, SPARQL queries and SHACL validation.

## Requirements and configuration files

The entity classes, the builder and `RDFMapper` are part of the base package, and rdflib is a core dependency. `RDFMapper` also imports PyYAML, which pyeuropepmc does not declare as a dependency. If `from pyeuropepmc.mappers import RDFMapper` fails with `ModuleNotFoundError: No module named 'yaml'`, run `pip install pyyaml`.

The mapping files ship with the package, in `src/pyeuropepmc/conf/`; the SHACL shapes are in the repository only:

| File | Used by |
|---|---|
| [`rdf_map.yml`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rdf_map.yml) | `RDFMapper` and `PaperProcessingPipeline` |
| [`rml_mappings.ttl`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rml_mappings.ttl), [`rdfizer_config.ini`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rdfizer_config.ini) | `RMLRDFizer`, see [RML mappings](rml_mappings_guide.md) |
| [`pyeuropepmc-vocab.ttl`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/pyeuropepmc-vocab.ttl) | Definitions of the `pyeuropepmc:` vocabulary |
| [`shacl/pub.shacl.ttl`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/shacl/pub.shacl.ttl) | SHACL shapes |

`RDFMapper()` and `PaperProcessingPipeline` use the packaged `rdf_map.yml`; `pyeuropepmc.conf.config_file("rdf_map.yml")` returns its path, for example to copy it as the starting point of your own mapping, which you then pass as `RDFMapper(config_path=...)`.

## Quick start

Fetch an article, build its entities and write them as Turtle:

```python
from rdflib import Graph

from pyeuropepmc import FullTextClient
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mappers import RDFMapper

with FullTextClient() as client:
    xml_content = client.get_fulltext_content("PMC3258128", format_type="xml")

parser = FullTextXMLParser(xml_content)
paper, authors, sections, tables, figures, references = build_paper_entities(parser)
print(paper.title)
print(f"{len(authors)} authors, {len(sections)} sections, {len(references)} references")

paper.normalize()
paper.validate()

mapper = RDFMapper()
g = Graph()
paper.to_rdf(
    g,
    mapper=mapper,
    related_entities={
        "authors": authors,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "references": references,
    },
)
print(len(g), "triples")
mapper.serialize_graph(g, format="turtle", destination="PMC3258128.ttl")
```

For JSON, use `to_dict()`:

```python
import json

with open("PMC3258128.json", "w", encoding="utf-8") as fh:
    json.dump(paper.to_dict(), fh, indent=2, default=str)
```

## Entity classes

The entity classes are dataclasses in `pyeuropepmc.models`. Every field has a default, so you can pass any subset as keyword arguments.

```text
BaseEntity
├── ScholarlyWorkEntity
│   ├── PaperEntity              bibo:AcademicArticle
│   └── ReferenceEntity          bibo:Document
├── AuthorEntity                 foaf:Person
├── InstitutionEntity            org:Organization
├── JournalEntity                bibo:Journal
├── GrantEntity                  frapo:Grant
├── SectionEntity                bibo:DocumentPart, nif:Context
├── TableEntity                  bibo:Table
├── TableRowEntity               bibo:Row
├── FigureEntity                 bibo:Image
└── AnnotationEntity             oa:Annotation, pyeuropepmc:Annotation
    ├── EntityAnnotation         oa:Annotation, oa:SpecificResource, pyeuropepmc:EntityAnnotation
    └── RelationshipAnnotation   oa:Annotation, rdf:Statement, pyeuropepmc:RelationshipAnnotation
```

The names after each class are its default `types`, which become the entity's `rdf:type` triples.

`pyeuropepmc.models` also exports `MeSHHeadingEntity` and `MeSHQualifierEntity`, plain dataclasses described in [MeSH models and PICO](../features/mesh-pico.md). It also exports the pydantic models `LiteratureResult` (also available as `NormalizedWork`), `LiteratureSearchResponse`, `Author`, `ClinicalTrial` and `ICiteMetrics`, which [multi-source search](../features/multi-source-search.md) uses.

### Common fields and methods

Every entity has these fields from `BaseEntity`:

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str \| None` | `None` | Local identifier |
| `label` | `str \| None` | `None` | Human-readable label |
| `source_uri` | `str \| None` | `None` | URI of the source record, for example `urn:pmc:1234567` |
| `confidence` | `float \| None` | `None` | Extraction confidence |
| `types` | `list[str]` | class-specific | RDF types as prefixed names |
| `data_sources` | `list[str]` | `[]` | Sources merged into the entity |
| `last_updated` | `str \| None` | `None` | Time of the last merge |

| Method | Returns | Description |
|---|---|---|
| `to_dict()` | `dict` | The fields as a dictionary |
| `to_rdf(g, uri=None, mapper=None, related_entities=None, extraction_info=None, parent_uri=None)` | `rdflib.URIRef` | Adds the entity's triples to graph `g` and returns its subject URI. Raises `ValueError` without `mapper`. |
| `normalize()` | `None` | Cleans values in place, for example trimming whitespace and lower-casing DOIs |
| `validate()` | `None` | Raises `ValueError` when required fields are missing |
| `merge_from_source(source_data, source_name)` | `None` | Copies values from a dict and records the source |
| `mint_uri(path)` | `rdflib.URIRef` | Returns `http://example.org/data/<path>/<id>`, assigning a UUID `id` first if it is `None`. `to_rdf()` does not use this URI. |

```python
from pyeuropepmc.models import BaseEntity

entity = BaseEntity(
    id="unique-id",
    label="Human-readable label",
    source_uri="urn:pmc:1234567",
    confidence=0.95,
    types=["bibo:Document"],
)
print(entity.mint_uri("entity"))  # http://example.org/data/entity/unique-id
print(entity.to_dict()["label"])
```

### PaperEntity

`PaperEntity` has 60 fields; `dataclasses.fields(PaperEntity)` lists them all. The most used:

| Field | Type | Description |
|---|---|---|
| `title`, `abstract` | `str \| None` | Title and abstract |
| `doi`, `pmid`, `pmcid` | `str \| None` | Identifiers |
| `journal` | `JournalEntity \| None` | Journal |
| `volume` | `int \| str \| None` | Volume |
| `issue`, `pages`, `pub_date` | `str \| None` | Issue, pages, publication date |
| `publication_year` | `int \| None` | Publication year |
| `keywords`, `mesh_terms` | `list` | Keywords and MeSH terms, default `[]` |
| `citation_count`, `cited_by_count`, `influential_citation_count` | `int \| None` | Citation counts |
| `is_oa`, `oa_status`, `oa_url` | `bool \| None`, `str \| None`, `str \| None` | Open-access status |
| `license` | `dict \| None` | Licence information |
| `grants` | `list[GrantEntity] \| None` | Funding |

`normalize()` lower-cases the DOI and removes a `https://doi.org/` prefix. `validate()` requires at least one of `pmcid`, `doi` or `title`.

```python
from pyeuropepmc.models import JournalEntity, PaperEntity

paper = PaperEntity(
    pmcid="PMC1234567",
    doi="https://doi.org/10.1234/Example.2024.001",
    title="Example Scientific Article",
    journal=JournalEntity(title="Nature"),
    volume="580",
    issue="7805",
    pages="123-127",
    pub_date="2024-01-15",
    keywords=["bioinformatics", "RDF"],
)
paper.normalize()
print(paper.doi)  # 10.1234/example.2024.001
paper.validate()
```

### AuthorEntity

| Field | Type | Description |
|---|---|---|
| `full_name` | `str` | Full name, default `""` |
| `first_name`, `last_name`, `initials` | `str \| None` | Name parts |
| `orcid` | `str \| None` | ORCID iD |
| `affiliation_text` | `str \| None` | Affiliations as text |
| `institutions` | `list[InstitutionEntity] \| None` | Structured affiliations |
| `name`, `email`, `position` | `str \| None` | Alternative name, email, author position |
| `openalex_id`, `semantic_scholar_id` | `str \| None` | External author IDs |

`validate()` requires `full_name` or `name`.

```python
from pyeuropepmc.models import AuthorEntity

author = AuthorEntity(
    full_name="Jane Doe",
    first_name="Jane",
    last_name="Doe",
    initials="J.D.",
    orcid="0000-0001-2345-6789",
    affiliation_text="University of Example",
)
author.normalize()
author.validate()
```

### Sections, tables and figures

| Class | Fields |
|---|---|
| `SectionEntity` | `title`, `content` (`str \| None`); `begin_index`, `end_index` (`int \| None`, character offsets). `validate()` requires `content`. |
| `TableEntity` | `table_label`, `caption` (`str \| None`); `headers` (`list[str]`); `rows` (`list[TableRowEntity]`) |
| `TableRowEntity` | `cells` (`list[str]`). Column headers belong to `TableEntity.headers`. |
| `FigureEntity` | `figure_label`, `caption`, `graphic_uri` (`str \| None`). `graphic_uri` may be an absolute URI or a relative reference such as the file name in `<graphic xlink:href="gkr715f1"/>`; `normalize()` and `validate()` reject only malformed absolute URIs. |

```python
from pyeuropepmc.models import FigureEntity, SectionEntity, TableEntity, TableRowEntity

section = SectionEntity(title="Introduction", content="This is the introduction text...", begin_index=0, end_index=33)
section.validate()

row = TableRowEntity(cells=["Value 1", "Value 2"])
table = TableEntity(table_label="Table 1", caption="Sample data table", headers=["Column 1", "Column 2"], rows=[row])

figure = FigureEntity(figure_label="Figure 1", caption="Study design", graphic_uri="https://example.org/figure1.png")
```

### ReferenceEntity

`ReferenceEntity` has the `ScholarlyWorkEntity` fields `title`, `doi`, `pmid`, `pmcid`, `volume`, `pages`, `publication_year` (`int`), `publication_date`, `journal`, `authors` (a string or a list of dicts), `abstract` and `citation_count`, plus `raw_citation`.

```python
from pyeuropepmc.models import ReferenceEntity

ref = ReferenceEntity(
    title="Referenced Article",
    journal="Nature",
    publication_year=2023,
    volume="600",
    pages="123-127",
    doi="10.1038/nature12345",
    authors="Smith J, Doe J",
)
ref.normalize()
ref.validate()
```

### Institutions, journals and grants

| Class | Main fields |
|---|---|
| `InstitutionEntity` | `display_name`, `ror_id`, `openalex_id`, `country`, `country_code`, `city`, `latitude`, `longitude`, `institution_type`, `website`, `established` |
| `JournalEntity` | `title`, `medline_abbreviation`, `iso_abbreviation`, `nlmid`, `issn`, `essn`, `publisher`, `country`, `language` |
| `GrantEntity` | `fundref_doi`, `funding_source`, `award_id`, `recipients` (`list[AuthorEntity] \| None`) |

## Building entities from a parsed article

`build_paper_entities(parser, search_data=None)` from `pyeuropepmc.builders` returns a tuple of six values:

| Position | Value | Built from |
|---|---|---|
| 0 | `PaperEntity` | `parser.extract_metadata()`: identifiers, title, journal (as `JournalEntity`), volume, issue, pages, publication date, keywords, grants |
| 1 | `list[AuthorEntity]` | `parser.extract_authors_detailed()` and `parser.extract_affiliations()`; affiliations become `InstitutionEntity` objects |
| 2 | `list[SectionEntity]` | `parser.get_full_text_sections()`: title and text of each section |
| 3 | `list[TableEntity]` | `parser.extract_tables()`, one `TableRowEntity` per row |
| 4 | `list[FigureEntity]` | `parser.extract_figures()`: label, caption and the `<graphic xlink:href>` file name as `graphic_uri` |
| 5 | `list[ReferenceEntity]` | `parser.extract_references()` |

`search_data` is an optional Europe PMC search result record, one dict from `response["resultList"]["result"]`. Its PMID, citation count, open-access flags, publication year and similar fields are merged into the paper with `merge_from_source(..., "europe_pmc_search")`.

Some sections have no text and fail `SectionEntity.validate()`; check `section.content` before validating sections.

## Converting to RDF

### RDFMapper

`RDFMapper(config_path=None, enable_named_graphs=True)` loads the YAML mapping. A missing file raises `FileNotFoundError: RDF mapping config not found: <path>`.

| Method | Returns | Description |
|---|---|---|
| `serialize_graph(g, format="turtle", destination=None)` | `str` | Serialises a graph in an rdflib format such as `turtle`, `nt`, `xml` or `json-ld`. With `destination`, writes the file and returns an empty string. |
| `convert_and_save_papers_to_rdf(papers_dict, output_dir="rdf_output", prefix="", extraction_info=None, include_content=None)` | `dict[str, Graph]` | Converts `{identifier: (paper, authors, sections, tables, figures, references)}` and writes `<output_dir>/<prefix>paper_<identifier>.ttl` |
| `save_rdf(entities_data, output_dir="rdf_output", kg_type=None, extraction_info=None)` | `dict[str, Graph]` | Converts `{identifier: {"entity": paper, "related_entities": {...}}}` for the chosen knowledge-graph type; `None` uses the `default_type` in `rdf_map.yml` (`complete`) |
| `save_complete_rdf(...)`, `save_metadata_rdf(...)`, `save_content_rdf(...)` | `dict[str, Graph]` | Fixed knowledge-graph type, with file prefixes `""`, `"metadata_"` and `"content_"` |

| `kg_type` | Entities |
|---|---|
| `complete` | The paper and all related entities |
| `metadata` | Paper, authors and institutions |
| `content` | Sections, references, tables and figures |

```python
from pyeuropepmc.builders import build_paper_entities
from pyeuropepmc.features.fulltext.fulltext_parser import FullTextXMLParser
from pyeuropepmc.mappers import RDFMapper

with open("PMC3258128.xml", encoding="utf-8") as fh:
    parser = FullTextXMLParser(fh.read())
paper, authors, sections, tables, figures, references = build_paper_entities(parser)

mapper = RDFMapper()
entities_data = {
    "PMC3258128": {
        "entity": paper,
        "related_entities": {
            "authors": authors,
            "sections": sections,
            "tables": tables,
            "figures": figures,
            "references": references,
        },
    }
}
graphs = mapper.save_rdf(entities_data, output_dir="kg_metadata", kg_type="metadata")
print(len(graphs["PMC3258128"]), "triples")  # kg_metadata/metadata_paper_PMC3258128.ttl
```

### Subject URIs

`to_rdf()` gets the subject URI from the mapper. For each class the first available identifier wins:

| Entity | URI |
|---|---|
| `PaperEntity` | `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`, then `https://doi.org/<doi>`, then `https://www.ncbi.nlm.nih.gov/pmc/articles/<pmcid>/` |
| `ReferenceEntity` | `https://pubmed.ncbi.nlm.nih.gov/<pmid>/`, then the PMC URL, then `https://doi.org/<doi>`, then a `https://w3id.org/pyeuropepmc/reference/...` URI built from the first author, the year and a hash of the title |
| `AuthorEntity` | `https://w3id.org/pyeuropepmc/author/<normalised name>`, then `https://orcid.org/<orcid>`, then the OpenAlex ID |
| `InstitutionEntity` | The ROR ID, then the OpenAlex ID, then `https://w3id.org/pyeuropepmc/institution/<name>` |
| `JournalEntity` | `https://w3id.org/pyeuropepmc/journal/<abbreviation or title>` |
| `SectionEntity` | `https://w3id.org/pyeuropepmc/section/<title>`, with the paper's identifier inserted when converted as part of a paper |
| Other entities | A URI under `https://w3id.org/pyeuropepmc/`, for example `.../table/table-1`, or one ending in a UUID |

The base `https://w3id.org/pyeuropepmc/` is `_base_uri` in `rdf_map.yml`. Converted entities also get `prov:generatedAtTime` and `prov:wasGeneratedBy` triples, and papers and authors get `owl:sameAs` links to their DOI, PMC, Europe PMC and ORCID pages.

### Predicates

For each class, `rdf_map.yml` defines `fields` (one triple per value), `multi_value_fields` (one triple per list item) and `relationships` (links to related entities). A class also uses the fields of its parent classes. The main predicates:

**PaperEntity** (including `ScholarlyWorkEntity` fields)

| Field | Predicate |
|---|---|
| `title` | `dcterms:title` |
| `abstract` | `dcterms:abstract` |
| `doi` | `bibo:doi` |
| `pmcid`, `pmid` | `pyeuropepmc:pmcid`, `pyeuropepmc:pmid` |
| `volume`, `issue`, `pages` | `bibo:volume`, `bibo:issue`, `bibo:pages` |
| `pub_date`, `publication_year` | `dcterms:issued` |
| `publication_date` | `dcterms:date` |
| `citation_count`, `cited_by_count` | `pyeuropepmc:citationCount` |
| `keywords`, `fields_of_study` | `dcterms:subject` |
| Relationship `authors` | `dcterms:creator` (inverse `foaf:made`) |
| Relationship `journal` | `bibo:journal` |
| Relationships `sections`, `tables`, `figures` | `dcterms:hasPart` |
| Relationship `references` | `cito:cites` |
| Relationship `grants` | `foaf:fundedBy` |

**AuthorEntity**

| Field | Predicate |
|---|---|
| `full_name` | `foaf:name` |
| `first_name`, `last_name` | `foaf:givenName`, `foaf:familyName` |
| `initials` | `foaf:initials` |
| `orcid` | `datacite:orcid`, plus `owl:sameAs` to `https://orcid.org/<orcid>` |
| `email` | `foaf:mbox` |
| Relationship `institutions` | `pyeuropepmc:affiliatedWith` |

`affiliation_text` is not mapped; affiliations reach the graph through `institutions`.

**Other classes**

| Class | Field | Predicate |
|---|---|---|
| `SectionEntity` | `title`, `content`, `begin_index`, `end_index` | `dcterms:title`, `nif:isString`, `nif:beginIndex`, `nif:endIndex` |
| `TableEntity` | `caption`, `table_label`, relationship `rows` | `dcterms:description`, `rdfs:label`, `dcterms:hasPart` |
| `TableRowEntity` | `cells` | `rdfs:member`, one triple per cell |
| `FigureEntity` | `caption`, `figure_label`, `graphic_uri` | `dcterms:description`, `rdfs:label`, `foaf:depiction` |
| `ReferenceEntity` | `title`, `doi`, `volume`, `pages`, `publication_year` | `dcterms:title`, `bibo:doi`, `bibo:volume`, `bibo:pages`, `dcterms:issued` |
| `ReferenceEntity` | `authors`, `raw_citation` | `bibo:authorList`, `dcterms:description` |

`TableEntity.headers` is not mapped. The graph types each entity from its `types` field; the `"rdf:type"` entries of `rdf_map.yml` hold the same types and are used for the generated RML file.

**Namespaces**

| Prefix | Namespace |
|---|---|
| `bibo` | `http://purl.org/ontology/bibo/` |
| `dcterms` | `http://purl.org/dc/terms/` |
| `foaf` | `http://xmlns.com/foaf/0.1/` |
| `prov` | `http://www.w3.org/ns/prov#` |
| `nif` | `http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#` |
| `cito` | `http://purl.org/spar/cito/` |
| `datacite` | `http://purl.org/spar/datacite/` |
| `frapo` | `http://purl.org/cerif/frapo/` |
| `org` | `http://www.w3.org/ns/org#` |
| `oa` | `http://www.w3.org/ns/oa#` |
| `pyeuropepmc` | `https://w3id.org/pyeuropepmc/vocab#` |

`rdf_map.yml` also declares `owl`, `rdfs`, `rdf`, `skos`, `geo`, `mesh`, `meshv`, `obo`, `ror`, `xsd` and `pyeuropepmcdata`.

### Customising the mapping

Copy `rdf_map.yml`, change the predicates, and pass the copy as `config_path`. A class entry looks like this:

```yaml
PaperEntity:
  "rdf:type": ["bibo:AcademicArticle"]
  fields:
    issue: {predicate: "bibo:issue", datatype: "xsd:string"}
    abstract: {predicate: "dcterms:abstract", datatype: "xsd:string"}
  multi_value_fields:
    keywords: dcterms:subject
  relationships:
    authors:
      predicate: "dcterms:creator"
      inverse: foaf:made
```

`RDFMapper` reads the YAML file directly. The RML file `rml_mappings.ttl` is generated from it by `examples/scripts/sync_rdf_mappings.py` (options `--yaml` and `--rml`), also run by `make sync-rdf`. A field may map to `{predicate, datatype}` or, as the annotation classes do, to a bare predicate string. `"rdf:type"` only affects the generated RML file: `RDFMapper` takes the types from the entity's `types` field, so change both when you change a type.

To add a field in Python, subclass an entity and decorate the subclass with `@dataclass`. Without the decorator, the new attribute is not a dataclass field and `to_dict()` leaves it out.

```python
from dataclasses import dataclass

from pyeuropepmc.models import PaperEntity


@dataclass
class ExtendedPaperEntity(PaperEntity):
    custom_field: str = ""


extended = ExtendedPaperEntity(title="Example", custom_field="value")
print(extended.to_dict()["custom_field"])  # value
```

### Other conversion functions

`pyeuropepmc.mappers` also has functions that convert data directly to an rdflib `Dataset`. Each also accepts the optional parameters `config_path`, `namespaces`, `cache_backend` and `extraction_info`.

| Function | Converts |
|---|---|
| `convert_xml_to_rdf(xml_data, ..., include_content=True)` | Parsed XML data (`dict`) |
| `convert_search_to_rdf(search_results, ...)` | Europe PMC search results |
| `convert_enrichment_to_rdf(enrichment_data, ...)` | Enrichment results |
| `convert_annotations_to_rdf(annotations_data, ...)` | Europe PMC Annotations API responses |
| `convert_pipeline_to_rdf(search_results=None, xml_data=None, enrichment_data=None, annotations_data=None, ..., include_content=True)` | Any combination of the above |
| `convert_incremental_to_rdf(base_rdf, enrichment_data, ...)` | Adds enrichment data to an existing `Graph` and returns the `Graph` |

## Command-line scripts

A source checkout includes two conversion scripts in `examples/scripts/`. They use the mapping files that ship with the package unless you pass other paths.

```bash
python examples/scripts/xml_to_rdf.py PMC3258128.xml --ttl PMC3258128.ttl --json PMC3258128.json -v
python examples/scripts/xml_to_rdf_rml.py PMC3258128.xml --output PMC3258128_rml.ttl --json entities.json -v
```

| Script | Options |
|---|---|
| `xml_to_rdf.py INPUT` | `--ttl PATH` (Turtle output), `--json PATH` (entities as JSON), `--config PATH` (mapping YAML), `-v/--verbose` |
| `xml_to_rdf_rml.py INPUT` | `--output/-o PATH` (required, Turtle output), `--json PATH` (entities as JSON), `--mappings PATH` (RML file), `--config PATH` (RDFizer configuration), `-v/--verbose` |

## Querying with SPARQL

```python
from rdflib import Graph

g = Graph()
g.parse("PMC3258128.ttl", format="turtle")

query = """
PREFIX bibo: <http://purl.org/ontology/bibo/>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT ?paper ?title ?doi
WHERE {
    ?paper a bibo:AcademicArticle ;
           dcterms:title ?title .
    OPTIONAL { ?paper bibo:doi ?doi }
}
"""
for row in g.query(query):
    print(row.paper, row.title, row.doi)
```

## SHACL validation

`shacl/pub.shacl.ttl` defines shapes for `bibo:AcademicArticle`, `foaf:Person`, `bibo:DocumentPart`, `bibo:Table` and `bibo:Document`, mostly limits on how often a property may occur. Validating against them needs `pyshacl`, which is not installed with pyeuropepmc:

```bash
pip install pyshacl
```

```python
from pyshacl import validate
from rdflib import Graph

data_graph = Graph().parse("PMC3258128.ttl", format="turtle")
shapes_graph = Graph().parse("pub.shacl.ttl", format="turtle")

conforms, results_graph, results_text = validate(data_graph, shacl_graph=shapes_graph, inference="rdfs")
print(f"Conforms: {conforms}")
if not conforms:
    print(results_text)
```

## References

- [BIBO ontology](http://purl.org/ontology/bibo/)
- [FOAF vocabulary](http://xmlns.com/foaf/spec/)
- [DCMI Metadata Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
- [PROV-O](https://www.w3.org/TR/prov-o/)
- [NIF core ontology](http://persistence.uni-leipzig.org/nlp2rdf/)
- [SPAR ontologies (CiTO, DataCite, FRAPO)](http://www.sparontologies.net/)
- [SHACL](https://www.w3.org/TR/shacl/)
- [RML mappings](rml_mappings_guide.md)
