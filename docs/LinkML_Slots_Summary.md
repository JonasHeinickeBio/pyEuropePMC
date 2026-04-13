# LinkML Schema Slots Summary

## Total Slots: 100+ slots across all entities

### Core Identifiers (7 slots)
```
id                      → string              Local identifier
doi                     → uriorcurie          Digital Object Identifier (pattern)
pmcid                   → string              PubMed Central ID (pattern: ^PMC\d+$)
pmid                    → string              PubMed ID (pattern: ^\d+$)
semantic_scholar_id     → string              Semantic Scholar ID
orcid                   → string              ORCID (pattern: ^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$)
openalex_id             → uriorcurie          OpenAlex ID
```

### Bibliographic (22 slots)
```
title                   → string              Work title
authors                 → string/AuthorEntity Authors (string or list)
journal                 → string/JournalEntity Journal
volume                  → string              Publication volume
pages                   → string              Page range
publication_year        → integer             Publication year (1000-9999)
publication_date        → date                Full publication date
abstract                → string              Abstract
issn                    → string              ISSN (pattern: ^\d{4}-\d{3}[\dX]$)
publication_type        → PublicationType     Publication type
first_page              → string              First page
last_page               → string              Last page
publisher               → string              Publisher
author_list             → string              Author list
raw_citation            → string              Raw citation text
journal_string          → string              Journal name (for references)
authors_string          → string              Comma-separated authors
```

### Publication Details (18 slots)
```
issue                   → string              Issue number
pub_date                → date                Publication date
keywords                → string              Keywords (multivalued)
fields_of_study         → string              Fields of study (multivalued)
related_works           → string              Related work IDs (multivalued)
pub_types               → string              Publication types (multivalued)
mesh_terms              → string              MeSH terms (multivalued)
topics                  → string              Research topics (multivalued)
publication_types       → string              Publication types (multivalued)
s2_fields_of_study      → string              Semantic Scholar fields (multivalued)
```

### Open Access (7 slots)
```
is_oa                   → boolean             Open access flag
oa_status               → OpenAccessStatus    Open access status
oa_url                  → uriorcurie          Open access URL
license_url             → uriorcurie          License URL
license_text            → string              License text
open_access_pdf_url     → uriorcurie          OA PDF URL
oa_status               → OpenAccessStatus    Open access status
```

### Metrics (12 slots)
```
citation_count          → integer             Citation count (min: 0)
influential_citation_count → integer          Influential citations (min: 0)
cited_by_count          → integer             Papers citing this (min: 0)
reference_count         → integer             Reference count (min: 0)
influential_citation_count → integer          Influential citations (min: 0)
citation_count          → integer             Citation count (min: 0)
quality_score           → float               Quality score (0.0-1.0)
confidence_score        → float               Confidence score (0.0-1.0)
orcid_works_count       → integer             ORCID works count (min: 0)
paper_count             → integer             Total papers (min: 0)
h_index                 → integer             H-index (min: 0)
```

### Document Structure (15 slots)
```
sections                → SectionEntity       Sections (multivalued)
tables                  → TableEntity         Tables (multivalued)
figures                 → FigureEntity        Figures (multivalued)
references              → ReferenceEntity     References (multivalued)
grants                  → GrantEntity         Grants (multivalued)
caption                 → string              Caption
label                   → string              Label
headers                 → string              Headers (multivalued)
cells                   → string              Cell values (multivalued)
content                 → string              Content
begin_index             → integer             Text start offset (min: 0)
end_index               → integer             Text end offset (min: 0)
section_type            → SectionType         Section type
context_text            → string              Context text
```

### Relationships (18 slots)
```
paper_institutions      → Organization        Paper institutions (multivalued)
author_institutions     → Organization        Author institutions (multivalued)
affiliations            → AffiliationEntity   Affiliations (multivalued)
institutions            → Organization        Institutions (multivalued)
affiliated_author       → AuthorEntity        Affiliated author
affiliated_institution  → Organization        Affiliated institution
citations               → CitationContextEntity Citations (multivalued)
citing_paper            → PaperEntity         Citing paper
cited_paper             → PaperEntity         Cited paper
citing_section          → SectionEntity       Citing section
 subsections            → SectionEntity       Subsections (multivalued)
parent_section          → SectionEntity       Parent section
paper                   → PaperEntity         Parent paper
table                   → TableEntity         Parent table
figure_paper            → FigureEntity        Parent paper
funded_papers           → PaperEntity         Funded papers (multivalued)
recipients              → AuthorEntity        Recipients (multivalued)
parent_organization     → Organization        Parent organization
```

### Geographic (6 slots)
```
latitude                → float               Latitude (-90 to 90)
longitude               → float               Longitude (-180 to 180)
country                 → string              Country
country_code            → string              Country code
city                    → string              City
```

### Organization (14 slots)
```
display_name            → string              Display name
ror_id                  → uriorcurie          ROR ID
institution_type        → InstitutionType     Institution type
grid_id                 → string              GRID ID
isni                    → string              ISNI identifier
wikidata_id             → uriorcurie          Wikidata ID
fundref_id              → string              FundRef ID
website                 → uriorcurie          Website
established             → integer             Year established (1000-9999)
domains                 → string              Domains (multivalued)
relationships           → string              Relationships (multivalued)
institution_members     → AuthorEntity        Members (multivalued)
names                   → string              Names (multivalued)
locations               → string              Locations (multivalued)
links                   → uriorcurie          Links (multivalued)
```

### Author (17 slots)
```
full_name               → string              Full name
first_name              → string              First name
last_name               → string              Last name
initials                → string              Initials
affiliation_text        → string              Affiliation text
email                   → string              Email (pattern)
position                → AuthorPosition      Position
roles                   → AuthorRole          Roles (multivalued)
sources                 → string              Sources (multivalued)
name                    → string              Display name
semantic_scholar_author_id → string           Semantic Scholar author ID
scopus_author_id        → string              Scopus author ID
researcher_id           → string              ResearcherID
```

### Grant (8 slots)
```
funding_source          → string              Funding source
award_id                → string              Award ID
grant_id                → string              Grant ID
fundref_doi             → uriorcurie          FundRef DOI (pattern)
agency                  → string              Funding agency
recipient               → string              Recipient (deprecated)
recipients              → AuthorEntity        Recipients (multivalued)
order_in                → integer             Order in list (min: 0)
```

### Citation (12 slots)
```
citation_count          → integer             Citation count
cites                   → CitationContextEntity Citation type
citation_type           → CitationType        Citation relationship
citing_section          → SectionEntity       Citing section
cited_paper             → PaperEntity         Cited paper
cites_as_evidence       → CitationType        Cites as evidence
cites_as_background     → CitationType        Cites for background
cites_as_related        → CitationType        Cites related work
cites_as_method         → CitationType        Cites methodological work
cites_for_information   → CitationType        Cites for information
shares_authors          → CitationType        Shares authors
agrees_with             → CitationType        Agrees with cited work
```

### Metadata (10 slots)
```
confidence              → float               Confidence score (0.0-1.0)
quality_score           → float               Quality score (0.0-1.0)
types                   → uriorcurie          RDF types (multivalued)
data_sources            → string              Data sources (multivalued)
last_updated            → datetime            Last update timestamp
generatedAtTime         → datetime            Generation timestamp
source_uri              → uriorcurie          Source URI
label                   → string              Label
id                      → string              Identifier
```

## Slot Usage Patterns

### Multivalued Slots (100+ slots)
- `keywords` - string list
- `fields_of_study` - string list
- `related_works` - string list
- `pub_types` - string list
- `mesh_terms` - string list
- `topics` - string list
- `publication_types` - string list
- `s2_fields_of_study` - string list
- `sections` - SectionEntity list
- `tables` - TableEntity list
- `figures` - FigureEntity list
- `references` - ReferenceEntity list
- `grants` - GrantEntity list
- `affiliations` - AffiliationEntity list
- `institutions` - Organization list
- `authors` - AuthorEntity list
- `papers` - PaperEntity list
- `affiliated_authors` - AuthorEntity list
- `citations` - CitationContextEntity list
- `subsections` - SectionEntity list
- `recipients` - AuthorEntity list
- `fundef_papers` - PaperEntity list
- `names` - string list
- `locations` - string list
- `links` - uriorcurie list
- `domains` - string list
- `relationships` - string list
- `institutions_members` - AuthorEntity list
- `roles` - AuthorRole list
- `sources` - string list
- `headers` - string list
- `cells` - string list

### Pattern Validation Slots
- `doi` - pattern: `^10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+$`
- `pmcid` - pattern: `^PMC\d+$`
- `pmid` - pattern: `^\d+$`
- `issn` - pattern: `^\d{4}-\d{3}[\dX]$`
- `issn` - pattern: `^\d{4}-\d{3}[\dX]$`
- `orcid` - pattern: `^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$`
- `email` - pattern: `^[\w\.-]+@[\w\.-]+\.\w+$`
- `fundref_doi` - pattern: `^10\.\d{4,9}/[-._;()/:A-Z0-9]+$`

### Numeric Range Slots
- `publication_year` - min: 1000, max: 9999
- `established` - min: 1000, max: 9999
- `latitude` - min: -90.0, max: 90.0
- `longitude` - min: -180.0, max: 180.0
- `citation_count` - min: 0
- `quality_score` - min: 0.0, max: 1.0
- `confidence_score` - min: 0.0, max: 1.0
