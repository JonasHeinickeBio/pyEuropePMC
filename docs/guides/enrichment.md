# Metadata enrichment

`PaperEnricher` looks up a paper in Europe PMC and several scholarly APIs and merges their answers into one metadata record. This guide covers installation, configuration, the result format, batch enrichment, the individual source clients and the rules for merging conflicting values.

## Installation

The enrichment clients are part of the base package. The Semantic Scholar source also needs the `semanticscholar` library:

```bash
pip install "pyeuropepmc[enrichment]"
```

The `enrichment` extra installs `semanticscholar` and `cryptography`; `pyeuropepmc[semanticscholar]` installs only `semanticscholar`. Without the library, `PaperEnricher` logs an error, skips Semantic Scholar and runs the other sources.

## Sources

| Source | `EnrichmentConfig` flag | Default | Looked up by | Credentials |
|---|---|---|---|---|
| Europe PMC | `enable_europepmc` | `True` | DOI, PMID or PMCID | None |
| CrossRef | `enable_crossref` | `True` | DOI | Optional `crossref_email` (polite pool) |
| OpenAlex | `enable_openalex` | `True` | DOI | Optional `openalex_email` (polite pool) |
| Semantic Scholar | `enable_semantic_scholar` | `True` | DOI | Optional `semantic_scholar_api_key` |
| NIH iCite | `enable_icite` | `True` | PMID | None |
| ROR | `enable_ror` | `True` | ROR IDs of the authors' institutions | Optional `ror_email`, `ror_client_id` |
| Unpaywall | `enable_unpaywall` | `False` | DOI | `unpaywall_email` (required) |
| DataCite | `enable_datacite` | `False` | DOI | Optional `datacite_email` |

`OrcidClient` is a separate client for researcher profiles that `PaperEnricher` does not call; see [ORCID and NIH iCite clients](../features/orcid.md). Citation graphs are covered in [Citation graph walking](../features/citation-walking.md).

## Enriching a paper

```python
from pyeuropepmc import EnrichmentConfig, PaperEnricher

config = EnrichmentConfig(crossref_email="you@example.org")

with PaperEnricher(config) as enricher:
    result = enricher.enrich_paper("10.1371/journal.pone.0308090")

print(result["sources"])

merged = result["merged"]
print(merged.get("title"))
print(merged.get("citation_count"), merged.get("citation_counts"))
print(merged.get("is_oa"), merged.get("oa_url"))
```

Pass the identifier positionally or as `identifier=`. `doi=`, `pmid=` and `pmcid=` are accepted as synonyms, so `enrich_paper(doi="10.1371/journal.pone.0308090")` does the same; they are not forwarded to the sources.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `identifier` | `str \| None` | `None` | DOI, DOI URL (`https://doi.org/...`), PMID or PMCID; also accepted as `doi=`, `pmid=` or `pmcid=`. Without any of them, `ValueError` is raised. |
| `save_responses` | `bool` | `False` | Write each source's response and the whole result to JSON files |
| `save_dir` | `str \| Path \| None` | `None` | Directory for those files; `None` means `./enrichment_responses`. The files are `raw_<source>_<key>.json` and `merged_<key>.json`, where `<key>` is the resolved DOI, or the identifier you passed when no DOI was found, with every character other than letters, digits and `-` replaced by `_` |
| `**kwargs` | | | Passed to every source client's `enrich()` |

Before querying the sources, the enricher runs one Europe PMC search to find the DOI, PMID and PMCID it was not given. This lookup also runs when `enable_europepmc=False`. iCite receives the PMID; the other sources receive the DOI, or the PMID or original identifier when no DOI was found. The sources are queried in parallel. A source that raises an exception or returns nothing is logged and left out of `sources`.

### Result

`enrich_paper()` returns a `dict`:

| Key | Type | Content |
|---|---|---|
| `identifier` | `str` | The identifier you passed |
| `doi`, `pmid` | `str \| None` | The resolved identifiers |
| `sources` | `list[str]` | Sources that returned data, in the order they finished; `"ror"` is added when institutions were enriched |
| `europepmc`, `crossref`, `openalex`, `semantic_scholar`, `icite`, `unpaywall`, `datacite`, `ror` | `dict \| None` | One entry per enabled source (and always `ror`): that client's normalised response, or `None` |
| `merged` | `dict` | The merged record (see [Merge rules](#merge-rules)); `{}` when no source returned data |

`enricher.generate_enrichment_report(result)` returns a short text summary of a result. It reads `merged["journal"]` both as the string Europe PMC supplies and as a dict with `title` or `name`.

## Configuration

`EnrichmentConfig` parameters:

| Parameter | Type | Default | Environment variable |
|---|---|---|---|
| `enable_europepmc` | `bool` | `True` | |
| `enable_crossref` | `bool` | `True` | |
| `enable_datacite` | `bool` | `False` | |
| `enable_unpaywall` | `bool` | `False` | |
| `enable_semantic_scholar` | `bool` | `True` | |
| `enable_openalex` | `bool` | `True` | |
| `enable_icite` | `bool` | `True` | |
| `enable_ror` | `bool` | `True` | |
| `unpaywall_email` | `str \| None` | `None` | `UNPAYWALL_EMAIL` |
| `crossref_email` | `str \| None` | `None` | `CROSSREF_EMAIL` |
| `datacite_email` | `str \| None` | `None` | `DATACITE_EMAIL` |
| `semantic_scholar_api_key` | `str \| None` | `None` | `SEMANTIC_SCHOLAR_API_KEY` |
| `openalex_email` | `str \| None` | `None` | `OPENALEX_EMAIL` |
| `ror_email` | `str \| None` | `None` | `ROR_EMAIL` |
| `ror_client_id` | `str \| None` | `None` | `ROR_CLIENT_ID` |
| `cache_config` | `CacheConfig \| None` | `None` (no caching) | |
| `rate_limit_delay` | `float` | `1.0` | |

- An argument you pass takes precedence; the environment variable is used only when the argument is not given.
- `enable_unpaywall=True` without an email, as argument or environment variable, raises `ValueError: unpaywall_email is required when enable_unpaywall=True`.
- `rate_limit_delay` (seconds) is passed to every client; iCite gets at most 0.5. The Europe PMC and Semantic Scholar clients wait at least this long between requests. Known limitation: the other clients do not wait between requests and use the value only to size the wait after HTTP 429.
- `cache_config` is shared by all clients; see [Caching](../advanced/caching.md). Known limitation: a disk cache (`CacheConfig(enable_l2=True)`) is wiped when another cache opens the same directory, so it does not persist between runs.

To use only the external APIs, with Unpaywall and caching:

```python
import os

from pyeuropepmc import CacheConfig, EnrichmentConfig, PaperEnricher

config = EnrichmentConfig(
    enable_europepmc=False,
    enable_icite=False,
    enable_ror=False,
    enable_unpaywall=True,
    unpaywall_email=os.environ.get("UNPAYWALL_EMAIL", "you@example.org"),
    semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY"),
    cache_config=CacheConfig(enabled=True, ttl=86400),
    rate_limit_delay=1.0,
)

with PaperEnricher(config) as enricher:
    print(sorted(enricher.clients))  # ['crossref', 'openalex', 'semantic_scholar', 'unpaywall']
    result = enricher.enrich_paper("10.1371/journal.pone.0308090")
```

## Enriching many papers

```python
from pyeuropepmc import EnrichmentConfig, PaperEnricher

identifiers = ["10.1371/journal.pone.0308090", "PMC11309437"]

with PaperEnricher(EnrichmentConfig()) as enricher:
    results = enricher.enrich_papers_batch(identifiers, save_responses=False)

for identifier, result in results.items():
    if "error" in result:
        print(identifier, "failed:", result["error"])
    else:
        print(identifier, result["sources"])
```

`enrich_papers_batch(identifiers, save_responses=True, save_dir=None, **kwargs)` enriches the papers one after another. It returns a `dict` that maps each identifier to its `enrich_paper()` result, or to `{"error": ..., "identifier": ...}` when enrichment failed. `save_responses` defaults to `True`, which writes JSON files to `./enrichment_responses`.

## Source clients

Every client can be used on its own. `enrich()` returns a `dict`, or `None` when nothing was found or the identifier is not valid for that source (for example, a PMID passed to CrossRef). The clients are context managers; `close()` releases the HTTP session and the cache.

```python
from pyeuropepmc.features.enrich import CrossRefClient, ICiteClient, OpenAlexClient

with CrossRefClient(email="you@example.org") as crossref:
    work = crossref.enrich("10.1371/journal.pone.0308090")
    if work:
        print(work["title"], work["citation_count"])

with OpenAlexClient(email="you@example.org") as openalex:
    work = openalex.enrich("10.1371/journal.pone.0308090")
    if work:
        print(work["cited_by_count"], work["topics"])

with ICiteClient() as icite:
    metrics = icite.enrich("39116051")  # PMID
    if metrics:
        print(metrics["rcr"], metrics["nih_percentile"])
```

Pass the identifier positionally or as `identifier=`. The DOI-keyed clients (CrossRef, OpenAlex, Semantic Scholar, Unpaywall, DataCite) also accept it as `doi=`, `ICiteClient` as `pmid=` and `OrcidClient` as `orcid=`. Used on their own, CrossRef, OpenAlex, Unpaywall, iCite, DataCite and ORCID raise `APIClientError` (importable from `pyeuropepmc`) on network errors, timeouts and HTTP errors other than 404. `RorClient` logs these errors and returns `None`.

All clients below are importable from `pyeuropepmc.features.enrich`. Every result also has a `source` key.

| Client | Constructor | `enrich()` input | Main result keys |
|---|---|---|---|
| `CrossRefClient` | `(rate_limit_delay=1.0, timeout=15, cache_config=None, email=None)` | DOI | `title`, `authors`, `abstract`, `journal`, `publication_date`, `citation_count`, `references_count`, `license`, `funders`, plus `type`, `issn`, `volume`, `issue`, `page`, `publisher` when present |
| `OpenAlexClient` | `(rate_limit_delay=1.0, timeout=15, cache_config=None, email=None, enable_ror_enrichment=True)` | DOI, or `openalex_id=` | `openalex_id`, `title`, `publication_year`, `publication_date`, `citation_count`, `cited_by_count`, `is_oa`, `oa_status`, `oa_url`, `authors`, `institutions`, `topics`, `venue`, `biblio`, `referenced_works_count`, `related_works` |
| `UnpaywallClient` | `(email, rate_limit_delay=1.0, timeout=15, cache_config=None)` | DOI | `is_oa`, `oa_status`, `best_oa_location`, `oa_locations`, `oa_locations_embargoed`, `first_oa_date`, `journal_is_oa`, `journal_is_in_doaj`, `publisher`, `year` |
| `ICiteClient` | `(rate_limit_delay=0.5, timeout=15, **kwargs)` | PMID | `pmid`, `rcr`, `percentile`, `nih_percentile`, `citation_count`, `citations_per_year`, `expected_citations`, `field_citation_ratio`, `is_research_article`, `provisional`, `year`. Also `enrich_many(pmids)`, `get_rcr(pmid)`, `get_percentile(pmid)`, `get_citation_count(pmid)`. |
| `SemanticScholarClient` | `(rate_limit_delay=1.2, timeout=15, cache_config=None, api_key=None)` | DOI, or `semantic_scholar_id=` | See [Semantic Scholar](#semantic-scholar) |
| `RorClient` | `(email=None, client_id=None, cache_config=None, rate_limit_delay=1.0)` | ROR ID or ROR URL | Organisation record |
| `DataCiteClient` | `(rate_limit_delay=1.0, timeout=15, cache_config=None, email=None)` | DOI | DataCite record |
| `OrcidClient` | `(rate_limit_delay=1.0, timeout=15, cache_config=None)` | ORCID iD | See [ORCID and NIH iCite clients](../features/orcid.md) |

## Semantic Scholar

`SemanticScholarClient` is the client that `PaperEnricher` and `CitationWalker` use. It is also importable from `pyeuropepmc`, and it returns plain dicts.

```python
from pyeuropepmc import SemanticScholarClient

with SemanticScholarClient(api_key=None) as s2:
    paper = s2.enrich("10.1371/journal.pone.0308090")
    if paper:
        print(paper["title"], paper.get("citation_count"), paper.get("influential_citation_count"))

    hits = s2.search_papers("CRISPR base editing", limit=20, year="2020-2024")
    for hit in hits:
        print(hit["title"])

    similar = s2.get_recommendations_for_paper("649def34f8be52c8b66281af98ae884c09aef38b", limit=10)
```

| Method | Returns | Notes |
|---|---|---|
| `enrich(identifier=None, use_cache=True, semantic_scholar_id=None)` | `dict \| None` | Keys include `title`, `abstract`, `year`, `venue`, `journal`, `citation_count`, `influential_citation_count`, `reference_count`, `authors`, `fields_of_study`, `external_ids`, `open_access_pdf_url`, `publication_types`, `tldr`. Keys without a value are left out. |
| `enrich_batch(identifiers, use_cache=True)` | `dict[str, dict]` | Keyed by Semantic Scholar paper ID (or DOI); requests at most 500 papers at a time |
| `enrich_author(author_id, use_cache=True)` | `dict \| None` | `author_id`, `name`, `affiliations`, `homepage`, `paper_count`, `citation_count`, `h_index`, `url` |
| `search_papers(query, limit=100, use_cache=True, bulk=False, **filters)` | `list[dict]` | Filters: `year`, `venue`, `fieldsOfStudy`, `minCitationCount`, `publicationDateOrYear`. `bulk=True` uses the bulk search endpoint, which does not rank by relevance. Errors return `[]`. |
| `get_recommendations_for_paper(paper_id, limit=None, fields=None, use_cache=True)` | `list[dict]` | `limit` is capped at 500. An invalid paper ID raises `ValueError`; API errors return `[]`. |
| `get_recommendations_for_papers(positive_paper_ids, negative_paper_ids=None, limit=None, fields=None, use_cache=True)` | `list[dict]` | An empty `positive_paper_ids`, an invalid ID, or an ID in both lists raises `ValueError`; API errors return `[]`. IDs may contain letters, digits, `:`, `.`, `/`, `_` and `-`. |

Known limitation: `search_papers()` returns at most 100 papers; a larger `limit` is reduced to 100.

Without an API key, the Semantic Scholar API allows fewer requests; set `SEMANTIC_SCHOLAR_API_KEY` or pass `api_key`.

### Bulk search

`search_papers(..., bulk=True)` sends the query to Semantic Scholar's bulk search endpoint, which returns papers without relevance ranking. The default, `bulk=False`, uses relevance search. Either way a call returns at most 100 papers.

```python
from pyeuropepmc import SemanticScholarClient

with SemanticScholarClient() as s2:
    papers = s2.search_papers("CRISPR base editing", limit=100, bulk=True, year="2020-2024")

for paper in papers:
    print(paper["title"], paper.get("year"), paper.get("citation_count"))
```

Each result is a dict in the `enrich()` format, built from the fields the search requests: title, abstract, venue, year, citation counts, authors, fields of study and external IDs. Keys whose value is missing are left out, so read optional fields with `get()`. Errors, including rate limiting that persists after the retries, are logged and return an empty list.

### ProfessionalSemanticScholarClient

`ProfessionalSemanticScholarClient` is the thin wrapper around the `semanticscholar` library that `SemanticScholarClient` uses internally. It is not exported from `pyeuropepmc.features.enrich`, returns dicts rather than typed objects, and is not a context manager.

```python
from pyeuropepmc.features.enrich.sources.semanticscholar_pro import ProfessionalSemanticScholarClient

client = ProfessionalSemanticScholarClient(api_key=None, rate_limit_delay=1.1)
paper = client.get_paper("DOI:10.1038/nature12373")
if paper:
    print(paper["title"], paper.get("citation_count"), len(paper["authors"]))

results = client.search_paper("cancer", bulk=True, limit=50)
```

Its methods are `get_paper`, `get_papers`, `search_paper`, `get_paper_authors`, `get_author`, `search_author`, `get_recommendations` and `get_recommendations_from_lists`. `search_paper()` raises `ValueError` when `limit` is outside 1 to 100.

## Merge rules

`merged` is built from the source results as follows. "A, then B" means the first source that has a value wins.

| `merged` key | Rule |
|---|---|
| `title` | Europe PMC, then CrossRef, OpenAlex, Semantic Scholar |
| `abstract` | Europe PMC, then CrossRef, Semantic Scholar |
| `journal` | Europe PMC, then CrossRef, then OpenAlex (`venue`) |
| `publication_year` or `publication_date` | Europe PMC `publication_year`, then CrossRef `publication_date`, then OpenAlex `publication_date` or `publication_year` |
| `citation_count` | Highest count from Europe PMC, iCite, CrossRef, Semantic Scholar and OpenAlex |
| `citation_counts` | `[{"source": ..., "count": ...}, ...]` for every source with a count |
| `icite` | `rcr`, `percentile`, `nih_percentile`, `field_citation_ratio` from iCite |
| `is_oa`, `oa_status`, `oa_url` | Unpaywall, then OpenAlex, then Europe PMC (open-access flag and first full-text URL) |
| `influential_citation_count`, `fields_of_study` | Semantic Scholar |
| `topics` | OpenAlex |
| `license`, `funding` | CrossRef |
| `mesh_terms`, `grants`, `full_text_urls`, `publication_type` | Europe PMC |
| `authors` | Combined from CrossRef, OpenAlex, Semantic Scholar and DataCite; institutions receive ROR data when ROR is enabled |
| `biblio` | Volume, issue, pages, publisher, ISSN and type from CrossRef, gaps filled from OpenAlex and Semantic Scholar |
| `references` | Reference count (highest of CrossRef, Semantic Scholar, OpenAlex), plus OpenAlex `cited_by_count` and `related_works` |
| `external_ids`, `external_id_conflicts` | Identifiers reported by Semantic Scholar, OpenAlex and CrossRef; values that disagree are listed in `external_id_conflicts` |

Keys without a value from any source are left out.

## Errors and retries

- A client that cannot be created, for example because `semanticscholar` is not installed, is logged and skipped.
- The sources run independently. An exception in one source is logged, and the other sources still contribute.
- Clients built on `BaseEnrichmentClient` (CrossRef, OpenAlex, Unpaywall, iCite, ROR, DataCite, ORCID) retry connection errors and HTTP 500, 502, 503 and 504 up to 3 times with exponential backoff. HTTP 429 is retried within 3 attempts in total, after the `Retry-After` value or an exponential backoff, capped at 60 seconds. A 404 returns `None`. A 403 on a request sent with an API key is retried once without the key.
- `ProfessionalSemanticScholarClient` methods retry through their `max_retries` argument (default 3; 2 for `search_paper`).

## Authentication

Set credentials as environment variables to keep them out of code:

```bash
export SEMANTIC_SCHOLAR_API_KEY="your-api-key"
export UNPAYWALL_EMAIL="you@example.org"
export CROSSREF_EMAIL="you@example.org"
export OPENALEX_EMAIL="you@example.org"
```

`EnrichmentConfig` reads `UNPAYWALL_EMAIL`, `CROSSREF_EMAIL`, `DATACITE_EMAIL`, `SEMANTIC_SCHOLAR_API_KEY`, `OPENALEX_EMAIL`, `ROR_EMAIL` and `ROR_CLIENT_ID`. `SemanticScholarClient` also reads `SEMANTIC_SCHOLAR_API_KEY` when you create it directly without `api_key`. Rate limits and polite-pool rules are set by each provider; see their documentation:

- [CrossRef REST API](https://api.crossref.org/)
- [Unpaywall API](https://unpaywall.org/products/api)
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [OpenAlex API](https://docs.openalex.org/)
- [NIH iCite API](https://icite.od.nih.gov/api)
- [ROR API](https://ror.readme.io/)

## Examples and tests

- [examples/09-enrichment](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/09-enrichment) contains enrichment scripts and a notebook.
- In a source checkout, `pytest tests/features/enrich` runs the enrichment unit tests offline.
