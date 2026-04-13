# PyEuropePMC LinkML Schema Visualization

## 📊 Schema Statistics

```
Total Files: 13 schema files
Total Lines: ~1,300+ lines
Total Classes: 12 entity classes
Total Slots: 100+ slot definitions
Total Enums: 7 controlled vocabularies
Total Enum Values: 65+ permissible values
```

## 🏗️ File Structure

```
schemas/
├── base.yaml                    (21 lines)   Core schema metadata
├── slots.yaml                   (801 lines)  Reusable slot definitions
├── enums.yaml                   (165 lines)  Controlled vocabularies
├── pyeuropepmc_schema.yaml      (73 lines)   Main schema entry point
└── entities/
    ├── base.yaml                (47 lines)   Base entity classes
    ├── paper.yaml               (108 lines)  PaperEntity
    ├── reference.yaml           (75 lines)   ReferenceEntity
    ├── author.yaml              (59 lines)   AuthorEntity
    ├── organization.yaml        (82 lines)   Organization, Department
    ├── journal.yaml             (85 lines)   JournalEntity
    ├── grant.yaml               (67 lines)   GrantEntity
    ├── section.yaml             (57 lines)   SectionEntity
    ├── table.yaml               (72 lines)   TableEntity, TableRowEntity
    ├── figure.yaml              (53 lines)   FigureEntity
    └── affiliation.yaml         (43 lines)   AffiliationEntity, CitationContextEntity
```

## 🎯 Entity Class Breakdown

```
Entity Classes (12):
├── BaseEntity (abstract root)
├── ScholarlyWorkEntity (abstract)
│   ├── PaperEntity (full academic paper)
│   └── ReferenceEntity (cited reference)
├── AuthorEntity (researcher)
├── Organization (institution)
│   └── Department (sub-organization)
├── JournalEntity (publication)
├── GrantEntity (funding)
├── SectionEntity (document section)
├── TableEntity (data table)
├── TableRowEntity (table row)
├── FigureEntity (figure/image)
├── CitationContextEntity (citation context)
│   └── AffiliationEntity (author-institution link)
```

## 📋 Slot Distribution by Category

```
Total Slots: 100+

Identifiers:         7 slots  (doi, pmid, pmcid, orcid, etc.)
Bibliographic:      22 slots  (title, authors, journal, etc.)
Publication:        18 slots  (issue, pub_date, keywords, etc.)
Open Access:         7 slots  (is_oa, oa_status, oa_url, etc.)
Metrics:            12 slots  (citation_count, quality_score, etc.)
Document Structure: 15 slots  (sections, tables, figures, etc.)
Relationships:      18 slots  (citing_paper, institutions, etc.)
Geographic:          6 slots  (latitude, longitude, country, etc.)
Organization:       14 slots  (display_name, ror_id, domains, etc.)
Author:             17 slots  (full_name, email, position, etc.)
Grant:               8 slots  (funding_source, award_id, etc.)
Citation:           12 slots  (citation_type, cites, etc.)
Metadata:           10 slots  (confidence, types, data_sources, etc.)
```

## 🔢 Enumerations

```
OpenAccessStatus:     7 values  (open, closed, hybrid, green, gold, bronze, unknown)
PublicationType:      8 values  (journal_article, review, preprint, book_chapter, etc.)
InstitutionType:      8 values  (education, healthcare, company, government, etc.)
AuthorPosition:       4 values  (first, middle, last, corresponding)
AuthorRole:          15 values  (CRediT roles: conceptualization, methodology, etc.)
SectionType:         11 values  (abstract, introduction, methods, results, etc.)
CitationType:        12 values  (cites, cites_as_evidence, agrees_with, etc.)
```

## 🔗 Inheritance Hierarchy

```
linkml:Thing
    └── BaseEntity
        ├── ScholarlyWorkEntity
        │   ├── PaperEntity (108 lines, 80+ slots)
        │   └── ReferenceEntity (75 lines, inherits + overrides)
        ├── AuthorEntity (59 lines, 17 slots)
        ├── Organization (82 lines, 14 slots)
        │   └── Department (inherits + overrides)
        ├── JournalEntity
        ├── GrantEntity
        ├── SectionEntity
        ├── TableEntity
        ├── TableRowEntity
        ├── FigureEntity
        └── CitationContextEntity
            └── AffiliationEntity
```

## 📊 Slot Cardinality

```
Required Slots (most entities):
- None (all slots are optional by default)

Optional Slots:
- Most slots have required: false in slot_usage

Multivalued Slots (30+):
- keywords, authors, fields_of_study, related_works
- pub_types, mesh_terms, topics, sections
- tables, figures, references, grants
- affiliations, institutions, papers
- citations, subsections, recipients
- names, locations, domains, relationships
- roles, sources, headers, cells

Singular Slots (70+):
- title, doi, pmid, pmcid, abstract
- volume, pages, publication_year
- publication_type, first_page, last_page
```

## 🎨 Slot Range Distribution

```
string:          60+ slots  (primary data type)
uriorcurie:      20+ slots  (URIs, CURIEs)
integer:         20+ slots  (years, counts, indices)
float:           10+ slots  (scores, coordinates)
boolean:          5 slots   (is_oa, has_pdf, etc.)
date:             5 slots   (publication_date, established)
datetime:         2 slots   (last_updated, generatedAtTime)
enum types:      10+ slots  (PublicationType, OpenAccessStatus, etc.)
entity types:    15+ slots  (PaperEntity, AuthorEntity, etc.)
```

## 🔍 Pattern Validation Slots

```
DOI Pattern:        ^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$
PMCID Pattern:      ^PMC\d+$
PMID Pattern:       ^\d+$
ISSN Pattern:       ^\d{4}-\d{3}[\dX]$
ORCID Pattern:      ^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$
Email Pattern:      ^[\w\.-]+@[\w\.-]+\.\w+$
Funder DOI Pattern: ^10\.\d{4,9}/[-._;()/:A-Z0-9]+$
```

## 📈 Numeric Range Slots

```
Years (1000-9999):
- publication_year
- established
- year

Counts (min: 0):
- citation_count
- reference_count
- reference_count
- paper_count
- h_index
- orcid_works_count
- influential_citation_count

Coordinates (-90 to 90, -180 to 180):
- latitude
- longitude

Scores (0.0-1.0):
- quality_score
- confidence_score
```

## 🔄 Entity Relationships

```
PaperEntity ──author──> AuthorEntity[]
PaperEntity ──journal──> JournalEntity
PaperEntity ──section──> SectionEntity[]
PaperEntity ──reference──> ReferenceEntity[]
PaperEntity ──table──> TableEntity[]
PaperEntity ──figure──> FigureEntity[]
PaperEntity ──grant──> GrantEntity[]
PaperEntity ──institution──> Organization[]

ReferenceEntity ──citing_paper──> PaperEntity
ReferenceEntity ──author──> AuthorEntity[] | string
ReferenceEntity ──journal──> JournalEntity | string

AuthorEntity ──paper──> PaperEntity[]
AuthorEntity ──institution──> Organization[]
AuthorEntity ──affiliation──> AffiliationEntity[]

Organization ──member──> AuthorEntity[]
Organization ──parent──> Organization
Organization ──relationship──> string[]

SectionEntity ──paper──> PaperEntity
SectionEntity ──subsections──> SectionEntity[]
SectionEntity ──parent──> SectionEntity
SectionEntity ──citation──> CitationContextEntity[]

TableEntity ──paper──> PaperEntity
TableEntity ──row──> TableRowEntity[]

TableRowEntity ──table──> TableEntity

FigureEntity ──paper──> PaperEntity

GrantEntity ──paper──> PaperEntity[]
GrantEntity ──recipient──> AuthorEntity[]

AffiliationEntity ──author──> AuthorEntity
AffiliationEntity ──institution──> Organization
```

## 🎯 Key Design Patterns

1. **Modularity**: Separate files for slots, enums, entities
2. **Inheritance**: ReferenceEntity extends ScholarlyWorkEntity
3. **Polymorphism**: `authors` can be string or AuthorEntity[]
4. **Composition**: PaperEntity contains sections, tables, figures
5. **Validation**: Patterns for DOIs, PMIDs, ISSNs, ORCIDs
6. **Constraint**: Numeric ranges for years, coordinates, scores
7. ** Enumeration**: Controlled vocabularies for types and roles
8. **Metadata**: Universal slots for provenance and quality

## 📝 Usage Examples

```bash
# Generate JSON Schema
gen-json-schema schemas/pyeuropepmc_schema.yaml > schemas/pyeuropepmc.schema.json

# Generate SHACL shapes
gen-shacl schemas/pyeuropepmc_schema.yaml > shacl/pyeuropepmc.shacl.ttl

# Generate Python models
gen-pydantic schemas/pyeuropepmc_schema.yaml > src/pyeuropepmc/models/generated.py

# View schema in browser
linkml-visualize schemas/pyeuropepmc_schema.yaml --format html > docs/schema.html
```

## 🌐 Namespace Prefixes

```
pyeuropepmc:      https://w3id.org/pyeuropepmc/vocab#
pyeuropepmcdata:  https://w3id.org/pyeuropepmc/data#
linkml:           https://w3id.org/linkml/
dcterms:          http://purl.org/dc/terms/
foaf:             http://xmlns.com/foaf/0.1/
bibo:             http://purl.org/ontology/bibo/
prov:             http://www.w3.org/ns/prov#
rdfs:             http://www.w3.org/2000/01/rdf-schema#
nif:              http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#
rdf:              http://www.w3.org/1999/02/22-rdf-syntax-ns#
owl:              http://www.w3.org/2002/07/owl#
mesh:             http://id.nlm.nih.gov/mesh/
meshv:            http://id.nlm.nih.gov/mesh/vocab#
obo:              http://purl.obolibrary.org/obo/
org:              http://www.w3.org/ns/org#
cito:             http://purl.org/spar/cito/
datacite:         http://purl.org/spar/datacite/
frapo:            http://purl.org/cerif/frapo/
geo:              http://www.w3.org/2003/01/geo/wgs84_pos#
ror:              https://ror.org/vocab#
skos:             http://www.w3.org/2004/02/skos/core#
xsd:              http://www.w3.org/2001/XMLSchema#
```

---

*Generated from PyEuropePMC LinkML Schema v1.0.0*
