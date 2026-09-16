# Multi-source search

`UnifiedSearch` sends one query to several literature sources in parallel, rewrites it for each source, and merges the answers into one deduplicated list of `LiteratureResult` records. Each source client can also be used on its own. This page covers both, the source registry, and the normalization helpers the clients share.

## Quick start

```python
from pyeuropepmc.features.search import UnifiedSearch

with UnifiedSearch() as searcher:  # Europe PMC, PubMed and arXiv
    results, report = searcher.search("chronic fatigue syndrome", limit=25)

print(f"{len(results)} records, {report.duplicates_removed} duplicates removed")
print(report.metadata["source_counts"])  # records returned by each source
print(report.metadata["source_errors"])  # {source: message} for sources that failed
for paper in results[:5]:
    print(paper.source, paper.publication_year, paper.title)
```

`UnifiedSearch` is also exported as `pyeuropepmc.UnifiedSearch`.

## UnifiedSearch

`UnifiedSearch(sources=None, dedup_mode=DedupMode.BALANCED, timeout=30, rate_limit_delay=1.2, api_key=None, max_workers=None, translate=True, credentials=None, primary=..., primary_limit_factor=2.0)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sources` | `list[str]` or `None` | `None` | Source keys from the [registry](#sources); `None` means `["europepmc", "pubmed", "arxiv"]`. An unknown key raises `ValueError` |
| `dedup_mode` | `DedupMode` | `DedupMode.BALANCED` | Duplicate matching mode, from `pyeuropepmc.features.enrich.merger`; see [Deduplication](dedup.md) |
| `timeout` | `int` | `30` | Request timeout in seconds, passed to each client that accepts it |
| `rate_limit_delay` | `float` | `1.2` | Delay passed to every client, replacing the client's own default |
| `api_key` | `str` or `None` | `None` | Shortcut for `credentials={"api_key": ...}` |
| `max_workers` | `int` or `None` | `None` | Thread-pool size; `None` uses one thread per source |
| `translate` | `bool` | `True` | Rewrite the query for each source; see [Query translation](#query-translation) |
| `credentials` | `dict` or `None` | `None` | Credentials for sources that accept them; see [Credentials](#credentials) |
| `primary` | `str` or `None` | `"europepmc"` if selected, otherwise `None` | Source whose records anchor the merge and win ties; `None` treats all sources equally |
| `primary_limit_factor` | `float` | `2.0` | The primary source is asked for `limit` times this many records |

Clients are created at the first search. Use `UnifiedSearch` as a context manager or call `close()` to close them.

### search

`search(query, limit=25, sort=None, sources=None, **kwargs) -> tuple[list[LiteratureResult], MergeReport]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | Query string |
| `limit` | `int` | `25` | Records requested from each source; the primary source is asked for `limit × primary_limit_factor` |
| `sort` | `str` or `None` | `None` | `"relevance"`, `"date"` or `"citations"`, translated into each source's own sort vocabulary; see below |
| `sources` | `list[str]` or `None` | `None` | Query only these configured sources |
| `**kwargs` | | | Passed to the sources whose `search()` accepts them |

`sort` takes one of three canonical values, which `UnifiedSearch` rewrites into what each source expects:

| `sort` | Europe PMC | PubMed | arXiv | OpenAlex | Semantic Scholar |
|---|---|---|---|---|---|
| `"relevance"` | default order | `relevance` | default order | `relevance` | default order |
| `"date"` | `P_PDATE_D desc` | `pub_date` | `date` | `date` | `publicationDate:desc` |
| `"citations"` (alias `"citation_count"`) | `CITED desc` | not supported | not supported | `citation_count` | `citationCount:desc` |

A source that cannot sort the way you asked keeps its own default order instead of receiving a value it would reject. Any other `sort` value is passed through unchanged, so a source-native value such as `sort="P_PDATE_D desc"` still works when Europe PMC is the only source you query.

A failing source does not stop the others. `report` is a [`MergeReport`](dedup.md#mergereport), and `report.metadata` holds:

| Key | Content |
|---|---|
| `source_counts` | Records each source returned, before deduplication |
| `source_errors` | `{source: message}` for sources that failed, including `"client not initialised"` |
| `source_times` | Seconds from the start of the parallel requests until each source finished |
| `sources_used` | The sources queried |
| `primary_source`, `primary_records`, `added_by_source` | With a primary source: its name, how many merged records match one of its records, and how many new records each other source added |

### search_all

`search_all(query, limit=25, **kwargs) -> tuple[dict[str, list[LiteratureResult]], dict[str, str]]`

Queries every configured source without deduplication and returns `(results_by_source, errors_by_source)`:

```python
from pyeuropepmc.features.search import UnifiedSearch

with UnifiedSearch(sources=["pubmed", "arxiv", "clinicaltrials"], rate_limit_delay=3.0) as searcher:
    per_source, errors = searcher.search_all("biomarkers", limit=10)

for source, papers in per_source.items():
    print(f"{source}: {len(papers)} records")
print(errors)
```

### Query translation

With `translate=True` the query is rewritten for each source by `pyeuropepmc.features.search.translate_query(query, source)`. For `TITLE:"gene editing" AND CRISPR`:

| Sources | Query sent |
|---|---|
| `europepmc`, `pubmed`, `clinicaltrials` | `TITLE:"gene editing" AND CRISPR`, passed through |
| `arxiv` | `all:"gene editing CRISPR"`; a query that already uses arXiv prefixes such as `ti:` or `cat:` is sent as written |
| `openalex`, `semantic_scholar`, `core`, `zenodo`, `doaj`, `dblp`, `hal` | `gene editing CRISPR`, with field tags, Boolean operators, quotes and parentheses removed |

Field syntax is not converted between Europe PMC and PubMed, so a fielded query written for one of them reaches the other as written. `translate_query()` never raises and returns the query unchanged for an unknown source.

## Sources

```python
from pyeuropepmc.features.search import registry

print(registry.available_sources())
print(registry.available_sources(installed_only=True))  # skip sources whose optional package is missing
print(sorted(registry.source_capabilities("europepmc")))  # ['date_filter', 'fulltext', 'get_paper', 'search']
```

| Key | Client | Covers | Credentials |
|---|---|---|---|
| `europepmc` | `EuropePMCLiteratureAdapter`, wrapping [`SearchClient`](search/README.md) | Europe PMC | |
| `pubmed` | `PubMedClient` | PubMed through NCBI E-utilities | `email` |
| `arxiv` | `ArxivClient` | arXiv preprints; see [arXiv client](arxiv.md) | |
| `clinicaltrials` | `ClinicalTrialsClient` | ClinicalTrials.gov; see [ClinicalTrials.gov client](clinical-trials.md) | |
| `semantic_scholar` | `SemanticScholarLiteratureAdapter` | Semantic Scholar; needs `pip install "pyeuropepmc[semanticscholar]"` | `api_key` |
| `openalex` | `OpenAlexLiteratureAdapter` | OpenAlex | `email` |
| `zenodo` | `ZenodoClient` | Zenodo datasets, software and publications | |
| `doaj` | `DOAJClient` | Directory of Open Access Journals articles | |
| `dblp` | `DBLPClient` | DBLP computer-science bibliography | |
| `hal` | `HALClient` | HAL open archive | |
| `core` | `COREClient` | CORE open-access aggregator; needs a free CORE API key | `api_key` |

ORCID and NIH iCite are enrichment clients that look up known identifiers, not search sources; see [ORCID and iCite clients](orcid.md).

### Credentials

```python
from pyeuropepmc.features.search import UnifiedSearch

with UnifiedSearch(
    sources=["europepmc", "pubmed", "semantic_scholar", "core"],
    credentials={"api_key": "YOUR_KEY", "email": "you@example.org"},
) as searcher:
    results, report = searcher.search("CRISPR", limit=10)
```

- `api_key` is passed to both Semantic Scholar and CORE; to use different keys, create those clients directly. `COREClient` reads the `CORE_API_KEY` environment variable when it gets no key.
- `email` is added to the User-Agent header of PubMed requests and puts OpenAlex requests in its polite pool (the address is sent as the `mailto` parameter).
- Constructor arguments a client does not accept are discarded. A credential the registry lists for that source is logged as a warning when it is dropped, so a mismatch does not pass unnoticed; other arguments are dropped at debug level.

### Rate limits

| Client | Own default `rate_limit_delay` (seconds) |
|---|---|
| `PubMedClient` | 0.35 |
| `ClinicalTrialsClient` | 0.5 |
| `EuropePMCLiteratureAdapter`, `OpenAlexLiteratureAdapter`, `DOAJClient`, `HALClient`, `COREClient` | 1.0 |
| `SemanticScholarLiteratureAdapter` | 1.2 |
| `ArxivClient`, `ZenodoClient`, `DBLPClient` | 3.0 |

`UnifiedSearch` passes its own `rate_limit_delay` (1.2 seconds unless you change it) to every client instead of these defaults. arXiv asks clients to make at most one request every three seconds, so use `UnifiedSearch(rate_limit_delay=3.0)` when arXiv is selected. No client shortens its delay when given an API key.

### Missing optional packages

If a selected source cannot be created, for example `semantic_scholar` without the `semanticscholar` package, `UnifiedSearch` logs a warning, skips the source and reports `"client not initialised"` in `source_errors`. `registry.load_source(name, **kwargs)` instead raises `OptionalDependencyError` (from `pyeuropepmc._optional_imports`, a subclass of `ImportError`) with the `pip install` command.

### Register a source

```python
from pyeuropepmc.features.search import registry

registry.register_source(
    registry.SourceSpec(
        name="my_repo",
        target="my_package.clients:MyRepoClient",  # imported on first use
        extras=("my_sdk",),                        # modules the client needs
        capabilities=frozenset({"search", "get_paper"}),
        credential_kwargs=("api_key",),
    )
)
```

`SourceSpec(name, target, extras=(), pip_extra=None, capabilities=frozenset({"search"}), credential_kwargs=())`. Registering an existing name raises `ValueError` unless you pass `replace=True`. `registry.load_entry_point_sources(group="pyeuropepmc.sources")` calls each zero-argument function published under that entry-point group; call it before creating `UnifiedSearch`.

The client class must accept `rate_limit_delay`, `timeout` or the credential names as keyword arguments (others are dropped) and return `LiteratureResult` objects from `search(query, limit=...)`. `LiteratureResult.source` only accepts the built-in names listed under [LiteratureResult](#literatureresult), so records from a new source must use one of them.

## Using a source client directly

The clients in `pyeuropepmc.features.search` share `search(query, limit=25, sort=None, **kwargs) -> list[LiteratureResult]` and `get_paper(identifier) -> LiteratureResult | None`, and can be used as context managers. The Semantic Scholar and OpenAlex adapters have the same two methods but no context-manager support.

### PubMed

```python
from pyeuropepmc.features.search import PubMedClient

with PubMedClient(email="you@example.org") as client:
    papers = client.search("ME/CFS", limit=10, sort="date")
    paper = client.get_paper("32791984")
    batch = client.get_papers_batch(["32791984", "32882182"])

print(paper.title, paper.doi, len(batch))
```

`PubMedClient(rate_limit_delay=0.35, timeout=15, cache_config=None, email=None, tool_name="pyeuropepmc")`:

- `search()` runs ESearch and then ESummary; `sort` is the E-utilities sort value, such as `"relevance"` or `"date"`.
- `get_paper(pmid, use_efetch=False)` and `get_papers_batch(pmids, use_efetch=False)` use ESummary. With `use_efetch=True` they read the full EFetch record, which adds MeSH terms, publication types, keywords and grants under `pubmed_data`, with one request per PMID.
- `pmid_for_citation(author=None, year=None, journal=None, volume=None, first_page=None, title=None)` resolves a citation with ECitMatch and returns the PMID or `None`.

### Semantic Scholar and OpenAlex

```python
from pyeuropepmc.features.literature.adapters import (
    OpenAlexLiteratureAdapter,
    SemanticScholarLiteratureAdapter,
)

semantic_scholar = SemanticScholarLiteratureAdapter(api_key=None)
papers = semantic_scholar.search("machine learning", limit=10)

openalex = OpenAlexLiteratureAdapter()
works = openalex.search("CRISPR", limit=10, sort="citation_count")

print(len(papers), len(works))
```

`SemanticScholarLiteratureAdapter(enrichment_client=None, api_key=None, rate_limit_delay=1.2, timeout=15)` passes `sort` to Semantic Scholar as given. `OpenAlexLiteratureAdapter(enrichment_client=None, rate_limit_delay=1.0, timeout=15, cache_config=None)` accepts `sort` values `"citation_count"`, `"date"` and `"relevance"`. Both classes are also exported by `pyeuropepmc.features.literature`.

### Zenodo, DOAJ, DBLP, HAL and CORE

```python
from pyeuropepmc.features.search import COREClient, DBLPClient, DOAJClient, HALClient, ZenodoClient

with ZenodoClient() as client:
    datasets = client.search_datasets("metabolomics", limit=10)

with DOAJClient() as client:
    articles = client.search("open access publishing", limit=10)

with DBLPClient() as client:
    cs_papers = client.search("knowledge graph", limit=10)

with HALClient() as client:
    hal_papers = client.search("neuroscience", limit=10)

with COREClient(api_key="YOUR_CORE_KEY") as client:
    core_papers = client.search("machine learning", limit=10)

for paper in datasets + articles + cs_papers + hal_papers + core_papers:
    print(paper.source, paper.title)
```

- `ZenodoClient(rate_limit_delay=3.0, timeout=30)` also offers `search_publications(query, limit=25)` and `search_software(query, limit=25)`.
- `COREClient(api_key=None, rate_limit_delay=1.0, timeout=30)` returns at most 100 records per call; `search(..., fulltext_only=True)` limits results to records with full text.
- `DOAJClient` and `HALClient` default to a 1.0-second delay, `DBLPClient` to 3.0 seconds.

## LiteratureResult

All clients return `pyeuropepmc.models.LiteratureResult`, a Pydantic model:

| Field | Type | Description |
|---|---|---|
| `doi` | `str` or `None` | Lower-cased, without a `https://doi.org/` prefix |
| `pmid`, `pmcid` | `str` or `None` | |
| `title` | `str` or `None` | |
| `authors` | `list[Author]` or `None` | `Author(name, orcid=None, affiliation=None, institution=None, position=None)` |
| `publication_year` | `int` or `None` | |
| `journal` | `str` or `None` | |
| `abstract` | `str` or `None` | |
| `citation_count` | `int` or `None` | |
| `source` | `str` | One of `europepmc`, `pubmed`, `semanticscholar`, `openalex`, `crossref`, `unpaywall`, `arxiv`, `clinicaltrials`, `zenodo`, `doaj`, `dblp`, `hal`, `core`, `icite` |
| `source_id` | `str` | Identifier within the source |
| `extra_metadata` | `dict` or `None` | Source-specific values |
| `semantic_scholar_data`, `openalex_data`, `pubmed_data` | `dict` or `None` | Raw source records |

Semantic Scholar records have `source="semanticscholar"`, while the registry key is `semantic_scholar`. The model accepts additional fields. `to_paper_entity()` converts a result to a `PaperEntity`, and `merge(other)` returns a new result that fills this result's empty fields from `other`.

Known limitation: author names given as surname followed by initials, the form PubMed and Europe PMC use, are reversed during normalization, so `Smith J` becomes `J, Smith`.

## Normalization utilities

The clients clean identifiers and text with functions from `pyeuropepmc.features.literature`:

```python
from pyeuropepmc.features.literature import (
    is_valid_doi,
    normalize_abstract,
    normalize_author_name,
    normalize_doi,
    normalize_mesh_terms,
    normalize_paper_title,
)
from pyeuropepmc.features.literature.normalization import normalize_pmid

print(normalize_doi("https://doi.org/10.1000/ABC.123"))              # 10.1000/abc.123
print(is_valid_doi("10.1000/xyz"), is_valid_doi("abc"))              # True False
print(normalize_author_name("John Smith"))                           # Smith, John
print(normalize_paper_title("  CRISPR   screens.  "))                # CRISPR screens
print(normalize_abstract("BACKGROUND: Some   text."))                # Some text.
print(normalize_mesh_terms(["neoplasms", "Neoplasms", " Humans "]))  # ['neoplasms', 'Humans']
print(normalize_pmid("PMID:12345678"))                               # 12345678
```

| Function | Returns |
|---|---|
| `normalize_doi(doi)` | Lower-cased DOI without resolver or `doi:` prefix; `None` if it is not a DOI |
| `is_valid_doi(doi)`, `is_valid_pmid(pmid)` | `bool`; import `is_valid_pmid` from `pyeuropepmc.features.literature.normalization` |
| `normalize_pmid(pmid)` | The digits as a `str`, or `None`; import from `pyeuropepmc.features.literature.normalization` |
| `normalize_author_name(name)` | `"First Last"` becomes `"Last, First"`; `"Last, First"` is kept |
| `normalize_author_list(authors)` | The list of author dicts with normalized names |
| `normalize_paper_title(title)` | Unicode NFKC, collapsed whitespace, trailing punctuation removed |
| `normalize_abstract(abstract, strip_headers=True)` | Section labels such as `BACKGROUND:` removed, whitespace collapsed |
| `normalize_mesh_terms(terms)` | Trimmed terms with case-insensitive duplicates removed |
| `normalize_journal_title(journal)`, `normalize_affiliation(affiliation)`, `normalize_to_nfkc(text)` | Unicode and whitespace cleanup |

## See also

- [Deduplication](dedup.md)
- [Searching Europe PMC](search/README.md)
- [ORCID and iCite clients](orcid.md)
