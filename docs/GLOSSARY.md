# Glossary

This page defines the terms used across the pyEuropePMC documentation: Europe PMC concepts, pyEuropePMC's classes, and the formats and values they work with.

## Europe PMC

**Europe PMC**
A free database of life-science literature. It holds abstracts from PubMed and other sources, and the full text of a subset of articles, including the open-access articles in PubMed Central.

**PMID**
PubMed identifier: the number PubMed assigns to a record.

**PMCID**
PubMed Central identifier, such as `PMC3258128`. Only articles in PubMed Central have one, and only they can have full text in Europe PMC.

**DOI**
Digital Object Identifier: a persistent identifier for a publication.

**Source**
The collection a Europe PMC record comes from: `MED` (PubMed/MEDLINE), `PMC`, `PPR` (preprints), `AGR`, `CBA`, `CTX`, `ETH`, `HIR` or `PAT`. Filter by it inside a query, as in `SRC:MED`. `ArticleClient` methods take a source and an ID, as in `get_citations("MED", "8521067")`.

**Open access (OA)**
Free to read and reuse under an open licence. Search results mark such records with `isOpenAccess: "Y"`.

**JATS**
Journal Article Tag Suite: the XML format of Europe PMC's full-text articles.

**cursorMark**
The position marker Europe PMC uses for paging. Pass `"*"` for the first page and the response's `nextCursorMark` for each following page. `SearchClient.search_all()` does this for you.

**resultType**
How much of each record a search returns: `idlist` (identifiers only), `lite` (the default: key metadata) or `core` (adds the abstract, MeSH terms and full-text links).

**hitCount**
The total number of records that match a query, returned with every search response.

## pyEuropePMC classes

**SearchClient**
Searches Europe PMC and pages through results. See [SearchClient](api/search-client.md).

**ArticleClient**
Gets the details, citations, references and links of one article, identified by source and ID.

**FullTextClient**
Downloads full-text XML, PDF and HTML by PMCID, with fallbacks between download routes.

**FTPDownloader**
Downloads open-access PDF packages in bulk from the Europe PMC FTP site; `bulk_download_and_extract()` runs several downloads at once.

**QueryBuilder**
Builds Europe PMC query strings from named fields, checks where operators are placed, and saves, loads and translates queries.

**FullTextXMLParser**
Extracts metadata, sections, tables, figures and references from JATS XML, and converts articles to plain text or Markdown.

**EuropePMCParser**
Turns search responses in JSON, XML or Dublin Core into lists of record dicts.

**JATSNormalizer**
Prepares JATS XML for text mining (`normalize_xml()`, `normalize_text()`, `normalize_sections()`) and labels sections with canonical types such as `intro`, `methods`, `results` and `discussion`. See [JATS normalization](features/parsing/jats-normalization.md).

**UnifiedSearch**
Searches several services at once, translating the query for each, and merges duplicate records. See [Multi-source search](features/multi-source-search.md).

**Source registry**
`pyeuropepmc.features.search.registry`, which lists the sources `UnifiedSearch` can use (`available_sources()`). Other packages can add sources through the `pyeuropepmc.sources` entry-point group.

**LiteratureMerger**
Deduplicates lists of records from several sources and returns the merged records with a `MergeReport`. Its `DedupMode` values are `BALANCED`, `FOCUSED` and `RELAXED`. See [Deduplication](features/dedup.md).

**PaperEnricher**
Adds metadata to a paper from external services: CrossRef, OpenAlex, Semantic Scholar, Unpaywall, iCite, ORCID, DataCite and ROR. See [Enrichment](guides/enrichment.md).

**ArtifactStore**
Content-addressed storage for downloaded files: each file is stored under a hash of its content, so identical files are kept once.

## Full text and parsing

**Full-text XML**
The JATS XML of an article, available for a subset of Europe PMC records.

**defusedxml**
The library pyEuropePMC uses to parse all XML. It accepts a normal `DOCTYPE` but rejects documents that declare entities, which blocks entity-expansion attacks; `FullTextXMLParser` raises `ParsingError` for such documents.

**Structured section**
A section returned by `FullTextXMLParser.get_full_text_sections_structured()`: a dict with `title`, `section_type`, `section_path`, `schema_version` and `content`, where `content` is a list of content blocks.

**section_type**
The part of the article a structured section belongs to: `front` (the article title and abstract), `body` (the main text), `back` (back matter) or `appendix`.

**Content block**
One item in a structured section's `content`: a dict whose `type` is `paragraph`, `heading`, `list`, `table`, `figure`, `formula`, `table_ref`, `figure_ref`, `code`, `boxed_text`, `quote`, `mathml`, `definition_list`, `peer_review` or `unknown_block`. When a paragraph contains a table or a figure, the paragraph is split so that the table or figure becomes a block of its own.

**BioC**
A format for text-mining corpora. `pyeuropepmc normalize bioc` converts a JATS XML file to BioC JSON.

## Analysis and knowledge graphs

**Analytics**
Functions for publication statistics, such as `publication_year_distribution()`, `citation_statistics()` and `quality_metrics()`; they need the `analytics` extra.

**Visualization**
Plotting functions for those statistics, such as `plot_publication_years()` and `create_summary_dashboard()`; they need the `visualization` extra.

**DataFrame conversion**
Turning search results into a pandas DataFrame, with `to_dataframe()` or `SearchClient.export_results(results, format="dataframe")`.

**MeSH**
Medical Subject Headings, the controlled vocabulary used to index PubMed. `pyeuropepmc.features.review` has helpers to suggest and expand MeSH terms. See [MeSH and PICO](features/mesh-pico.md).

**PICO**
Population, Intervention, Comparison, Outcome: a way to structure a clinical question. `pyeuropepmc.features.review` parses PICO elements and turns them into queries.

**RDF**
Resource Description Framework: data as subject–predicate–object triples, the basis of knowledge graphs. rdflib is part of the base install; JSON-LD output needs the `rdf` extra. See [Data models and RDF mapping](reference/models.md).

**RML**
RDF Mapping Language: declarative rules that generate RDF from structured data. RML mapping needs the separate `rdfizer` package.

**SHACL**
Shapes Constraint Language: rules for validating RDF, used by the validation code in `pyeuropepmc.mappers`.

**Knowledge graph**
Entities and the relationships between them, represented as RDF so they can be queried together.

## Caching

**Cache**
Stored responses or files that let pyEuropePMC skip repeated requests. `SearchClient` caches responses only when given a `CacheConfig`, in memory by default; `FullTextClient` keeps a file cache of downloads by default. See [Caching](features/caching/README.md) and [Caching internals](advanced/caching.md).

**TTL (time to live)**
How long a cached entry stays valid. `CacheConfig(ttl=...)` takes seconds; the default is one day.

## Systematic reviews

**PRISMA**
Preferred Reporting Items for Systematic Reviews and Meta-Analyses: guidelines for reporting systematic reviews.

**Search log**
A record of the searches in a review, with each query, its filters, the date and the number of results. Start one with `start_search()` from `pyeuropepmc.utils.search_logging`.

**Deduplication**
Finding and merging records of the same article, especially across databases. See **LiteratureMerger**.

## Installation, tools and errors

**Extra**
An optional group of dependencies installed with the package, as in `pip install "pyeuropepmc[analytics]"`. See [Installation](getting-started/installation.md#extras).

**OptionalDependencyError**
The error raised when a feature needs a package that is not installed. Its message names the package and the install command.

**Error code**
The code, such as `NET001`, that every pyEuropePMC exception carries. See [Error codes](reference/error-codes.md).

**pyeuropepmc (command)**
The command-line tool installed with the package, with the `normalize`, `unified_search`, `claim` and `benchmark` command groups.

**pyeuropepmc-mcp**
A Model Context Protocol (MCP) server that exposes pyEuropePMC's search, full-text and enrichment tools to MCP clients.
