# LinkML Schema Class Hierarchy

## Full Inheritance Tree

```
linkml:Thing (base)
    └── linkml:MetadataType
        └── BaseEntity (pyeuropepmc)
            ├── ScholarlyWorkEntity (pyeuropepmc)
            │   ├── PaperEntity (pyeuropepmc)
            │   └── ReferenceEntity (pyeuropepmc)
            ├── AuthorEntity (pyeuropepmc)
            ├── Organization (pyeuropepmc)
            │   └── Department (pyeuropepmc)
            ├── JournalEntity (pyeuropepmc)
            ├── GrantEntity (pyeuropepmc)
            ├── SectionEntity (pyeuropepmc)
            ├── TableEntity (pyeuropepmc)
            ├── TableRowEntity (pyeuropepmc)
            ├── FigureEntity (pyeuropepmc)
            └── CitationContextEntity (pyeuropepmc)
                └── AffiliationEntity (pyeuropepmc)
```

## Slot Usage Matrix

### BaseEntity Slots (inherited by all entities)
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| id | string | false | Local identifier |
| label | string | false | Human-readable label |
| source_uri | uriorcurie | false | Source URI |
| confidence | float | false | Confidence score (0.0-1.0) |
| quality_score | float | false | Quality score (0.0-1.0) |
| types | uriorcurie | true | RDF types |
| data_sources | string | true | Data sources |
| last_updated | datetime | false | Last update timestamp |
| generatedAtTime | datetime | false | Generation timestamp |

### ScholarlyWorkEntity Slots (inherited by PaperEntity, ReferenceEntity)
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| title | string | false | Work title |
| doi | uriorcurie | false | Digital Object Identifier |
| pmid | string | false | PubMed ID |
| pmcid | string | false | PubMed Central ID |
| semantic_scholar_id | string | false | Semantic Scholar ID |
| authors |AuthorEntity\|string | true | Authors |
| journal | JournalEntity\|string | false | Journal |
| publication_year | integer | false | Publication year |
| publication_date | date | false | Full publication date |
| abstract | string | false | Abstract |
| issn | string | false | ISSN |
| publication_type | PublicationType | false | Publication type |
| keywords | string | true | Keywords |

### PaperEntity Additional Slots (108 lines)
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| issue | string | false | Issue number |
| pub_date | date | false | Publication date |
| citation_count | integer | false | Citation count |
| influential_citation_count | integer | false | Influential citations |
| is_oa | boolean | false | Open access flag |
| oa_status | OpenAccessStatus | false | Open access status |
| oa_url | uriorcurie | false | Open access URL |
| reference_count | integer | false | Reference count |
| cited_by_count | integer | false | Papers citing this |
| publisher | string | false | Publisher |
| first_page | string | false | First page |
| last_page | string | false | Last page |
| fields_of_study | string | true | Fields of study |
| related_works | string | true | Related work IDs |
| pub_types | string | true | Publication types |
| mesh_terms | string | true | MeSH terms |
| topics | string | true | Research topics |
| has_pdf | boolean | false | Has PDF |
| has_supplementary | boolean | false | Has supplementary |
| in_epmc | boolean | false | In Europe PMC |
| in_pmc | boolean | false | In PubMed Central |
| sections | SectionEntity | true | Sections |
| references | ReferenceEntity | true | References |
| tables | TableEntity | true | Tables |
| figures | FigureEntity | true | Figures |
| grants | GrantEntity | true | Grants |
| quality_score | float | false | Quality score |
| s2_paper_id | string | false | Semantic Scholar ID |
| openalex_id | uriorcurie | false | OpenAlex ID |
| tldr | string | false | TLDR summary |
| open_access_pdf_url | uriorcurie | false | OA PDF URL |

### ReferenceEntity Additional Slots (75 lines)
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| citing_paper | PaperEntity | false | Paper citing this reference |
| author_list | string | false | Author list |
| raw_citation | string | false | Raw citation text |

### AuthorEntity Additional Slots (59 lines)
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| full_name | string | false | Full name |
| first_name | string | false | First name |
| last_name | string | false | Last name |
| initials | string | false | Initials |
| affiliation_text | string | false | Affiliation text |
| orcid | string | false | ORCID identifier |
| papers | PaperEntity | true | Papers by author |
| author_institutions | Organization | true | Author institutions |
| affiliations | AffiliationEntity | true | Affiliations |
| institutions | Organization | true | Institutional affiliations |
| h_index | integer | false | H-index |
| citation_count | integer | false | Citation count |
| orcid_works_count | integer | false | ORCID works count |
| paper_count | integer | false | Total papers |
| roles | AuthorRole | true | Author roles |
| email | string | false | Email address |

### Organization/Department Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| display_name | string | false | Display name |
| ror_id | uriorcurie | false | ROR identifier |
| country | string | false | Country |
| country_code | string | false | Country code |
| city | string | false | City |
| latitude | float | false | Latitude (-90 to 90) |
| longitude | float | false | Longitude (-180 to 180) |
| institution_type | InstitutionType | false | Institution type |
| grid_id | string | false | GRID identifier |
| isni | string | false | ISNI identifier |
| wikidata_id | uriorcurie | false | Wikidata ID |
| fundref_id | string | false | FundRef ID |
| website | uriorcurie | false | Website |
| established | integer | false | Year established |
| domains | string | true | Institution domains |
| relationships | string | true | Related institutions |
| institution_members | AuthorEntity | true | Institution members |
| names | string | true | Alternative names |
| locations | string | true | Locations |
| links | uriorcurie | true | Links |

### SectionEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| content | string | false | Section content |
| begin_index | integer | false | Text start offset |
| end_index | integer | false | Text end offset |
| section_type | SectionType | false | Section type |
| context_text | string | false | Context text |
| citations | CitationContextEntity | true | Citations in section |
| subsections | SectionEntity | true | Subsections |
| parent_section | SectionEntity | false | Parent section |
| paper | PaperEntity | false | Parent paper |

### TableEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| label | string | false | Table label |
| caption | string | false | Table caption |
| headers | string | true | Column headers |
| rows | TableRowEntity | true | Table rows |
| paper | PaperEntity | false | Parent paper |

### TableRowEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| cells | string | true | Cell values |
| table | TableEntity | false | Parent table |

### FigureEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| caption | string | false | Figure caption |
| label | string | false | Figure label |
| graphic_uri | uriorcurie | false | Figure image URI |
| paper | PaperEntity | false | Parent paper |

### GrantEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| funding_source | string | false | Funding source |
| award_id | string | false | Award ID |
| grant_id | string | false | Grant ID |
| fundref_doi | uriorcurie | false | FundRef DOI |
| recipients | AuthorEntity | true | Grant recipients |
| funded_papers | PaperEntity | true | Funded papers |

### AffiliationEntity Additional Slots
| Slot | Range | Multivalued | Description |
|------|-------|-------------|-------------|
| affiliated_author | AuthorEntity | false | Author |
| affiliated_institution | Organization | false | Institution |
| affiliation_order | integer | false | Order in list |

## Entity Relationships Diagram

```
PaperEntity
├── authors: AuthorEntity[]  (1..*)
├── journal: JournalEntity   (0..1)
├── sections: SectionEntity[]  (0..*)
├── references: ReferenceEntity[]  (0..*)
├── tables: TableEntity[]  (0..*)
├── figures: FigureEntity[]  (0..*)
├── grants: GrantEntity[]  (0..*)
├── paper_institutions: Organization[]  (0..*)
└── affiliations: AffiliationEntity[]  (0..*)

ReferenceEntity
├── citing_paper: PaperEntity  (0..1)
├── authors: string\|AuthorEntity[]  (0..*)
├── journal: string\|JournalEntity  (0..1)
└── references: ReferenceEntity[]  (0..*)

AuthorEntity
├── papers: PaperEntity[]  (0..*)
├── institutions: Organization[]  (0..*)
├── affiliations: AffiliationEntity[]  (0..*)
└── author_institutions: Organization[]  (0..*)

Organization
├── institution_members: AuthorEntity[]  (0..*)
├── parent_organization: Organization  (0..1)
└── relationships: string[]  (0..*)

SectionEntity
├── paper: PaperEntity  (0..1)
├── subsections: SectionEntity[]  (0..*)
├── parent_section: SectionEntity  (0..1)
└── citations: CitationContextEntity[]  (0..*)

TableEntity
├── paper: PaperEntity  (0..1)
└── rows: TableRowEntity[]  (0..*)

TableRowEntity
└── table: TableEntity  (0..1)

FigureEntity
└── paper: PaperEntity  (0..1)

GrantEntity
├── funded_papers: PaperEntity[]  (0..*)
└── recipients: AuthorEntity[]  (0..*)

AffiliationEntity
├── affiliated_author: AuthorEntity  (0..1)
└── affiliated_institution: Organization  (0..1)
```
