# LinkML Schema Overview

## Schema Structure

```
pyeuropepmc (Main Schema)
├── imports
│   ├── base.yaml (core metadata)
│   ├── slots.yaml (801 lines - reusable slots)
│   ├── enums.yaml (6 controlled vocabularies)
│   └── entities/*.yaml (12 entity files)
│
├── classes (inherited from entities)
│   ├── BaseEntity (root)
│   │   ├── ScholarlyWorkEntity
│   │   │   ├── PaperEntity (108 lines)
│   │   │   └── ReferenceEntity (75 lines)
│   │   ├── AuthorEntity (59 lines)
│   │   └── Organization
│   │       └── Department
│   ├── JournalEntity
│   ├── GrantEntity
│   ├── SectionEntity
│   ├── TableEntity
│   ├── TableRowEntity
│   ├── FigureEntity
│   └── CitationContextEntity
│       └── AffiliationEntity
```

## Key Components

### 1. Slot Definitions (slots.yaml - 801 lines)

#### Identifiers
- `id` - Local identifier (slug/uuid)
- `doi` - Digital Object Identifier (pattern: `^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$`)
- `pmcid` - PubMed Central ID (pattern: `^PMC\d+$`)
- `pmid` - PubMed ID (pattern: `^\d+$`)
- `semantic_scholar_id` - Semantic Scholar paper ID
- `orcid` - ORCID identifier (pattern: `^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$`)

#### Bibliographic
- `title` - Work or entity title
- `authors` - Authors (string or list of AuthorEntity)
- `journal` - Journal (string or JournalEntity)
- `volume`, `pages`, `publication_year`, `publication_date`

#### Entity Relationships
- `paper_institutions` - Organizations affiliated with a paper
- `authors` - List of AuthorEntity objects
- `affiliations` - Author-institution links
- `references` - References cited by a paper
- `citations` - Citation contexts in a section
- `sections` - Sections of a paper
- `tables`, `figures` - Document components
- `grants` - Funding information

#### Metrics & Quality
- `citation_count` - Total citation count
- `quality_score` - Overall quality score (0.0-1.0)
- `confidence_score` - Confidence for citation classification (0.0-1.0)

#### Specialized for ReferenceEntity
- `authors_string` - Comma-separated list of authors
- `journal_string` - Journal name as string

### 2. Enumerations (enums.yaml - 165 lines)

#### OpenAccessStatus
- `open` - Fully open access
- `closed` - Not open access
- `hybrid` - Hybrid open access
- `green` - Green open access (preprint/postprint)
- `gold` - Gold open access
- `bronze` - Bronze open access
- `unknown` - Unknown status

#### PublicationType
- `journal_article`, `review`, `preprint`, `book_chapter`, `conference_paper`, `dataset`, `thesis`, `other`

#### InstitutionType
- `education`, `healthcare`, `company`, `government`, `nonprofit`, `facility`, `funder`, `other`

#### AuthorPosition
- `first`, `middle`, `last`, `corresponding`

#### AuthorRole (CRediT)
- `conceptualization`, `methodology`, `software`, `validation`, `formal_analysis`
- `investigation`, `resources`, `data_curation`, `writing_original_draft`
- `writing_review_editing`, `visualization`, `supervision`, `project_administration`
- `funding_acquisition`

#### SectionType
- `abstract`, `introduction`, `methods`, `results`, `discussion`, `conclusion`
- `acknowledgments`, `references`, `supplementary`, `appendix`, `other`

#### CitationType
- `cites`, `cites_as_evidence`, `cites_as_background`, `cites_as_related`
- `cites_as_method`, `cites_for_information`, `shares_authors`
- `agrees_with`, `disagrees_with`, `cites_as_metadata`, `cites_as_data`

### 3. Entity Classes

#### PaperEntity (108 lines)
Full academic paper with 80+ slots including:
- Basic metadata (title, authors, journal, publication info)
- Citation metrics (citation_count, reference_count)
- Open access status (oa_status, oa_url)
- Identifiers (doi, pmid, pmcid, semantic_scholar_id, openalex_id)
- Relationships (sections, references, tables, figures, grants)
- Quality score for data completeness

#### ReferenceEntity (75 lines)
Bibliographic reference inheriting from ScholarlyWorkEntity:
- References cited by papers
- String-based journal and authors fields (slot_usage overrides)
- Publication metadata for cited works

#### AuthorEntity (59 lines)
Research authors with:
- Personal info (full_name, first_name, last_name, initials, email)
- Identifiers (orcid, semantic_scholar_id, scopus_author_id)
- Affiliations (institutions, affiliations)
- Metrics (paper_count, h_index, orcid_works_count)
- Roles and positions

#### Organization/Department
Institutions with geographic data:
- Basic info (display_name, ror_id, country, city)
- Geographic (latitude, longitude)
- Type and classification (institution_type, institution_members)
- Relationships (parent_organization, relationships)
- Contact (website, domains, names, locations)

#### SectionEntity
Document sections with:
- Content (content, begin_index, end_index for text alignment)
- Metadata (section_type, label, order)
- Relationships (paper, subsections, parent_section, citations)

#### TableEntity
Tables with:
- Metadata (label, caption, headers)
- Rows (list of TableRowEntity)
- Relationships (paper)

#### TableRowEntity
Table rows with:
- Cell values (cells - multivalued)
- Relationships (table)

#### FigureEntity
Figures with:
- Metadata (label, caption, graphic_uri)
- Relationships (paper)

#### GrantEntity
Funding information with:
- Basic info (funding_source, award_id, grant_id)
- DOI (fundref_doi)
- Recipients (authors)
- Relationships (funded_papers)

#### AffiliationEntity
Author-institution links with:
- Text (affiliation_text)
- Entity references (affiliated_author, affiliated_institution)
- Position (affiliation_order)

## Schema Design Highlights

1. **Modular Design**: Separate files for slots, enums, and entities
2. **Inheritance**: ReferenceEntity inherits from ScholarlyWorkEntity
3. **Multivalued Fields**: Support for lists (authors, keywords, etc.)
4. **Range Constraints**: Type safety (string, integer, float, uriorcurie, datetime)
5. **Patterns**: Regex validation for DOIs, PMIDs, ISSNs, ORCIDs
6. **Minimum/Maximum**: Numeric constraints for years, counts, coordinates
7. **Slot Usage**: Per-class overrides with required, range, description

## Usage

Generate different outputs from the schema:
```bash
gen-json-schema schemas/pyeuropepmc_schema.yaml > schemas/pyeuropepmc.schema.json
gen-shacl schemas/pyeuropepmc_schema.yaml > shacl/pyeuropepmc.shacl.ttl
gen-pydantic schemas/pyeuropepmc_schema.yaml > src/pyeuropepmc/models/generated.py
```
