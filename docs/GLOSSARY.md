# Glossary

## Core Concepts

**Europe PMC**
A free life sciences literature database providing access to over 40 million articles, including full-text XML and open-access PDFs.

**Full-Text XML**
Structured XML representations of articles in JATS (Journal Article Tag Suite) format, available for a large subset of Europe PMC content.

**PMID**
PubMed Identifier. A unique numerical identifier assigned to each article in PubMed/PMC databases.

**PMCID**
PubMed Central Identifier. An identifier for articles deposited in the PubMed Central full-text archive.

**DOI**
Digital Object Identifier. A persistent identifier used to uniquely identify academic publications.

**Open Access (OA)**
Articles that are freely available to read and download without subscription barriers. Europe PMC supports several open-access licenses.

**JATS**
Journal Article Tag Suite. An XML format for representing scholarly article content, used by Europe PMC for full-text articles.

## PyEuropePMC Components

**SearchClient**
The primary client for querying Europe PMC's search API, supporting keyword searches, field-specific queries, and systematic review filters.

**FullTextClient**
A client for retrieving full-text content (XML, PDF, HTML) from Europe PMC, with automatic fallback between download endpoints.

**ArticleClient**
A client for retrieving detailed article metadata, citations, and references by PMC ID.

**QueryBuilder**
A fluent, type-safe API for constructing complex Europe PMC search queries with logical operators, field validation, and cross-platform translation.

**FullTextXMLParser**
A parser for extracting structured data from JATS XML articles, including metadata, sections, tables, figures, and references.

**EuropePMCParser**
A parser for normalizing and processing raw API response data from Europe PMC search results.

**FTPDownloader**
A client for bulk-downloading full-text articles from Europe PMC's FTP archive, with concurrent download support and progress tracking.

## Processing & Analytics

**Analytics**
A module providing statistical analysis functions for publication data, including citation statistics, year distributions, journal rankings, and quality metrics.

**Visualization**
A module providing plotting functions for analytics results, including publication trends, citation distributions, and dashboard generation.

**DataFrame Conversion**
The process of converting raw API response data into pandas DataFrames for efficient analysis and manipulation.

**Citation Statistics**
Metrics derived from article citation counts, including mean, median, percentiles, and impact scores.

**Quality Metrics**
Measures of data completeness and reliability, such as DOI coverage, abstract availability, and full-text access rates.

## Enrichment

**Paper Enrichment**
The process of augmenting basic article metadata with additional information from external sources like CrossRef, Semantic Scholar, and OpenAlex.

**Unpaywall**
A service that discovers open-access versions of articles, providing license and URL information for legal free access.

**Semantic Scholar**
An AI-powered research tool providing citation contexts, influence metrics, and semantic search capabilities.

## Knowledge Graph

**RDF (Resource Description Framework)**
A standard for representing information as triples (subject-predicate-object), used for building knowledge graphs.

**RML (RDF Mapping Language)**
A declarative mapping language for generating RDF from structured data sources.

**SHACL (Shapes Constraint Language)**
A validation language for checking RDF data against defined shapes and constraints.

**Knowledge Graph**
A structured representation of information using entities and relationships, enabling semantic queries and inference.

## Caching

**Cache**
A storage layer that stores frequently accessed data to improve performance and reduce redundant API calls.

**TTL (Time-to-Live)**
The duration for which cached data remains valid before being refreshed.

**Namespace**
A cache partitioning mechanism that isolates cached data by client, collection, or other logical groupings.

**Content-Addressed Storage**
A storage approach where data is addressed by its content hash, enabling deduplication and integrity verification.

## Systematic Review

**PRISMA**
Preferred Reporting Items for Systematic Reviews and Meta-Analyses. A set of guidelines for reporting systematic reviews.

**Search Log**
A record of all search operations performed during a systematic review, including queries, timestamps, and result counts.

**Deduplication**
The process of identifying and removing duplicate articles from search results across multiple databases.
