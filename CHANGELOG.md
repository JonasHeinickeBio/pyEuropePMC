# Changelog

All notable changes to PyEuropePMC are documented here.

## [Unreleased]

### 🐛 Bug Fixes

- `analyze_search`, found by running it against the live Europe PMC. (1) Records dated in the
  future (2096 on a search for `cancer`) pushed the window of 60 years out of range, so 5.6 million
  records fell into one `before` bucket and `by_year` showed one meaningless year: the years now
  end with the current year and later-dated records are one `after` bucket (`years` + `before` +
  `after` + `undated` is still `hit_count`). (2) Without pandas, which is what `uvx pyeuropepmc mcp`
  installs, the default call (no `metrics`) failed outright because the default set includes the
  sample metrics; it now returns the counted metrics and marks the others `basis: unavailable`
  with the install hint, while naming a sample metric still fails with that hint. (3) The 60
  yearly counts took about 40 s because the shared client sends one request at a time; each
  worker thread now counts through a client of its own (about 24 s for `cancer`).
- Real-world tests (`tests/mcp/e2e/test_mcp_real_world.py`): the exact numbers of `analyze_search`
  against independent `count_papers` counts, the paper resources against the tool on real articles,
  and the bearer token on a real socket with a session id.

## [4.4.0] - 2026-10-26

> Multi-source search: where results came from. `UnifiedSearch.search(diagnostics=True)` and the MCP
> tool `unified_search(diagnostics=true)` report what each source did (answered, found nothing,
> failed, was rate limited, or could not be created) and which sources returned each record.
> Opt-in; the default result is unchanged.

### ✨ Features

- Per-source rate limits and concurrency for `UnifiedSearch` (#373). `rate_limits={"arxiv": 5.0}`
  sets the delay between requests per source (it wins over `rate_limit_delay`, which still sets one
  delay for all), and `source_concurrency` (an `int`, or `{source: n}`) caps how many calls one
  source gets at the same time across all threads that share the object, 1 by default, so several
  overlapping searches, as in a server, queue up instead of hitting a provider together. The limits
  that applied are in every result, `report.metadata["effective_limits"]`, and with `diagnostics`
  the status rows also carry `rate_limit_delay`, `max_concurrency` and `waited_seconds`. Bad
  values (a source that is not in `sources`, a negative delay, a cap below 1) raise `ValueError`.
  The multi-source search guide documents the order in which a delay is chosen, the two levels of
  concurrency (`max_workers` for the sources of one search, `source_concurrency` across searches)
  and safe defaults for repeated and large searches.

### 🐛 Bug Fixes

- `rate_limit_delay` was never applied to a successful request by the HTTP source clients (arXiv,
  PubMed, DOAJ, CORE, HAL, Zenodo, DBLP, ClinicalTrials.gov): the sleep sat at the end of the retry
  loop, which a successful request leaves by returning. Found by measuring real requests to arXiv,
  which arrived 0.3 s apart with a 3 s delay set. Each client now reserves a start slot under a
  lock before every request (`BaseHTTPClient._wait_turn`), so requests of one client, from any
  number of threads, start at least `rate_limit_delay` apart; arXiv now sees exactly 3.0 s. Searches
  across these sources are correspondingly slower, as the delays always intended.
- `UnifiedSearch.search(sources=[...])` could not use a source outside the set the object was
  built with: the source was skipped without a word, so the MCP tool `unified_search` with
  `sources=["openalex", ...]` returned only Europe PMC and PubMed results. Any registered source
  may now be named in a call; its client is created on first use, one that cannot be created is
  `unavailable` with the real reason, and an unknown name raises `ValueError`.

- A source whose client swallowed a failure (Semantic Scholar answering HTTP 403, OpenAlex and the
  Europe PMC adapter on any request error, DBLP answering a bot-check page instead of JSON) was
  reported as `empty`, which reads as "no results". These clients now record the error in
  `last_error` and `UnifiedSearch` raises it when the answer is empty, so the source is `error`
  (or `rate_limited`) with the real message, in `source_errors` and in the diagnostics. Found by
  running ten live sources through `unified_search(diagnostics=true)`.

### 🔄 Changed

- Without an explicit `rate_limit_delay`, arXiv, DBLP and Zenodo are now paced at 3 seconds instead
  of the 1.2 seconds every source used to get. arXiv asks for one request every three seconds;
  these three clients already defaulted to 3 s on their own, and `UnifiedSearch` had overridden
  that. Passing `rate_limit_delay` or `rate_limits` still decides the delay, as before.

### ✨ Features

- `UnifiedSearch.search(..., diagnostics=True)` and the MCP tool `unified_search(diagnostics=true)`
  say where each result came from and what each source did (#289). Opt-in, so the default result
  keeps its shape: `report.metadata["source_status"]` has one record per queried source
  (`status` is `ok`, `empty`, `error`, `rate_limited` for HTTP 429 or a rate-limit message, or
  `unavailable` when the client could not be created, with the reason; plus record count, seconds,
  limit, the query and sort actually sent, the error type, message and HTTP status, and a numeric
  `Retry-After`), and every merged record gets `matched_sources`, the sources that returned that
  paper. An empty source and an unavailable one are now distinguishable. The MCP tool returns the
  records and a `sources` object. Documented in the multi-source search guide and the API
  reference.

## [4.3.0] - 2026-10-26

> MCP release: authentication. The streamable-HTTP and SSE transports can now require a bearer
> token, so the server can be run as a network service without a proxy in front. Nothing changes
> without a token, and stdio is never checked.

### ✨ Features

- Opt-in bearer-token authentication for the MCP HTTP transports (#288). With a token
  (`PYEUROPEPMC_MCP_AUTH_TOKEN`, comma separated, or `--auth-token-file` /
  `PYEUROPEPMC_MCP_AUTH_TOKEN_FILE`, one per line) every request to the streamable-HTTP and SSE
  transports needs `Authorization: Bearer <token>`; anything else gets HTTP 401 with
  `WWW-Authenticate: Bearer` before the MCP server sees it. It is a plain ASGI middleware, so it
  works under MCP SDK 1.x and 2.x, and resources and prompts are covered like tools. Tokens are
  compared in constant time, need 16 or more printable characters, are never logged, and are never
  taken from the command line (`--auth-token VALUE` is refused without echoing the value); a
  variable or file that is set but empty stops the server instead of leaving it open. Several
  tokens allow rotation, `pyeuropepmc-mcp --generate-token` prints a new one, and binding to a
  non-loopback address without a token logs a warning. stdio and the default (no token)
  behaviour are unchanged. The MCP server guide has a section on the threat model, proxy
  deployment, rotation and what the token does not do (no per-user identity, no OAuth, TLS is
  the proxy's job).

## [4.2.0] - 2026-10-22

> MCP release: search analytics, resources and prompts. `analyze_search` summarises a search
> without returning its records and labels every metric `exact` or `sample`; papers are
> attachable as `epmc://paper/...` resources, and three prompts encode literature workflows. The
> server now has 47 tools.

### ✨ Features

- MCP resources and prompts (#319). Resource templates `epmc://paper/{pmcid}` (Markdown full
  text), `epmc://paper/{pmcid}/references` (parsed references as JSON, cut at an entry after
  100,000 characters) and `epmc://paper/{pmcid}/outline` (section titles, block counts and
  sizes). They run the code of `get_paper_fulltext`, so the open-access check, the XML cache,
  the 30,000-character limit and the error messages are the tool's; a failure reaches the client
  with its reason under both SDK generations (2.x shows a client only the message of a
  `ResourceError`, so the tool's `ToolError` is converted). Prompts `literature_review(topic,
  years, max_papers)`, `critical_appraisal(pmcid)` and `citation_trace(pmid, direction)` spell out
  sequences of this server's tools; a test reads every tool and parameter out of the prompt texts
  and checks them against `list_tools()`. The optional `epmc://search/{query}` resource is not
  offered: queries contain characters clients encode inconsistently, and `search_papers` takes
  them as a typed argument.

- New MCP tool `analyze_search` (#316): aggregate statistics about a search without returning its
  records. `by_year` (one `FIRST_PDATE:[Y TO Y]` count per year, at most 60 years plus one
  `before` bucket, with `undated` so that the parts add up to `hit_count`), `open_access` and the
  citation `thresholds` (`CITED:[n TO *]`) are counted by Europe PMC over the whole result set and
  labelled `basis: exact`. `journals`, `authors`, `types`, `countries`, `funders` and the
  `citations` statistics are computed from the first `limit` records (default 500, at most 1,000;
  `sort` sets the order) with the library's analytics functions and labelled `basis: sample`
  with a `sample_note`; they are `exact` only when `limit` covers the whole result. The response
  always carries `hit_count`, `limit` and `records_read`, and holds plain JSON, never a pandas
  object. The sample metrics need the `analytics` extra and say so before any request is made;
  the counted ones work in a core install. It takes the filters of `count_papers`. The server now
  has 47 tools.

### 🐛 Bug Fixes

- `SearchClient` sends one request at a time (`serialize_requests`): its `requests.Session` is
  shared by the MCP server's concurrent tool calls and by the per-year counts of
  `analyze_search`, and a session is not documented as safe for concurrent use. The delay after
  a request stays outside the lock, so waiting still overlaps (10 yearly counts: 6.8 s live).
- `geographic_analysis`: a country written with full stops (`USA.`, `U.S.A.`, `U.K.`) was counted
  as a country of its own and never reached the name mapping, so `Usa.` and `United States`
  were two countries. The dots are dropped before the name is mapped.

## [4.1.0] - 2026-10-22

> MCP release: sentence roles. `tag_paper_sentences` groups the body sentences of a paper by what
> they do (method, result, limitation, ...), whatever its headings are called. The server now has
> 46 tools.

### ✨ Features

- New MCP tool `tag_paper_sentences`: the sentences of an open-access paper's body grouped by
  rhetorical role (`background`, `motivation`, `method`, `result`, `claim`, `limitation`,
  `conclusion`, or `unknown`). Front matter, references, captions and administrative sections
  (acknowledgments, funding, conflicts, ethics and consent statements) are excluded; `roles`,
  `sections`, `min_confidence` and `max_chars` filter, sentences are never cut and `truncated`
  says whether some were left out. It reuses the full-text download and cached XML of
  `get_paper_fulltext`. The rules use the section a sentence is in plus cues in the sentence;
  the older `RhetoricalHighlighter` (keywords for computer-science papers) labelled 13 of 93
  hand-labelled biomedical sentences correctly, the tool's rules 82 (precision 0.92 to 1.00 per
  role; 43 of 46 on the sentences used while writing them, 22 of 23 on a paper labelled
  beforehand, 17 of 24 on a harder sample). Without recognisable headings only background,
  method and conclusion are returned. A scientific sentence splitter (abbreviations, `et al.`,
  genus initials, numbers) is included. `use_llm` asks the configured LLM about up to 40
  `unknown` sentences; that path is tested with a fake client only.

## [4.0.1] - 2026-10-21

> Patch release: connections no longer stall for 30 to 60 seconds on a network with an IPv6
> address but no IPv6 route.

### 🐛 Fixed

- A new connection no longer waits for a dead IPv6 address. Python tries a host's addresses one
  at a time, IPv6 first, each for the full connect timeout, so on a network with an IPv6 address
  but no IPv6 route every new connection stalled for 30 to 60 seconds before it tried IPv4 (the
  first request to `id.nlm.nih.gov` took 97.6 s that way and 1.2 to 3.8 s with the fix; `curl`
  takes 0.6 s). The clients now connect as RFC 8305 describes: the next address starts 0.25 s
  after the previous one, the first connection that completes is used and the others are
  closed (`pyeuropepmc.core.network`). On a working network the first address wins and nothing
  changes. It covers every client that owns a session (`BaseAPIClient` and the clients built on
  `BaseHTTPClient`: search, article, annotations, full-text sessions, all enrichment sources) and
  the MCP server's NLM lookups. `PYEUROPEPMC_HAPPY_EYEBALLS=0` restores the plain behaviour.
  Not covered: the places that call `requests.get` directly (some full-text downloads, the
  citation walker, `features.review.mesh`, the query builder's field check, dataset downloads),
  which keep the old behaviour.

## [4.0.0] - 2026-10-21

> Major release: the MCP server moves to MCP Python SDK 2.x, and gains question decomposition
> (PICO, SPIDER) and MeSH expansion. The server now has 45 tools. The Python API of the library
> is unchanged; the major version marks a change in the installed dependency set and in how the
> HTTP transports behave.

### ⚠️ Upgrade notes

- The lock file and `requirements.txt` pin `mcp` 2.3.0. A fresh install now brings `httpx2`,
  `httpcore2`, `mcp-types`, `opentelemetry-api` and `truststore`, and no longer `httpx`,
  `httpcore`, `httpx-sse` or `pydantic-settings`. `pip install pyeuropepmc` still accepts
  `mcp>=1.20.0,<3.0.0`, so an environment that keeps MCP SDK 1.x for another package works; the
  server detects the SDK it finds.
- With SDK 2.x the HTTP transports (`--transport sse` and `streamable-http`) answer HTTP 421 to a
  `Host` header they do not know. Behind a reverse proxy that forwards its public name, start the
  server with `--allowed-host mcp.example.org` (or `PYEUROPEPMC_MCP_ALLOWED_HOSTS`). Loopback
  names stay allowed. Not available on SDK 1.x.
- `pydantic` moves to 2.14 in the lock (with `pydantic-core` 2.50) and `starlette` to 1.7 on
  Python 3.10 and 1.9 on 3.11 and later.

### ✨ Features

- New MCP tool `pico_decompose`: a research question split into PICO, PICOS, PICOT or SPIDER
  elements, offline and without a model. Each element is a verbatim span of the question with its
  position; elements the question does not state are reported in `missing` and
  `optional_missing`, never filled in. It builds a Europe PMC query (population condition AND
  intervention by default; `query_elements` and `mesh` change it) and checks it with the
  `validate_query` linter. The existing `PICOParser` takes the rest of the sentence for each
  element and found 5 of 106 stated elements on 36 gold questions, so the tool uses its own
  rules: 39 of 39 on the 12 questions used while writing them, 39 of 39 on 12 written
  beforehand, 11 of 28 on 12 phrased outside the patterns (`benchmarks/evaluate_pico_parser.py`),
  and nothing invented.
- New MCP tool `mesh_expand`: MeSH descriptor, tree numbers, entry terms and a Europe PMC
  fragment for each term, joined with AND or OR into a checked query. Offline by default from a
  bundled snapshot of 244 common clinical headings taken from NLM's published MeSH
  (`scripts/build_mesh_snapshot.py`); terms outside it are reported unmatched, not guessed.
  `use_api=true` asks the NLM MeSH service and covers all of MeSH; its `time_budget` (30 s) bounds
  the whole call and terms not reached are reported as skipped. The tool is annotated as open-world
  because that option sends the terms to id.nlm.nih.gov.

### 🔧 Changed

- The MCP server runs on MCP Python SDK 2.x as well as 1.x (`mcp>=1.20.0,<3.0.0`; the lock file
  now pins 2.3.0). SDK 2.x renamed `FastMCP` to `MCPServer`, moved `ToolError` and `Context`,
  and moved the HTTP settings from the server object to `run()`; the server imports whichever
  exists and tool behaviour, names, schemas and `server.json` are unchanged. Dependabot no
  longer ignores major `mcp` updates. A CI job runs the MCP unit tests against the newest 1.x.
- New `--allowed-host` option (`PYEUROPEPMC_MCP_ALLOWED_HOSTS`) for the HTTP transports: SDK
  2.x answers HTTP 421 to a `Host` header it does not know, which breaks a reverse proxy that
  forwards its public name. Loopback names and origins stay allowed, and each name is also
  accepted as a browser `Origin` over http and https. Values are trimmed and a URL or port is
  refused. Not available on SDK 1.x.

## [3.9.0] - 2026-10-21

> MCP release: enrichment. `enrich_paper` merges Europe PMC, Crossref, OpenAlex, Semantic Scholar and
> iCite into one compact record with impact, funding, institutions, open access and retractions,
> and says for every source whether it answered. The server now has 43 tools.

### ✨ Features

- New MCP tool `enrich_paper`: one compact record for a paper (PMCID, PMID, DOI or doi.org URL)
  merged from Europe PMC, Crossref, OpenAlex, Semantic Scholar, iCite and, with
  `UNPAYWALL_EMAIL`, Unpaywall. `include` picks the field groups `impact`, `funding`,
  `affiliations`, `oa` and `updates`; `sources` limits the sources. The answer has a `sources`
  map with `ok`, `empty`, `error` (with the reason), `timeout` (still running when
  `time_budget` ended) or `unavailable` for each source, so a failed source or a Semantic
  Scholar rate limit gives a partial record. About 2 to 7 KB. Read-only: it never saves
  responses or passes a directory to the enricher.
- `PaperEnricher` looks ROR up once, after the merge, and no longer lets its OpenAlex client
  fetch the same records first (one request per author-institution pair, kept by nobody):
  with ROR on, 14 requests became 1 for a paper with one institution on 13 author lines and 29
  became 12 for another; the median call with ROR went from 8.4 s to 5.3 s. Source requests
  now share a worker pool capped at four per source, so repeated calls against a stalled service
  queue (and are reported as `timeout`) instead of piling up threads. The raw `openalex` entry
  of a `PaperEnricher` result no longer carries ROR details; the merged record and `ror` do.
- Measured timings of `enrich_paper` per source and together are in the MCP server guide, with
  `benchmarks/benchmark_enrich_paper.py` to repeat them.
- `enrich_paper(ror_details=True)` adds city, country code, website and coordinates of each
  institution from ROR. It is off by default because it costs one request per institution; the
  time budget covers it, and the `sources` map shows `ror` with how many institutions it reached.
- `PaperEnricher.enrich_paper` has `only_sources` and `time_budget` parameters and returns a
  `source_status` map (`ok`, `empty`, `error`, `timeout`, `skipped`) next to `sources`, with a
  `ror` entry when ROR is enabled. Without them it behaves as before.
- The merged enrichment record has `is_retracted` and `updates`: correction and retraction
  notices from Crossref (`updated-by`, `update-to`) and Europe PMC (retraction, erratum and
  expression-of-concern links, the `Retracted Publication` type).

### 📚 Documentation

- New [MCP server guide](docs/features/mcp-server.md): which tool for which job, the common
  workflows (checking a query, exporting references, reading a paper, finding entities and data,
  following citations), the Europe PMC behaviours the tools work around, how to diagnose a
  failure, and the limits of each tool. The README's MCP section is a table by job instead of one
  long sentence. `tests/mcp/unit/test_mcp_docs.py` fails when a tool is missing from the tool
  table or the server docstring, or when the tool count in the docs is out of date.

## [3.8.0] - 2026-10-19

> MCP release: data links. `get_paper_data_links` answers "where is the data of this paper?"
> and `get_paper_lab_links` lists what third parties link to it. The server now has 42 tools.

### ✨ Features

- New MCP tools `get_paper_data_links` and `get_paper_lab_links`. `get_paper_data_links` answers
  "where is the data of this paper?" from Europe PMC's consolidated `datalinks` service: accession
  numbers text-mined from the full text (dbSNP, RefSeq, OMIM, ClinicalTrials.gov, cited DOIs) and
  records that providers link to the paper (BioStudies supplementary data, model-organism
  databases, Altmetric), flattened to one list with `category`, `kind`, `scheme`, `id`, `url`,
  `origin` (text mined or supplied by a provider) and mention count, with counts per category
  and scheme and a category/scheme filter. The service labels every link `dataset`, even an
  Altmetric page, so the category and section tag are used instead. `get_paper_lab_links`
  lists third-party links grouped by provider; Europe PMC ignores `providerId` and `pageSize`, so
  the provider filter and the limit are applied by the server. A paper without links gives an
  empty list. Supplementary files stay in `paper_figures`; no separate tool was added.

## [3.7.0] - 2026-10-19

> MCP release: export. `export_papers` turns a search or a list of identifiers into BibTeX,
> RIS, CSL-JSON, CSV, JSON or Markdown. The server now has 40 tools.

### ✨ Features

- New MCP tool `export_papers`: papers as BibTeX, RIS, CSL-JSON, CSV, JSON or
  Markdown, for a search `query` or a list of `ids`, ready for Zotero, Mendeley,
  EndNote, Pandoc or a spreadsheet. BibTeX keys (`vasiliou2005analysis`) are
  unique within an export, get `a`, `b`, ... on a collision and do not change
  when the export is cut to size; text that LaTeX reads as syntax (`& % # _ $`) is
  escaped, a consortium name stays one author, RIS has separate `SP` and `EP`
  lines and keywords, and a paper with more than 100 authors lists the first
  100 (BibTeX adds `and others`). Records are never cut in the middle: `truncated`
  says that some were left out and `next_skip` or `remaining` say where to
  continue. Nothing is written to disk. DOIs are passed through untouched; old
  ones such as `10.1002/(SICI)...<1661::AID-SIM968>3.0.CO;2-2` contain `<...>`.

### 🔧 Maintenance

- Dependency updates: coverage 7.16.2, cachetools 7.2, langchain 1.4, urllib3 2.8.0 and
  newer GitHub Actions (checkout 7, setup-uv 10.3, codecov-action 7.1). `mcp` 2.x is not
  supported yet (tracked in #334); Dependabot ignores major `mcp` bumps until then.

## [3.6.0] - 2026-10-19

> MCP release: service status and cache tools. `epmc_status` tells an agent whether a failure is
> Europe PMC's before it retries. The server now has 39 tools.

### ✨ Features

- New MCP tools `epmc_status`, `cache_status` and `clear_cache`. `epmc_status`
  probes the four endpoints the health workflow watches (search, full text,
  citations, annotations) at once, with one request each, a short timeout and the
  body never read, and answers `ok`, `degraded`, `down` or `unknown` (only 4xx) with
  the HTTP status and milliseconds of each; the answer is kept for 30 seconds so
  asking again does not probe again. The endpoint list is defined once in code and
  a test compares it with `europepmc-health.yml`. `cache_status` reports entries,
  capacity, size, hits, misses and hit rate of the search, article and annotation
  caches and of the full-text XML cache (which now counts its hits), counts only:
  no keys, content or paths. `clear_cache` empties one of those in-memory caches
  and is declared as changing state (`readOnlyHint: false`).

## [3.5.0] - 2026-10-19

> MCP release: query tools. Europe PMC answers a malformed query with a different result
> instead of an error; `validate_query` catches that before the query is sent. The
> server now has 36 tools.

### ✨ Features

- New MCP tools `validate_query`, `build_query`, `translate_query` and
  `evaluate_query`. Europe PMC does not reject a malformed query, it answers a
  different one: an unclosed parenthesis or a dangling operator is dropped
  silently (`malaria AND (dengue OR zika` finds 7,226 records, the closed query
  26,733), an unknown field, a flag that is not `y`/`n` and a date range with a
  missing or reversed bound match nothing, a bare leading wildcard gives HTTP
  503, and AND mixed with OR without parentheses is not read as either grouping
  (`a AND b OR c` returns just the records of `a`). `validate_query` reports each
  of these with its position, checks fields against Europe PMC's own field list
  and normalises a valid query. `build_query` writes a query from structured
  input (`all_of`, `any_of`, `none_of`, dates, open access, full text, source,
  `cites`) and explains it; `search_papers`, `count_papers` and `build_query`
  now share one filter implementation built on `QueryBuilder`.
  `translate_query` rewrites a query for PubMed, with `exact`, `warnings` and
  `dropped` for the constructs that do not map, and as a keyword approximation
  for arXiv, OpenAlex, Semantic Scholar and Crossref. `evaluate_query` scores a
  query against papers you already know: recall, the PMIDs it misses, excluded
  papers it still finds, precision and F1 on the seeds, measured by running the
  query on Europe PMC.

## [3.4.0] - 2026-10-19

> MCP release: batch lookups for metadata and full text, and a fix for sections that
> shrank to their heading under a size cap. The server now has 32 tools.

### 🐛 Bug Fixes

- **MCP `get_paper_fulltext` could return a bare section heading.** When the first
  paragraph or table of a section did not fit `max_chars`, the heading used up the
  budget and the section came back as `## Conclusions` with no text. The first
  *block* is now cut to the remaining budget instead; a heading never counts as
  content.

### ✨ Features

- New MCP tools `get_papers_batch` and `get_papers_fulltext_batch`, for agents that
  would otherwise make one call per paper. `get_papers_batch` takes up to 100 PMIDs,
  PMCIDs and DOIs (mixed), looks them up with one combined Europe PMC query per 50
  identifiers (120 identifiers answer in about half a second), and returns a result
  with a status (`ok`, `not_found`, `invalid`, `error`) for every input in the order
  given; a bad identifier never fails the batch. `fields` chooses what comes back,
  with `abstract` optional. `get_papers_fulltext_batch` returns the markdown full
  text of up to 20 papers within a size budget: papers that are not open access
  are reported without being downloaded, the rest are fetched four at a time, and
  once `max_total_chars` is used up the remaining papers are `skipped_budget` and
  not downloaded.

## [3.3.0] - 2026-10-19

> MCP release: `find_open_access` tells an agent where a paper that is not open access in
> Europe PMC can be read for free. The server now has 30 tools.

### ✨ Features

- New MCP tool `find_open_access`: where a paper can be read for free. It looks
  the DOI (or the DOI behind a PMID or PMCID) up in Unpaywall once and returns the
  open-access status, the best copy with its PDF link and licence, up to five
  alternatives, and `europepmc_fulltext`, which says whether `get_paper_fulltext`
  will work for the paper. It needs a contact e-mail in `UNPAYWALL_EMAIL` (or
  `CROSSREF_EMAIL`), the variables the library already reads, and has no default
  address; without one it says which variable to set. `server.json` declares the
  variable.

## [3.2.0] - 2026-10-19

> MCP release: text-mined annotations. `AnnotationsClient` returned no data for any
> article and its entity lookup always failed; both are fixed. The server now has
> 29 tools.

### 🐛 Bug Fixes

- **`AnnotationsClient` discarded every real article response.**
  `annotationsByArticleIds` answers with a top-level list, but
  `normalize_annotations_response` accepted only an object and replaced a list
  with an empty `valid: False` result, so `get_annotations_by_article_ids`
  returned no data for any article. A list is now kept under `raw` and
  `annotations`.
- **`AnnotationsClient.get_annotations_by_entity` always failed with HTTP 400.**
  It sent `entityId`, `entityType` and `page`; the API takes `entity`, an optional
  `type` and a `cursorMark`, and accepts a `pageSize` of 1 to 8 only (the old
  default was 25). `entity_type` is now optional, `page_size` defaults to 8 and is
  validated against that range, and `cursor_mark` pages through the results.
  Europe PMC's entity search ignores `type`, `provider` and `section`; the
  docstring says so.

### ✨ Features

- New MCP tools `get_paper_annotations` and `find_papers_by_entity`: the
  genes, proteins, chemicals, diseases and organisms that Europe PMC text-mined
  from a paper, grouped by entity with mention counts, sections and example
  mentions (a review with 371 mentions comes back as a 15 KB entity list instead
  of 154 KB), and the articles in which a given entity occurs, with cursor paging.

## [3.1.0] - 2026-10-19

> MCP release. `search_papers` could hang on any broad query, and
> `get_paper_citations` never returned a result; both are fixed, and the server
> gains full-text retrieval. The server now has 27 tools.

### 🐛 Bug Fixes

- **MCP `search_papers`, `search_authors`, `get_paper_details` and the LLM tools
  fetched every match.** They passed `pageSize` but no `max_results` to
  `SearchClient.search_all`, so `limit` only sized the pages. A broad query
  such as `CRISPR` (about 240 000 hits) paged through the whole result set and
  hung or died on a network error; `search_authors` returned hundreds of
  records for `limit=3`. The tools now stop at `limit`.
- **MCP `get_paper_citations` always returned nothing.** It searched
  `CITED:<pmid>`, a citation-count field, instead of listing the citing
  papers. It now uses the citations endpoint, which also works for PMC and
  preprint IDs (new `source` argument).
- **MCP `citation_snowball` returned 0 papers for a bare PMID or DOI.**
  Semantic Scholar only resolves an external ID with its type prefix; the tool
  now adds `PMID:`, `PMCID:` or `DOI:`.

### ✨ Features

- MCP `search_papers` takes `date_from`, `date_to`, `open_access`,
  `has_fulltext`, `source` and `synonym`.
- New MCP tool `get_paper_fulltext`: the structured full text of an open-access
  paper by PMCID, PMID or DOI, as markdown, typed sections or an outline, with
  a section filter, a `max_chars` cap that cuts at a block boundary, and
  optional parsed references. It drops the per-block `schema_version` / `inlines`
  bookkeeping and the triple copy of every table, and `paper_figures` shares its
  cached XML.
- MCP full-text and figure tools check `isOpenAccess` first. Europe PMC answers
  a full-text request for a non-open-access article with HTTP 500 after about
  20 s of retries, which read like an outage; they now fail in about a second
  and name the reason.
- New MCP tools `count_papers` (hit count for a query, with the same filters)
  and `get_paper_references` (reference list of a paper).

### 📚 Documentation

- The MCP Registry entry (`server.json`) has a description that says what the
  server does, and declares its optional environment variables
  (`SEMANTIC_SCHOLAR_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
  `OPENAI_MODEL`, `PYEUROPEPMC_MCP_LOG_LEVEL`) so clients can offer them at
  install time. The PyPI page gains keywords, project links and a description
  that mentions the MCP server. The READMEs show how to add the server to Claude
  Code, Cursor and VS Code.

### 🔧 Maintenance

- The MCP end-to-end tests pass the environment to the server subprocess; before,
  they imported whichever pyeuropepmc was installed instead of the code under
  test.

## [3.0.0] - 2026-09-17

> **Major release.** Full-text parsing, reference extraction, metadata and
> caching were checked against real documents rather than hand-written
> fixtures, and most of what surfaced was wrong output rather than a crash;
> see the Bug Fixes below for the affected methods. The lxml backend is
> removed and every XML entry point now goes through defusedxml, which is
> why this is a major bump rather than a patch.

### 💥 Breaking Changes

- **The lxml backend is removed.** `LXMLParser` and `is_lxml_available` are no
  longer exported from `pyeuropepmc.features.fulltext.extensions`.
  `FullTextXMLParser` parses exactly as before. The backend was opt-in, lxml was
  never a declared dependency, and CI never ran its tests. Measured on 36 papers
  it was no faster end to end, and it crashed building structured output for 15
  of them, ran words together, and returned no sections for JATS that uses a
  default namespace.

### 🔒 Security

- **One contract for a refused document.** defusedxml refuses XML that declares
  entities, and that refusal now reaches callers the same way everywhere: the
  JATS normalizer, the bioRxiv manifest, the benchmark metrics and the parse
  profiler raise `ParsingError` instead of a raw `defusedxml.EntitiesForbidden`,
  which `except ParseError` never caught. A refusal has its own code,
  `PARSE005`, so it is no longer reported as "Content cannot be None or empty".
  The arXiv, PubMed and figure paths still return their empty value and now log
  the reason; the MCP tool `paper_figures` reports an error instead of zero
  figures. Hostile XML is now tested against every entry point that parses, and
  ruff bans nine more parser entry points (`xml.etree.ElementTree.XML`,
  `XMLPullParser`, `fromstringlist`, `ElementInclude`, `expat`, `pyexpat`,
  `xmltodict`, `pandas.read_xml`, `defusedxml.lxml`).

- **All XML is parsed with defusedxml.** The arXiv and PubMed sources, figure
  extraction, the JATS normalizer, local-file and bioRxiv-manifest parsing and
  the benchmark metrics called the standard-library parser directly. They now
  use defusedxml, as full-text and search-result parsing already did, so a
  document that declares entities is refused instead of expanded. The arXiv,
  PubMed and figure paths treat it like any other unparseable response. Ruff now
  reports any other XML parser (rules S313-S319, and a ban on importing lxml).

- **A manual release run can no longer publish to pypi.org from a branch.** The
  `environment` input of `release.yml` defaulted to `pypi` and nothing tied
  publishing to a tag, so `gh workflow run release.yml --ref <branch>` uploaded
  a branch snapshot to the real index and burned that version number for good.
  The default is now `testpypi`; asking for `pypi` outside a `v*` tag fails in
  the first step of `verify`, and `publish` checks the target again immediately
  before the upload.

### 🐛 Bug Fixes

- **`FigureExtractor` finds the figures.** It searched for elements in the
  JATS1 XML namespace, which Europe PMC documents do not use, so it returned
  nothing for every article: 0 of 25 figures, 8 tables and 19 supplementary
  files across five papers. It now strips the document's own default namespace
  the way `FullTextXMLParser` does, so both the DTD-based JATS Europe PMC serves
  and schema-based JATS are matched, and it keeps the contract for a document
  defusedxml refuses: that still raises `ParsingError`. The MCP tool `paper_figures`, which reported
  `figure_count: 0` for every paper, reports them too, with a `counts_by_type`
  breakdown and `include_tables`/`include_supplements` arguments.

- **Asset URLs point at files that exist.** Figure and asset URLs were built by
  appending the file name to a PMC article page address - and, in
  `FigureExtractor`, by prefixing a PMCID with `PMC` a second time, giving
  `PMCPMC11687933`. Neither form resolved. Both now use the Europe PMC file
  endpoint that the article pages themselves load,
  `https://europepmc.org/api/fulltextRepo?pmcId=…&type=FILE&fileName=…&mimeType=…`,
  including the `.jpg` that publishers such as Springer Nature and Oxford
  University Press leave off a `<graphic>` reference. An identifier that is not
  a PMCID now leaves the file name alone rather than building a URL that 404s.

- **A figure's image is its own.** `extract_figures()`, the structured figure
  blocks and `ImageFetcher` took the first `<graphic>` anywhere inside a
  `<fig>`. That is an inline formula's image when the caption contains
  mathematics - PMC10775981's Fig 3 resolved to `pcbi.1011761.e012.jpg` - and a
  figure supplement's image when eLife nests one inside its parent. Only a
  graphic the figure carries directly, or in an `<alternatives>` of its own,
  counts now.

- **Figure supplements are linked to their parent.** A `<fig>` nested in
  another was listed as an unrelated figure. `extract_figures()` and
  `FigureInfo` now carry `parent_id` and `parent_label` for one, and its asset
  carries its own label instead of its parent's.

- **`extract_asset_refs()` reports each file once.** Every graphic inside a
  figure was added a second time without a label by the pass over "standalone"
  graphics (its `_is_inside_fig` check could never succeed, since ElementTree
  has no parent axis), graphics in `<alternatives>` again, and each `<media>`
  inside supplementary material twice: 139 references for 73 files across five
  papers, 56 of 101 figure references unlabelled. There is now one `AssetRef`
  per file-bearing element, in document order, typed and labelled by the block
  that owns it, and a file two blocks declare is returned once. Supplementary
  assets carry a MIME type, formula images are typed `FORMULA` rather than
  counted as figures, and a table deposited as an image is typed `TABLE`.

- **A display formula inside a paragraph gets a block of its own.** JATS allows
  a `<disp-formula>` inside a `<p>`, and PLOS always writes one that way.
  `get_full_text_sections_structured()` flattened it into the sentence that
  introduced it: PMC10775981 has eleven display formulas and produced no formula
  block at all, only paragraphs reading "models of the form y˙=F(y(t),θ,t,…), (1)
  with N-dimensional state-vector y". The paragraph is now split around the
  formula, as it already was around a table or figure. `to_plaintext()`,
  `to_markdown()` and `get_full_text_sections()` render the formula on a line of
  its own, after the section's paragraphs.

- **A formula block carries LaTeX in `tex`, not the flattened text.** `tex` held
  whatever `get_text_content()` made of the MathML - "y˙=F(y(t),θ,t,…)" - which
  compiles as nothing. It now holds LaTeX converted from the MathML, or the
  document's own `<tex-math>` where it ships one. The plain text moved to `text`,
  so a consumer that only reads text still gets the equation, and the equation
  number stays in `label` instead of being run into the expression. The
  publisher's rendered image, where there is one, is kept in `uri`.

- **`MathMLConverter` reads namespaced MathML.** `_handle_mtable` looked for rows
  with `findall("mtr")`, which matches nothing once the document declares the
  MathML namespace - which every Europe PMC document does. Every `<mtable>`
  converted to the empty string, and with it every PLOS display formula, since
  they all wrap their content in a one-row table. Rows are found by local name
  now, and a one-cell table unwraps instead of becoming a 1x1 `array`. Array rows
  are separated by `\\`, not by a newline, which is not a row separator in LaTeX.

- **`MathMLConverter` writes accents, scripts and symbols correctly.** An
  `<mover>` over a combining mark is an accent, so `η̄` is `\bar{\eta}` rather than
  `{\eta}^{¯}`, and `ẋ` is `\dot{x}`; `<munder>`/`<mover>` on anything else are
  `\underset`/`\overset`, not subscripts; limits on a big operator stay
  `\sum_{j=1}^{N}`. Greek letters and mathematical symbols become LaTeX commands
  instead of Unicode characters, `mathvariant` is kept (`\mathbf{y}`, not
  `\text{y}`), an author's `<annotation encoding="application/x-tex">` wins over
  anything derived, `<mfenced>` and `<mspace>` are handled, and a base is braced
  only where the script would otherwise mis-bind. Spacing follows the operator:
  `x + y`, but `(x)` and `\theta,`. Fences go through a delimiter table, so
  `<mfenced open="{">` is `\left\{`, not the error `\left{`; styled letters
  such as `ℝ` or a mathematical bold `x` become `\mathbb{R}` and `\mathbf{x}`;
  LaTeX's special characters are escaped; and an explicit space at the end of a
  group no longer turns into a backslash that escapes the closing brace.
  Measured with pdflatex on 1,654 formulas from 32 open-access papers, 711
  compiled and 275 were empty before; 1,650 compile now. The other four use a
  character outside mathematics, such as a Latin "ꝏ" for infinity.

- **`extract_tables()` finds header rows whose cells are `<td>`.** Header
  labels were read from `<th>` cells only, so a `<thead>` tagged with `<td>` -
  as many journals do - gave `headers == []`: all five tables of PMC1764484,
  both of PMC3359999. Every header row is read now, not only the first, and
  `headers` has one label per column, combined top to bottom
  ("Inputparameter 1 / A: Composition / wt.%"). The rows themselves are in the
  new `header_rows`. A `<th>` in a body row, which was dropped, is kept.

- **Tables are laid out with their `colspan` and `rowspan`.** Cells were read
  in document order with both attributes ignored, so every cell after a
  spanning one moved into the wrong column. In PMC12311175's Table 4 a drug's
  name and mechanism span every row of its trials, and 110 of the 120 body rows
  came back two cells short, their values under the wrong headers. Every row of
  `extract_tables()` and of the structured `table` block is now as wide as the
  table, with a spanning cell's text at its top-left position and `""` at the
  others; `spans` records which cells span.

- **The structured `table` block records its footer and its header rows.**
  `metadata["footer"]` holds the `<table-wrap-foot>` text and
  `metadata["header_rows"]` how many of `rows` are header rows; neither was
  recorded. A cell holding only an image - PMC5393345 draws six compound
  structures that way - reads `[graphic: <file>]` instead of `""`, in both
  outputs, and `cell_graphics` lists every image in a cell.

- **A table block's inline positions index its `text`.** They were positions
  within each cell, stored against the text of the whole table: 207 of 207 in
  PMC1764484 pointed at the wrong characters. `metadata["cell_inlines"]` now
  names the cell each entry belongs to (`{row, column, inlines}`); it was a
  list of lists that skipped cells without inlines, so no entry could be traced
  back to its cell.

- **`to_markdown()` escapes the text it takes from the document.** Nothing was
  escaped, so `DRB1*0402 ... DQB1*0503` opened an emphasis running to the next
  asterisk and a literal `<node>` was passed through as an HTML tag: rendered
  with a CommonMark implementation, 49 of PMC1764484's 127 body sentences came
  out as something other than the article's text. Every character that changes
  how Markdown renders text is now backslash-escaped; code listings are not.

- **The flat renderings carry every block of a section, in document order.**
  `to_plaintext()`, `to_markdown()` and `get_full_text_sections()` collected a
  section's `<p>` elements and little else, so anything that is not a
  paragraph reached them only through a `<p>` nested inside it. A figure placed
  directly in a section lost its label and caption title; a table lost its
  label, and in `to_markdown()` and `get_full_text_sections()` every cell not
  wrapped in a `<p>` - 225 of PMC1764484's 247 distinct cells; all 14 of
  PMC10775981's code listings and every definition list were missing from all
  three; and `to_plaintext()` rendered an appendix that is a table as its title
  alone - 228 of the 248 cells in PMC11687933's appendix table. `to_plaintext()`
  also emitted a section's paragraphs, then its lists, then its tables. All
  three now walk a section once, in order, and render each element exactly
  once: tables with their label and laid out with their spans (a pipe table in
  Markdown), figures and supplementary items with label and caption, code
  listings with their line breaks (fenced in Markdown), lists with markers.

- **A structured `code` block keeps its line breaks.** The listing was
  collapsed to single spaces like prose, running each of PMC10775981's listings
  onto one line.

- **Figures and tables in `<floats-group>` reach every output.** NIH author
  manuscripts keep every figure and table in `<floats-group>`, a sibling of
  `<body>`, and every output but `extract_figures()` and `extract_tables()`
  walked only the body: PMC5393345's figure and table were missing from the
  structured sections, `to_plaintext()`, `to_markdown()` and
  `get_full_text_sections()`. They are now gathered in a section titled
  `Figures and Tables`, after the body and before the back matter. In the
  structured output its `section_type` is `"body"`, since a figure is body
  content wherever the XML keeps it; in `get_full_text_sections()` the entry has
  no `type`. A `<sub-article>`'s floats are not the article's and are left out.

- **References are given once, with their label once and correct offsets.**
  PMC1764484 keeps its reference list inside a `<sec>` of the body, and the
  structured sections gave it twice: flattened into one unknown block in that
  section, and again as References. A labelled reference repeated its label
  ("1. 1.Rowlett"), a `<citation-alternatives>` gave the element citation and
  the mixed citation one after the other, the fields of an element citation ran
  together ("RowlettVWImpact"), and the prefixed label moved the text without
  its inlines: all 134 reference inlines of PMC11671585 pointed at the wrong
  characters, and all 1,278 of PMC12311175. PMC12738713 also keeps its
  reference list in the body and got it twice. Each reference
  is now one block - label, then the mixed citation where there is one - with
  `target_id` set to the `<ref>`'s `id`, and the reference list is left out of
  the body section that holds it. A sub-article's references are no longer the
  article's. A footnote no longer repeats its label either.

- **An inline element that ends or starts with a space keeps it.** The text of
  `<sup>`, `<italic>`, `<xref>` and the rest was taken stripped in the
  structured blocks, so `R<sup>2 </sup>= 0.90` read "R2= 0.90" - 51 words ran
  together that way in PMC1764484 - while `get_full_text_sections()` read it
  correctly.

- **List and definition-list inlines say which item they index.** Their
  positions were relative to an item with nothing to say which, and a
  cross-reference in a list lost its `ref_type` and `target_id`. Each inline now
  carries `metadata["item"]` (or `"term"`/`"definition"`), and
  `metadata["item_inlines"]` names its item.

- **`extract_peer_reviews()` keeps the whole review.** It skipped PLOS's
  `aggregated-review-documents`, which hold each round's decision letter and
  reviews; read titles only from an `<article-meta>` that `<front-stub>` lacks,
  so every PLOS and eLife review was untitled; took top-level sections without
  their subsections; and, for a review without sections - every review of those
  publishers - kept the bare paragraphs and nothing else, losing the reviewer
  comments an eLife author response quotes. Measured by sentence, PMC10775981
  kept 10 of 160, PMC11687933 100 of 148 and PMC13567752 312 of 368; all are
  kept now. Review sections have `section_type` `"peer_review"`.

- **Content outside any section keeps its document order.** The structured
  sections put every bare `<p>` of a body first and every other block after
  them, and dropped a `<supplementary-material>` placed there.

- **`StructuredSection.to_chunks()` gives chunks their section path, type and
  order.** A chunk's `section_path` held the section title; the pieces of a
  block split for length had an empty `section_type` and were emitted before
  the text gathered ahead of them; and the overlap was compared, in tokens,
  with a limit in characters, so it repeated four times as much as asked. A
  sentence longer than a chunk is now split at spaces rather than left whole.

- **A formula block's `mathml` is serialized in the MathML namespace.**
  `ET.tostring` invents a prefix for a namespace it was not told about, so the
  MathML came back as `<ns0:math xmlns:ns0="...">`. It now reads
  `<math xmlns="http://www.w3.org/1998/Math/MathML">`, the form a renderer
  expects.

- **Parse errors say what went wrong.** `PARSE003` no longer stands in for a
  refused document, a recursion error or `bytes` input; each message names the
  cause, and extraction failures carry the underlying error.

- **`compute_all_metrics()` parses the document once**, not five times, which
  takes about a third off its runtime.

- **A table or figure inside a paragraph gets a block of its own.** JATS
  allows a `<table-wrap>` or `<fig>` inside a `<p>`, and
  `get_full_text_sections_structured()` folded it into the paragraph block:
  no table or figure block, so the rows and caption were out of reach, and the
  cells ran together with nothing between them. PMC12311175 nests seven tables
  and nine figures that way; its structured output had no table or figure
  block at all, and 703 cell boundaries ran together. The paragraph is now split
  around the element: the text before it, a table or figure block with label,
  caption and rows, then the text after.

- **Article metadata is read from the article's own front matter.** Every field
  in `<article-meta>` has a namesake elsewhere in the document, and the lookups
  searched all of them. `extract_metadata()["pages"]` took the page range of the
  first reference whenever the article itself is paginated with
  `<elocation-id>` — 4 of 5 measured articles, PMC11671585 reporting "1-22" for
  elocation-id 354 — and `volume`, `issue` and the journal title had the same
  fallback. A `<related-article>` beside them describes a different paper;
  PMC13567752 reported its companion's pages. `elocation_id` is now extracted
  and is a new key of `extract_metadata()`.

- **`extract_affiliations()` returns the authors' affiliations.** It returned
  every `<aff>` in the document: PMC11687933 has 8 and came back with 33 — the
  2 editor affiliations and the 23 belonging to the peer-review `<sub-article>`
  elements. An affiliation's `text` also ran the `<label>` marker and each
  `<institution-id>` (a ROR URL, a GRID code, an ISNI) into the institution
  name, which affected 18 of the 19 affiliations across the test corpus.

- **`extract_keywords()` returns the article's own keywords.** A peer-review
  `<sub-article>` tags keywords too, so PMC11687933's author keywords ended
  with eLife's assessment vocabulary, "Compelling" and "Important".

- **`extract_article_categories()` reports `article_type`.** It looked for
  `.//article`, which never matches, because the root element *is* the
  `<article>` and ElementTree's descendant search does not include it.

- **`extract_funding()` keeps every award ID of an award group** in a new
  `award_ids` list; only the first survived. PMC11671585 has a group naming
  four grants. `award_id` still holds the first.

- **`self_uri` is not an earlier version of the article.** eLife lists the
  preprint and each reviewed preprint before the version of record, so
  PMC11687933 reported the bioRxiv DOI of its preprint.

- **`to_plaintext()` keeps the cells of such a table apart again**, as 2.0.0
  did. 2.2 built a paragraph's text with a walker of its own that put nothing
  around block-level elements, where `get_text_content()` puts a space, so
  the same 703 boundaries ran together ("miRNARole") and a figure's label ran
  into its caption ("Fig. 1Mechanisms of immune"). Both now use the one walker.

- **`JATSNormalizer` parses documents that escape `<` and `&`.** Numeric
  character references were decoded before parsing, so `&#x0003c;` became a raw
  `<` and `&#x00026;` a raw `&`, and `normalize_xml()` raised `ParseError` on
  PMC3258128 and PMC12311175. Only named entities are resolved beforehand now.
  `bytes` input is decoded the way its byte order mark or XML declaration says,
  not always as UTF-8.

- **`JATSNormalizer` metadata is the article's own.** The DOI came from the last
  `<article-id>` in the document - for PMC10775981 that of a peer-review report,
  `10.1371/journal.pcbi.1011761.r004` - and every `<sub-article>` contributor
  was an author: 45 for PMC11687933's 22. Authorship declared on the
  `<contrib-group>` gave no authors at all.

- **`JATSNormalizer` sections are in document order**, each followed by its own
  subsections; they were in neither that order nor its reverse.
  `strip_display_markup` and `flatten_xrefs` now act independently, so the
  CLI's `--no-markup` keeps display markup, and an `<xref>` inside `<bold>` is
  kept when only markup is stripped. `drop_mathml` keeps each formula's text
  in its place instead of losing it and the text that followed.

- **`pyeuropepmc normalize` prints document text as it is.** `text`, `bioc` and
  the `sections` table went through Rich markup, so a `[/i]` in an article
  stopped the command and `[a]` disappeared. `normalize batch` exits with
  status 1 when any file fails, and every command reads files in the encoding
  their XML declaration names.

- **A caption's title no longer runs into its text** in the figure and table
  blocks built from it ("Overview of the study.a The workflow"). Eight
  figure captions in PMC12738713 joined that way.

- **PubMed EFetch records have their DOI, their own PMCID and full text.**
  `PubMedClient.get_paper(pmid, use_efetch=True)` looked for the DOI inside
  `<MedlineCitation>`, but EFetch puts a record's identifiers in
  `<PubmedData><ArticleIdList>`, so the DOI was `None` for 5 of 5 measured
  records; it now falls back to `<ELocationID EIdType="doi">` too. The PMCID
  search covered the `<ArticleIdList>` of every cited reference as well, so a
  record without a PMCID of its own reported a reference's (PMID 33093664).
  Abstract sections and titles stopped at their first inline `<i>`, `<b>`,
  `<sup>` or `<sub>`, and each author's ORCID and affiliations were dropped.

- **The article title and abstract are labelled `section_type="front"`**, not
  `"body"`, so keeping only body sections no longer returns them a second time
  alongside the metadata. `front` is added to `SectionType` in the LinkML
  schema. Code that relied on the old label needs to accept `front`.

- **The disk cache keeps its entries.** Opening a `CacheBackend` with
  `enable_l2=True` on a directory that already held a `cache.db` deleted it
  first, with its `-wal`, `-shm` and `-journal` files. Nothing survived a
  restart, two clients open on one `cache_dir` could not see each other's
  entries, two `SearchClient(enable_l2=True)` instances sent two HTTP requests
  for the same query, and the `.val` files diskcache writes for large values
  were left behind unreferenced. An existing database is now reused, and
  `_validate_diskcache_schema()` — written for this and never called — migrates
  an older one in place. A database that genuinely cannot be opened or migrated
  is still discarded, now together with its sidecar and orphaned `.val` files,
  and the reason is logged.

- **The in-memory layer honours per-entry expiry.** L1 was a
  `TTLCache(ttl=config.ttl)`, one lifetime for every entry, so
  `set(expire=...)`, `data_type` and `ttl_by_type` only reached the disk layer
  and a value could be served from memory long after it had expired on disk. L1
  is now a `TLRUCache` that asks for each entry's own expiry, and an L2 hit
  copied into L1 keeps the lifetime it has left instead of getting a fresh
  full TTL.

- **`invalidate_search_cache()` and `invalidate_annotations_cache()` remove
  something.** Their defaults were `"search:*"` and `"annotations:*"`, while the
  keys these clients write start with the data type
  (`general:v1:search:6950a79a94574e15`), so calling either without a pattern
  removed nothing and reported `0`. The defaults are now `"*:search*"` and
  `"*:annotations_*"`.

- **`invalidate_fulltext_cache(pmcid)` no longer removes other articles.** The
  pattern `*:{digits}*` also matched every longer ID with the same prefix, so
  clearing `PMC123` cleared `PMC1234` too. It is anchored at the end of the key.

- **`invalidate_older_than()` works.** It returned `0` without looking at
  anything. It now deletes entries this backend stored before the given age
  from both layers and returns how many; entries another process wrote are
  left to their TTL, which the docstring says.

- **`get_keys()` and `compact()` cover the disk layer**, not just memory:
  `get_keys()` lists L2-only keys too, and `compact()` runs `expire()` and
  `cull()` on L2.

- **One lookup counts as one hit or miss.** With L2 enabled, a lookup that
  missed both layers was counted twice in `get_stats()["misses"]`, halving the
  reported hit rate. The per-layer counters still record what each layer was
  asked.

- **`CacheConfig` reports a bad value as a configuration error.**
  `CacheConfig(ttl=None)` raised `TypeError` from a comparison; a non-integer
  `ttl`, `size_limit_mb`, `l2_size_limit_mb` or `namespace_version` now raises
  `ConfigurationError`, as a negative value already did. `l2_size_limit_mb` is
  validated too.

- **`CacheConfig(eviction_policy=...)` is used.** It was stored and ignored,
  and the disk layer always evicted least-recently-used entries. It is passed
  to diskcache, and a value outside `CacheConfig.EVICTION_POLICIES` raises
  `ConfigurationError` instead of being silently dropped.

- **`from pyeuropepmc.cache import CacheConfig` works.** `src/pyeuropepmc/cache/`
  had no `__init__.py`, so only `pyeuropepmc.cache.cache` could be imported.

- **Artifact IDs that sanitize to the same filename keep separate entries.**
  `ArtifactStore` mapped `:` and `/` to `_`, so `"a:b"` and `"a_b"` shared one
  index file and the second store overwrote the first. Index filenames now carry
  a digest of the ID, and each file records the ID it was written for, which is
  what garbage collection reads instead of guessing it back from the filename.

- **`ArtifactStore(min_free_space_mb=...)` is enforced.** It was stored and
  never checked: a store under its size limit would fill the disk. Storing
  content that would leave less free space than the floor now collects first.

- **`prisma_summary()` adds up repeated searches.** `records_by_database` kept
  only the last `results_returned` per database name, so a review that logged
  1234 and 200 records for Europe PMC and 50 for PubMed reported 250 identified
  records instead of 1484 — the number that goes into a PRISMA flow diagram.

- **`sign_file()` signatures verify.** It hashed the file and passed the digest
  to `sign(..., hashes.SHA256())`, which hashes again, so the signature was over
  the digest of a digest and `openssl dgst -sha256 -verify` reported
  `Verification failure` on the file it was meant to authenticate. It signs the
  file contents.

- **`generate_private_key(publish_public=True)` writes a loadable public key.**
  The metadata comment went *inside* the `BEGIN PUBLIC KEY` block, so the base64
  body would not decode and `load_pem_public_key()` raised `ValueError`. The
  comment now precedes the block, as it already did for the private key.

- **`record_platform()`, `record_export()` and a CSV export handle an empty
  log.** All three raised `IndexError` from indexing an empty list. The two
  record functions raise `ValueError` naming `record_query()`, and exporting a
  log with no entries writes a header-only CSV.

- **Schema coverage counts every pattern group.** `validate_schema_coverage()`
  consulted eleven of the seventeen groups in `ElementPatterns`, so elements the
  parser does handle — `award-id`, `subject`, `permissions`, `tex-math`, MathML
  and more — were reported as unrecognized. Coverage of
  `tests/fixtures/fulltext_downloads/PMC3258128.xml` goes from 77.8% to 86.1%.
  A pattern written with a namespace prefix (`.//mml:math`) now contributes the
  local name, which is what the document tags are compared as.

- **The MCP Registry entry starts the server, not the command-line tool.**
  `server.json` asked clients to run `uvx pyeuropepmc`, which starts the
  `pyeuropepmc` CLI - the console script named after the distribution - and
  prints its help instead of speaking MCP. The entry now passes the `mcp`
  subcommand.

- **`RDFMapper()` and `PaperProcessingPipeline` work after `pip install`.** The
  mapping files sat in a `conf/` directory at the repository root and were
  found by walking up from `__file__`, which only a source checkout has: an
  installed package looked in the interpreter's `lib/` directory and raised
  `FileNotFoundError`, and `load_rdf_config()` quietly used its built-in
  fallback, with `http://example.org/data/` as base URI instead of
  `https://w3id.org/pyeuropepmc/`. The four files now ship inside the package
  (`pyeuropepmc.conf.config_file(name)` returns a path), and `RMLRDFizer()`
  finds its defaults there too.

- **PyYAML is a declared dependency.** `pyeuropepmc.mappers` imports it at
  module level, but it only ever arrived with the `standard` or `agentic`
  extra: in a bare install `from pyeuropepmc.mappers import RDFMapper` raised
  `ModuleNotFoundError: No module named 'yaml'`.

- **MCP tools ask for the extra they need.** The availability flags recorded
  whether a pyeuropepmc module imported, which it always does, because optional
  libraries load lazily. The LLM tools now check LangChain, so without the
  `agentic` extra they return an install hint instead of empty analyses; the
  `bib_*` tools check bibtexparser; the `ref_*` tools, which need no extra, no
  longer name `bibliography`; and tools that are part of the core install no
  longer suggest `pip install pyeuropepmc[all]`.

### ⬆️ Dependencies

- **rapidfuzz 3 is allowed** (`>=2.15.0,<4.0`). The old bound resolved to
  2.15.2, which has no wheels for Python 3.13 or later, so installing there
  needed a compiler. Match scores do not change: `token_fuzzy_score()` now
  passes rapidfuzz 2's default processor explicitly, and its scores are
  identical on 5,064 pairs built from titles in the test fixtures (641 differ
  without it).

- **New `benchmark` extra** with `huggingface-hub`, which downloading the
  published benchmark datasets needs; a failed download now names the extra.

- **The `rdf` extra installs nothing.** rdflib, a core dependency, writes
  JSON-LD itself since 6.0, which made rdflib-jsonld redundant. The extra is
  kept so existing install commands keep working.

- **The `enrichment` extra no longer installs cryptography**, which no
  enrichment module imports. Signed search logs need the `signing` extra, as
  before.

### ✨ Features

- **`pyeuropepmc mcp` runs the MCP server**, the same server as the
  `pyeuropepmc-mcp` command. A client that starts the package with
  `uvx pyeuropepmc` gets the console script named after the distribution, and
  had no way to ask for the other one.

### 🔧 Maintenance

- **`twine check --strict` runs on the wheel and the sdist before publishing**,
  with `readme_renderer[md]` installed, so a `README.md` that PyPI cannot render
  fails the build instead of the upload.

- **Contributor tooling matches the repository.** `make codescene`,
  `make codescene-delta` and `make quality-full` call
  `examples/scripts/codescene_analysis.sh` where the script is. CI, `make
  quality` and the pre-commit hook read one bandit configuration from
  `pyproject.toml`; the hook used to skip two checks that CI ran. `tox.ini`
  installs the package with every extra and the `dev` dependency group instead
  of a stale hand-written list, and gains the `--run-integration` flag its
  integration environment needed. A test hook that skipped by marker names no
  test uses is removed, and stale comments and the Copilot instructions are
  brought up to date.

- **Reference authors are read in every JATS dialect.** PLOS lists a
  `<mixed-citation>`'s contributors as bare `<name>` children, which were not
  read, and the text pass that took over ran surname and initials together:
  `"NewtonSI"` in all 53 references of PMC10775981. They now read
  `"Newton, SI"`, and a chapter's editors, written after its title, are left
  out. A `<collab>` or `<string-name>` among the authors is kept in place; the
  4 collaboration authors of PMC11687933 were dropped.

- **The citation text no longer overwrites tagged reference fields.** The pass
  over a `<mixed-citation>`'s flattened text assigned volume, pages, DOI and
  PMID even when the tagged elements had given them: `"385-430"` became `"385"`,
  and a DOI followed by its PMID was read as `"10.1098/rstb.2001.091011545699"`
  (4 references in PMC10775981). It now only fills fields that are empty.

- **Identifiers in `<ext-link xlink:href>` are read.** BMC and Springer tag a
  text-only citation's DOI, PMID and PMCID as empty `<ext-link>` elements with
  the value in the link target, so every PMID was lost: 0 of 45 in PMC1764484.
  A page range written with an en dash, "48:662–667", also lost its last page
  in 43 references there.

- **Software and dataset references are titled by their `<data-title>`**, not
  by the repository in `<source>`: eLife's software citations were titled
  "GitHub", "CRAN" and "Sourceforge". A book chapter's `<chapter-title>` or
  `<part-title>` likewise comes before the book's title.

### 📚 Documentation

- **The caching, search logging, systematic review tracking and schema coverage
  pages drop the limitations above** and describe the fixed behaviour, with the
  documented element counts and coverage percentages recomputed.

- **The documentation matches the code again.** Audits of README.md and every
  page in docs/ found that most examples raised or used classes, methods,
  parameters and commands that do not exist. Each page was checked against the
  code and rewritten, merged or removed, and every Python example on the
  rewritten pages runs offline against mocked HTTP. README.md is a shorter front
  page whose links work on PyPI; docs/SUMMARY.md lists every page; new pages
  cover error codes, how the docs are published and the XML parser internals;
  `.gitbook.yaml` lets GitBook Git Sync publish docs/. Code defects found on the
  way are documented as known limitations where readers would hit them.

- **Error messages link to the error reference that exists.** The `Docs:` line
  of the HTTP error messages, and of any message built with
  `get_error_message(code, include_help_link=True)`, pointed at
  `pyeuropepmc.rtfd.io/errors/<CODE>`, which never existed. It now links to the
  section of the published error-codes page that lists the code, and a test
  checks that every code is listed in the section its link names.

## [2.2.1] - 2026-09-15

Packaging metadata only; no change to the installed package's runtime
behaviour.

### 🐛 Bug Fixes

- **The MCP Registry listing now publishes.** 2.2.0's
  `publish-mcp-registry` job got past login, so 2.1.2's namespace-casing
  fix held, but the registry rejected the publish with a 400. It confirms
  that a PyPI package belongs to a server by finding
  `mcp-name: io.github.JonasHeinickeBio/pyeuropepmc` in the package README,
  and `README.md` named the server only in prose. The README now carries
  that line as an HTML comment, invisible on GitHub and PyPI. PyPI does not
  allow a released version's README to change, so this needs a new version
  rather than a re-run of 2.2.0's job.

## [2.2.0] - 2026-09-15

Full-text parsing correctness. Fifteen defects, every one found by measuring
the parser's output against 124 real Europe PMC documents rather than by
reading code — several were invisible to hand-written fixtures because they
only occur in markup nobody writes by hand.

None of these raised an exception. They returned plausible, wrong answers.

This is a minor release rather than a patch: those fixes change what
several extraction methods return, and the minimum versions of three runtime
dependencies move (see Dependencies below). 2.1.2 was prepared but never
published, so its release-pipeline fix ships here too.

### 🐛 Bug Fixes — wrong data returned

- **References attributed the wrong text to title and journal.** A
  `<mixed-citation>` may carry the same structured children as an
  `<element-citation>`, or be a run of plain text. The parser ran a regex
  over the flattened text *first* and consulted the structure afterwards
  "for any missing fields" — but the regex fills `title` and `source` on
  almost any input, so the correct values were computed and discarded. One
  reference came back as `authors="Albritton E"`, `title="Hernández-Cancio S"`,
  `source="Lutz W"` — the second and third authors, in the title and journal
  fields. Complete author lists went from **11% to 100%** (16 → 149 of 149);
  exact titles from 80% to 98% (535 → 653 of 665). Anything building citation
  graphs on `extract_references()` was silently corrupt. (#226)

- **Peer reviewers and editors were returned as article authors.** The search
  covered the whole document, so the `<contrib>` inside every peer-review
  `<sub-article>` came back as an author — PMC13567752 has nine and returned
  fourteen, the reviewer once per report. Separately, with no
  `contrib-type="author"` anywhere the patterns fell through to a bare
  `.//name`, which also matches a `<contrib-group content-type="editor">`;
  that added a spurious author to 13 of 124 documents. Author surnames
  matching the article's own front matter: **82.3% → 100%**. (#227)

- **Peer-review bodies were returned as article sections.** `.//body` also
  matches the `<body>` of every `<sub-article>`, and every match was
  iterated: PMC13567752 has a 39,374-character body and returned 94,895
  characters of "sections". 9 of 124 documents were affected, 377,847
  characters of reviewer text between them. (#222)

- **`AUTH-01` reported missing authors for the majority JATS dialect.**
  Only `<contrib contrib-type="author">` was recognised, not
  `<contrib-group content-type="author">` — which was the commoner of the two
  in a 1,000-file sample. 550 of the rule's 553 fires were false, and those
  documents never reached `AUTH-02` either. (#218, issue #203)

- **Publication dates were missed for 57% of documents.** Only
  `pub-type` `ppub`/`epub`/`collection` were matched. The untyped
  `<pub-date>` was the single most common spelling, and JATS 1.1 uses
  `date-type`; 566 of 997 papers carrying a usable `<year>` returned `None`.
  Candidates are now ranked rather than filtered. A day is also only emitted
  with a month — previously a year-and-day date produced the malformed
  `"2022-14"`. (#219, issue #210)

- **Funding sources were dropped when the funder was direct text.** Only
  `<funding-source>//institution` was read, so a group naming its funder
  directly — and having no award ID or recipient — produced an empty
  dictionary and disappeared entirely. (#219, issue #210)

- **Licence URLs and text were missed.** The URL was taken only from
  `<ext-link>`, never from `<ali:license_ref>`, which is the canonical
  machine-readable form and often the only one present. `<license-p>` was
  read without full-text extraction, so a paragraph opening with an inline
  element (`<bold>Open Access</bold>This article…`) yielded only the
  whitespace before it. Licence URLs 83 → 100 of 124; licence text 96 → 124.
  (#224)

### 🐛 Bug Fixes — text lost or duplicated

- **Nested section text was emitted twice.** JATS sections nest, and the flat
  extractors selected descendant content with `.//`: a parent carried its
  subsections' paragraphs and each subsection emitted them again. Measured on
  Europe PMC samples this repeated 43% of `get_full_text_sections()`, 40% of
  `to_plaintext()` and 60% of `to_markdown()`. (#220, issue #209)

- **Paragraphs outside a `<sec>` were discarded.** `to_plaintext()` handled
  bare `<p>` under `<body>` only when the document had *no* `<sec>` at all, so
  articles with opening paragraphs *and* sections lost them; `to_markdown()`
  never handled them. A `<p>` inside a `<boxed-text>` under `<body>` was
  missed by both. (#221, #222)

- **List and table content was both lost and duplicated.**
  `_process_list_plaintext` rendered only the first `<p>` of each item and
  matched nested items twice. Table `<caption>` and `<table-wrap-foot>` — the
  abbreviation keys — were never rendered as table content, because the
  renderer was handed the inner `<table>` rather than its wrapper. (#222,
  #223)

- **The structured blocks API dropped figure and supplement text.** A `<fig>`
  was rendered from label, caption and graphic alone, discarding a
  `<disp-quote>` describing it; `<supplementary-material>` was traversed with
  `findall("caption")`, direct children only, while the caption usually sits
  under a nested `<media>`. A `<p>` sitting outside the caption was dropped
  too, because the no-caption fallback only fires when the element yields
  nothing at all — an item carrying both kept the caption and lost the
  paragraph. Body sentences absent from
  `get_full_text_sections_structured()`: **48 → 0**. (#229, #232)

- **The three renderings disagreed about back matter.**
  `get_full_text_sections()` returned `<author-notes>` but not `<ack>`;
  `to_plaintext()` did the reverse; `to_markdown()` returned neither, nor
  appendices, nor the glossary. All three now cover the same set.

### 🐛 Bug Fixes — input handling

- **XML comments leaked into extracted text on the lxml backend.** lxml keeps
  comments in the tree as children whose tag is a callable rather than a
  string; the text walkers descended into them and appended their content.
  stdlib ElementTree discards comments at parse time, so the two backends
  disagreed about the same document: `PMC3258128` opens its `<license-p>` with
  `<!--CREATIVE COMMONS-->`, and only the lxml backend returned that as part of
  the licence text. Comments and processing instructions are now skipped while
  their tails — which are real content — are kept. The two backends now agree
  on metadata, references, authors and section titles exactly, and on rendered
  text once whitespace is collapsed.

- **XML text carrying an encoding declaration could not be parsed.**
  `LXMLParser.fromstring()` is documented to take XML text, but lxml rejects a
  `str` with an encoding declaration — which is how Europe PMC ships full
  text, so 57 of 100 real files failed. Encoding to UTF-8 alone is not enough:
  lxml honours the declaration over the bytes it is given, so a latin-1
  declaration silently produced `cafÃ©`. The declaration is rewritten to name
  the encoding actually passed, and `bytes` input is accepted unchanged. (#217,
  issue #204)

- **JATS in a default XML namespace extracted nothing at all.** Every search
  in the package is unprefixed, which matches the DTD-based JATS Europe PMC
  serves; a schema-based document puts the same elements in a namespace, so
  every search returned nothing — no title, no sections, empty plain text, and
  no error raised. `parse()` now strips the root's own namespace while leaving
  prefixed vocabularies (`ali:`, `xlink:`) intact. (#225)

- **Spaces were invented around inline elements.** Text extraction stripped
  every fragment and joined with a space, so `PM<sub>2.5</sub>` read as
  `PM 2.5` and a citation parenthesis as `( Kumar, 2021 ; …)` — wrong for a
  reader, and worse for tokenisation. Inline runs now keep the document's own
  spacing; block-level children are still separated. Exact article titles:
  122 → 124 of 124. (#228)

### 🐛 Bug Fixes — query builder

- **`QueryBuilder(validate=True)` always warned that search-query was
  missing.** The refactor that removed the module-level
  `SEARCH_QUERY_AVAILABLE` flag left the warning body in place but dropped
  both halves of the logic around it: the guard that made it conditional, and
  the assignment that disabled validation. So the warning fired on every
  `validate=True` construction, telling users to `pip install search-query` —
  a declared runtime dependency they already had — while a genuinely absent
  package was not handled at all, leaving `_validate` true so `build()` raised
  instead of degrading as the docstring promises. Both halves restored.

### 🐛 Bug Fixes — release pipeline

- **Fixed the MCP Registry publish job** (added in 2.1.1): `server.json`
  named the server `io.github.jonasheinickebio/pyeuropepmc`, but the
  registry's GitHub OIDC verification is case-sensitive and only grants
  permission for the exact-case GitHub login `JonasHeinickeBio` — so the
  2.1.1 release's `publish-mcp-registry` job failed with a 403
  ("You have permission to publish: `io.github.JonasHeinickeBio/*`.
  Attempting to publish: `io.github.jonasheinickebio/pyeuropepmc`").
  Corrected the casing in `server.json` and its documentation references.

### ⬆️ Dependencies

The minimum supported versions move, so an environment pinned below them
needs to upgrade these along with pyEuropePMC.

- `cachetools` `>=7.1.8,<8.0`, was `>=6.2.1,<7.0` (#186)
- `tenacity` `>=9.1.4,<10.0`, was `>=8.2.0,<9.0` (#187)
- `search-query` `>=0.15.0,<0.16`, was `>=0.13.0,<0.14` (#151). The query
  builder's calls into it (`parse(..., platform=...)`, `load_search_file`,
  `SearchFile`) work unchanged on 0.15.

### ✅ Tests

- **`tests/features/fulltext/real_data/`** asserts parser invariants against
  the real Europe PMC documents in `tests/fixtures/fulltext_downloads/`: every
  body sentence appears in each rendering at least once and no more often than
  the source has it, and extracted values match what the XML says. Run against
  the code as it stood before this work, the suite fails 26 times; against the
  current code, not at all.

- Two fixtures were added to cover shapes the existing four do not:
  `PMC13567752.xml` (nine peer-review `<sub-article>` elements) and
  `PMC12018715.xml` (23 structured `<mixed-citation>` references).

- **`test_backend_parity.py`** holds the optional lxml backend to the same
  results as the default one. Nothing checked that before, which is how the
  comment leak above went unnoticed: structured values must match exactly,
  rendered text once whitespace is collapsed.

- **`tests/features/search/real_data/`** compares parsed search results against
  the captured Europe PMC responses in `tests/fixtures`. The existing tests for
  `EuropePMCParser` are mock-based — they assert the right parse function was
  called and that a list came back, which checks the wiring rather than the
  values. That is the same gap that let `extract_references()` mis-assign
  citation fields for as long as it did, on a code path whose coverage tests
  all passed. Every field of every record is now compared, order included, and
  the JSON and XML renderings of one search must name the same articles. No
  defect was found — the parser is exact on all 25 records in all three
  formats — but nothing was holding that.

- **`tests/mappers/real_data/`** parses a real article, maps it to RDF, and
  asserts the article's own title, DOI and every author name appear in the
  triples. `process_xml_for_rdf` wraps each entity in
  `except Exception: logger.warning(...); continue`, so an entity that fails
  to map is skipped and the graph simply comes back shorter — a caller gets a
  `Dataset` either way, and only a log line distinguishes a complete graph
  from one missing half its authors. Twenty-one test modules under
  `tests/mappers` read no real document before this. No defect was found; a
  simulated dropped author is detected.

- **`test_degenerate_input.py`** covers input the parser meets in the wild but
  nobody writes on purpose: malformed and truncated XML, a billion-laughs
  bomb, an external-entity reference, a document with no `<body>`, control
  characters, 500 sibling sections, 40 levels of nesting. Unparseable input
  must raise `ParsingError` rather than an arbitrary exception; parseable
  input must return from all twenty public methods without raising; entity
  attacks must be refused rather than expanded — a plain parser in place of
  `defusedxml` would silently reintroduce both.

- **`pytest -m unit` now selects every unit test.** `tests/conftest.py`
  already inferred `functional` and `integration` from a test's path; it now
  marks any test in no other category `unit`, so the lane grew from 1,738 to
  5,492 tests without per-module markers. Seven mocked tests had never run
  in CI, because a filename rule classed `search_interactive_test.py` as
  functional; renamed `test_interactive_search.py`, they now run with the
  rest. (#240, #241)

- **The query builder's tests moved to `tests/features/literature/`**, the
  directory that mirrors its source, from a top-level `tests/query_builder/`.
  (#239)

- **`tests/` is linted and formatted with ruff** in CI and pre-commit. It had
  been excluded; bringing it in fixed 1,203 findings and reformatted 145
  files, with every collected test and its markers unchanged. Pre-commit's
  ruff is now pinned to 0.14.14, the version CI runs. (#242)

### 📊 Verified across 124 real Europe PMC documents

| Check | Before | After |
| --- | ---: | ---: |
| Article title matches `<article-title>` | 122/124 | 124/124 |
| Author surnames match front matter, in order | 102/124 | 124/124 |
| Metadata field coverage (10 fields) | `pub_date` 43% | 100% |
| Complete author list on structured citations | 16/149 | 149/149 |
| Licence URL present | 83/124 | 100/124 |
| Body sentences lost from flat renderings (of 19,964) | 10 | 0 |
| Body sentences lost from structured blocks | 48 | 0 |
| Body sentences duplicated | 154 | 43 |
| Public API sweep (124 × 20 methods) | — | 2,480 calls, 0 exceptions |

The 43 remaining duplicates are short boilerplate that documents genuinely
repeat — ethics statements, "Not applicable." — in table footnotes and figure
captions.

### 🔁 Confirmed on documents never used while fixing

Every fix above was developed against the same 124-document corpus, so the
numbers in that table are the ones a change was tuned to produce. A further
**50 documents were fetched afterwards** — different journals, different
years, none of them seen while any fix was written — and measured with the
same checks:

| Check | Held-out result |
| --- | ---: |
| Article title matches `<article-title>` | 50/50 |
| Author surnames match front matter, in order | 50/50 |
| ORCID well-formed | 17/17 |
| Affiliation count | 50/50 |
| Figure count | 48/48 |
| Body sentences genuinely lost (of 10,723) | 0 |
| Body sentences lost from structured blocks | 0 |
| Public API sweep (50 × 20 methods) | 1,000 calls, 0 exceptions |

One sentence appears absent from `to_plaintext()` and is not: the measurement
splits sentences on punctuation, and a paragraph reading `"…summarized as
following:"` followed by a `<list>` produces a "sentence" spanning both, which
cannot appear contiguously once the list is rendered separately. Its
introduction and all five list items are present.

### 📚 Documentation

- `docs/DEPENDENCY_GROUPS.md` explains how to update a dependency without
  failing CI (#236), and why the committed `poetry.lock` is not reproducible
  byte for byte (#237).

## [2.1.1] - 2026-09-14

Docs and CI only — no changes to the installed package's runtime behavior.

### ✨ Features

- **`pyeuropepmc-mcp` is now published to the official
  [MCP Registry](https://registry.modelcontextprotocol.io/)** as
  `io.github.JonasHeinickeBio/pyeuropepmc`
  ([`server.json`](server.json)). Every tagged release republishes it
  automatically via GitHub OIDC (`publish-mcp-registry` job in
  `release.yml`) — no stored secret, the workflow's own repo identity
  proves namespace ownership.

### 🐛 Bug Fixes

- **Fixed the "Python Version Compatibility Matrix" Windows jobs**, broken
  since 2.1.0: every MCP test driving async code via `asyncio.run()`
  failed on Windows with `pytest_socket.SocketBlockedError`, because
  constructing a new event loop there needs a real (loopback-only) socket
  for its internal self-pipe, which `--disable-socket` blocked outright.
  `tests/mcp/conftest.py` now scopes `pytest.mark.allow_hosts(["127.0.0.1",
  "::1"])` to just the MCP test suite.

### 🔧 Maintenance

- Refreshed the README's badges: dynamic Python-version/PyPI badges instead
  of hand-typed ones that had drifted (actual test count is 5,000+, not
  the old "200+"), and a working CodeQL badge (the old one linked to a
  workflow file that doesn't exist, since CodeQL runs via GitHub's
  default-setup code scanning here, not a committed workflow).

## [2.1.0] - 2026-09-13

> **MCP server rewrite.** `pyeuropepmc-mcp` now runs on the official
> [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
> (`FastMCP`) instead of a hand-rolled JSON-RPC/stdio loop. The Python
> library API (`pyeuropepmc.SearchClient`, etc.) is unchanged — this affects
> only the MCP server and its 24 tools.

### ✨ Features

- **Spec-compliant, concurrent MCP server.** Rebuilt on `FastMCP`: tool
  errors are reported via the standard `isError: true` `CallToolResult`
  instead of ad hoc text, every tool call offloads its blocking
  network/disk work to a thread pool (`anyio.to_thread.run_sync`) so one
  slow request no longer stalls every other in-flight call, and input is
  validated against each tool's schema before the tool body ever runs.
- **More transports, more agents.** `pyeuropepmc-mcp --transport
  streamable-http` (or `sse`) runs the server as a standalone network
  service that any MCP-capable agent can reach over HTTP — not just
  stdio-based clients like Claude Desktop. New `--host`, `--port`, and
  `--log-level` flags (also settable via `PYEUROPEPMC_MCP_*` env vars).
- **Cached, reusable clients.** `SearchClient`, `CitationWalker`,
  `ClinicalTrialsClient`, `FigureExtractor`, and the LLM analysis agent are
  now constructed once per process and reused, instead of being rebuilt on
  every call — faster, and it fixes two latent bugs where a fresh
  `CitationWalker` per call reset its own rate limiter and a fresh LLM
  agent per call never hit its own analysis cache.
- **Structured tool output.** Tools return typed Python values instead of
  pre-serialized JSON strings; the SDK derives an output schema and returns
  both `structuredContent` and a human-readable text rendering.
- **Progress notifications.** `unified_search`, `citation_snowball`,
  `paper_screening`, and `literature_review` emit `ctx.info(...)` MCP
  logging notifications mid-call, so a client that surfaces them can show
  progress during a multi-source search instead of going silent.
- **Tool annotations.** Every tool advertises `readOnlyHint`/`openWorldHint`/
  `idempotentHint` metadata so a calling agent can reason about a tool
  without executing it first.

### 💥 Breaking changes (MCP tool interface only)

- **`mcp` is now a required core dependency** (previously the server had no
  real MCP SDK dependency at all). A bare `pip install pyeuropepmc` pulls it
  in automatically.
- **`citation_snowball`'s `strategy` argument is now validated.** An invalid
  value is rejected with a schema-validation error instead of silently
  falling back to `"forward"`.
- **`get_paper_citations` gained a `limit` parameter** (default 100) and
  dropped the `source` parameter, which the previous implementation accepted
  but never used.
- **`literature_review` gained an explicit `excluded_topics` parameter**
  that the previous implementation read from `arguments` without declaring
  in its schema.

### 🧪 Testing

- Rewrote the MCP test suite: 94 hermetic unit tests exercise each tool
  function directly (mocked clients via the module's lazy-singleton caches)
  plus FastMCP-level schema/registry checks, and 4 new e2e tests drive the
  real server subprocess over stdio with the official MCP client instead of
  hand-rolled JSON-RPC framing.

### 📚 Documentation

- Rewrote [`src/pyeuropepmc/mcp/README.md`](src/pyeuropepmc/mcp/README.md)
  and the top-level MCP section of the README for the new transports, tool
  registry, and design notes.

### 🔧 Maintenance

- **Fixed `mypy` aborting entirely on Python 3.12+.** numpy 2.5.x (the
  version `poetry.lock` resolves for Python ≥3.12) ships stubs that use PEP
  695 syntax (`type X = ...`, `class Foo[T]`) throughout — reachable
  transitively via `rapidfuzz` (a core dependency) and `matplotlib`/`pandas`
  (extras), not just via this package's own numpy usage. Under the
  project's `python_version = "3.10"` mypy target this crashed the *entire*
  run ("errors prevented further checking"), so `poetry run mypy src/`
  silently checked nothing on a Python 3.12 host — including the
  `release.yml` `verify` job, which pins Python 3.12. `[tool.mypy]` now
  targets `python_version = "3.12"`; this doesn't loosen protection against
  3.10-incompatible syntax landing in `src/`, since
  `python-compatibility.yml` separately compiles every file under real
  3.10–3.13 interpreters. Bumping the target surfaced one real, previously
  hidden issue: `load_entry_point_sources()`'s pre-3.10 `importlib.metadata`
  fallback (`entry_points().get(...)`) doesn't type-check against a modern
  `EntryPoints`, and was dead code anyway given `requires-python = ">=3.10"`
  — removed.

## [2.0.0] - 2026-09-10

> **Major release.** Package internals were reorganised into a vertical-slice
> layout and most runtime dependencies became optional. The public
> `pyeuropepmc.<Name>` API (e.g. `pyeuropepmc.SearchClient`) is unchanged, but
> deep imports and a bare `pip install` behave differently — see
> [`docs/migration/v1-to-v2.md`](docs/migration/v1-to-v2.md).

### 💥 Breaking changes

- **Vertical-slice package layout.** `src/pyeuropepmc/` is now organised by
  feature. Deep import paths changed:
  | 1.x | 2.0 |
  |-----|-----|
  | `pyeuropepmc.clients.search` | `pyeuropepmc.features.literature.search` |
  | `pyeuropepmc.clients.article` / `annotations` / `ftp_downloader` | `pyeuropepmc.features.literature.*` |
  | `pyeuropepmc.clients.fulltext` | `pyeuropepmc.features.fulltext.fulltext_client` |
  | `pyeuropepmc.enrichment.*` | `pyeuropepmc.features.enrich.*` (external APIs under `features.enrich.sources.*`) |
  | `pyeuropepmc.query.*` (`query_builder`, `filters`, `pagination`) | `pyeuropepmc.features.literature.*` |
  | `pyeuropepmc.processing.fulltext_parser` / `parsers` / `converters` / `extensions` | `pyeuropepmc.features.fulltext.*` |
  | `pyeuropepmc.processing.analytics` / `visualization` | `pyeuropepmc.features.analytics.*` |
  | `pyeuropepmc.processing.annotation_parser` / `annotations_to_rdf` | `pyeuropepmc.features.literature.*` / `features.fulltext.*` |

  Top-level re-exports (`pyeuropepmc.SearchClient`, `pyeuropepmc.QueryBuilder`,
  `pyeuropepmc.PaperEnricher`, …) still work.
- **Dependencies split into optional extras.** A bare `pip install pyeuropepmc`
  now installs a light core only (~14 packages: `requests`, caching, query
  building, JATS parsing, CLI). pandas, numpy, matplotlib, seaborn, rdflib,
  flask, langchain/openai, semanticscholar, Jupyter, etc. are **no longer
  installed by default**. Use extras:
  `analytics`, `visualization`, `export`, `rdf`, `agentic`, `ui`, `signing`,
  `enrichment`, `semanticscholar`, `bibliography`, `zotero`, `standard`, `all`.
  For the previous behaviour: `pip install "pyeuropepmc[all]"`.
- **`import pyeuropepmc` is now lazy (PEP 562).** Submodules and their heavy
  dependencies load on first attribute access. Accessing a feature whose extra
  is missing raises `OptionalDependencyError` with the exact `pip install`
  command. Import time dropped from ~2.6 s to ~0.15 s.
- `uv.lock` removed — Poetry is the single supported install workflow.
- Version bumped `1.18.0 → 2.0.0`; SPDX `MIT` license expression.

### ✨ Features

- **Multi-source literature search** (`pyeuropepmc.features.search`):
  - `UnifiedSearch` federates a single query across many sources in parallel
    (`ThreadPoolExecutor`), normalises and deduplicates the combined results,
    and reports per-source timings and errors.
  - Pluggable **source registry** (`features.search.registry`): `SourceSpec`,
    `register_source()`, `available_sources(installed_only=…)`,
    `source_capabilities()`, `load_source()`, plus a `pyeuropepmc.sources`
    entry-point hook for third-party sources.
  - New source clients: PubMed (E-utilities), arXiv, ClinicalTrials.gov v2,
    DOAJ, DBLP, HAL, CORE, Zenodo — and adapters for Europe PMC, OpenAlex and
    Semantic Scholar.
  - **Query translation** (`features.search.query_translation`): rewrites one
    query into each backend's dialect (arXiv `all:"…"`, free-text for
    OpenAlex/S2, field syntax kept for Europe PMC/PubMed; uses the optional
    `search-query` parser when available).
- **Identifier-cluster deduplication** — new `LiteratureMerger` in
  `features.enrich.merger`: CORD-19-style DOI/PMID/PMCID/title-hash grouping
  with `BALANCED` / `FOCUSED` / `RELAXED` modes, author- and journal-overlap
  gates, retraction and salami-slice awareness, and a structured `MergeReport`.
  (The 1.x `DataMerger` field-level metadata merge is unchanged.)
- **Metadata enrichment sources** consolidated under
  `features.enrich.sources`: CrossRef, OpenAlex, Semantic Scholar (+ pro
  wrapper), ORCID, Unpaywall, DataCite, ROR, and **iCite** (NIH citation
  metrics — new).
- **Agentic workflows** (`pyeuropepmc.agentic`, extra `agentic`): LangChain/
  LangGraph LLM client, `SmartCitationAnalysis`, a tool registry, and a
  multi-agent claim-verification pipeline (`pyeuropepmc.claims`) with an
  optional Flask review UI (`pyeuropepmc.ui`, extra `ui`).
- **JATS normalisation** for text-mining pipelines (`JATSNormalizer`) and a
  `pyeuropepmc normalize` CLI subcommand.
- **XML parser extensions**: content blocks, MathML, peer-review, JATS4R,
  batch processing, LinkML schema, reference resolver, lxml backend.
- `EuropePMCLiteratureAdapter` makes the native Europe PMC `SearchClient` a
  first-class `UnifiedSearch` source.
- `utils/env_loader.py` for `.env` handling; `_optional_imports.py` /
  `utils/dependencies.py` for graceful optional-dependency errors.

### 🧪 Testing

- **Hermetic default test run.** `pytest-socket` blocks real network in the
  default suite (a mis-mocked test fails fast with `SocketBlockedError` instead
  of hanging), `pytest-timeout` caps each test at 120 s, and markers are
  inferred from a test's path (`functional/`, `integration/`, `benchmark`,
  `gui`) so whole directories are excluded without per-file annotation. This
  fixed the full suite hanging and being OOM-killed. Run the excluded lanes
  with `pytest -m functional` / `--run-real` / `-m benchmark` /
  `--run-integration`.
- Tests reorganised to mirror `src/` (`tests/features/…`).
- Recorded fixtures replace several live-API "unit" tests; ~3,640 tests,
  ~50 s, ~410 MB peak.

### 🔧 Maintenance

- `ruff check src/` and `mypy src/` (strict) are clean; `pytest` green
  (3602 passed). The `release.yml` / `cdci.yml` gates pass locally.
- `pyproject.toml` moved to static PEP 621 metadata; `requirements.txt` /
  `poetry.lock` regenerated from it.
- Optional-dependency group maps consolidated into a single source of truth;
  `User-Agent` now reports the real package version; `py.typed` shipped.
- `sentence-transformers` is intentionally **not** an extra — it pulls in
  `torch` + the `nvidia-cuda-*` wheels, which made `poetry lock` effectively
  non-terminating. Semantic text matching asks you to install it directly.

## [1.18.0] - 2026-07-03

### ✨ Features

- **PaperProcessingPipeline Context Manager**: Added `__enter__` and `__exit__` methods
  - Pipeline now supports `with` statement for automatic resource cleanup
  - Consistent with other enrichment clients (`PaperEnricher`, `BatchEnricher`)

### 🐛 Bug Fixes

- **Hugging Face Dataset Loading**: Fixed dataset config name and import handling
  - Changed config name from `"PMC_sample_1943"` to `"default"` in tests
  - Added try-except around `datasets` module import in `_try_huggingface_load_dataset()`
  - Graceful fallback when datasets library is not installed

### 🧪 Testing

- **Benchmark Suite**: Added 35 new tests for profiler, memory tracker, dataset, and runner
  - Profiler tests: context manager, time function, time et parse
  - Memory tests: start/stop flow, snapshot structure with peak/current/allocated
  - Runner tests: normal, profiling, memory profiling, multiple datasets, limits
  - Dataset tests: local subdirs, empty dataset, to_dict structure
- **Pipeline Context Manager Test**: Added test for `PaperProcessingPipeline` with cleanup

### 🔧 Maintenance

- **Version Bump**: Updated to version 1.18.0
  - Updated pyproject.toml version from 1.17.0 to 1.18.0
  - Updated src/pyeuropepmc/__init__.py __version__ to 1.18.0
  - Created git tag v1.18.0 for release

- **All Tests Pass**: 3203 tests pass, 11 skipped, 75.20% coverage

## [1.17.0] - 2026-06-17

### 🐛 Bug Fixes

- **Type Errors**: Fixed mypy type errors in search_logging.py and cache.py
  - Added proper type annotations for optional cryptography and cachetools imports
  - Removed unused `type: ignore` comments

- **Test Failures**: Fixed test assertions in test_helpers_coverage.py
  - Updated error message assertions to match actual validation error messages
  - Changed "Failed to read JSON file" to "JSON file not found" for VALID004
  - Changed "Failed to parse JSON file" for VALID005 validation error

### ✨ Features

- **Documentation Restructuring**: Complete overhaul of documentation organization
  - Moved guides to docs/guides/, reference to docs/reference/, migration to docs/migration/
  - Added comprehensive guides for Semantic Scholar API integration
  - New documentation on professional library usage and rate limiting

### 🔧 Maintenance

- **Version Bump**: Updated to version 1.17.0
  - Updated pyproject.toml version from 1.16.0 to 1.17.0
  - Updated src/pyeuropepmc/__init__.py __version__ to 1.17.0
  - Created git tag v1.17.0 for release

- **Auto-formatting**: Applied ruff format across codebase
  - Fixed import ordering in all test files
  - Cleaned up unused imports
  - Fixed trailing whitespace and EOF issues

## [1.15.0] - 2025-01-20

### ✨ Features

- **Parallel Download Rate Limiting Fix**: Improved rate limiter implementation for parallel batch downloads
  - Rate limiter now only invoked after cache miss (network boundary), preventing unnecessary delays for cached files
  - Fixed exception handler worker_id derivation to use futures mapping instead of stale stats dict
  - More efficient parallel downloads with proper rate limiting at network boundary
  - Fixed `NameError` when exception handlers reference undefined `stats` variable

### 🔧 Maintenance

- **Exception Handling**: Improved worker error handling in parallel downloads
  - Worker_id now correctly derived from `futures[future][0]` tuple
  - Consistent stats tracking regardless of execution context

## [1.14.0] - 2025-01-15

### ✨ Features

- **Enhanced RDF Mapping System**: Complete overhaul of RDF mapping capabilities with YAML-based configuration
  - New `InstitutionEntity` model for institutional data representation
  - Enhanced `ScholarlyWorkEntity` base class with PMID support and validation
  - Comprehensive RDF mapping synchronization script (`scripts/sync_rdf_mappings.py`)
  - Improved enrichment integration for external metadata sources

- **Advanced Enrichment Integration**: Expanded support for external APIs and data enrichment
  - New enrichment RDF generation demo script (`examples/09-enrichment/enrichment_rdf_demo.py`)
  - Enhanced RDF mapping for enrichment data with automatic entity building
  - Integration tests for enrichment workflows (`tests/mappers/test_enrichment_rdf.py`)

- **RDF Mapping Demonstration**: Complete end-to-end RDF mapping workflow example
  - New comprehensive demo notebook (`examples/10-rdf-mapping/rdf_mapping_demo.ipynb`)
  - Shows full pipeline from search → XML retrieval → RDF conversion → enrichment → comparison
  - Includes both basic XML-derived RDF and enriched RDF from external APIs

### 🔧 Maintenance

- **Model Enhancements**: Extended data models with better validation and RDF support
  - Added PMID field to `PaperEntity` with proper validation and normalization
  - Enhanced `AuthorEntity` and other models with enrichment-compatible fields
  - Improved type safety and documentation across all entity models

- **Testing Improvements**: Added comprehensive tests for new RDF mapping features
  - New test suite for enrichment RDF generation (`tests/mappers/test_enrichment_rdf.py`)
  - Enhanced model tests with RDF validation (`tests/models/test_models_rdf.py`)
  - Fixed pagination timing tests for accurate elapsed time measurement

### 📚 Documentation

- **New Examples**: Added comprehensive examples for RDF mapping workflows
  - RDF mapping demo showing complete pipeline from search to enriched RDF
  - Enrichment RDF generation examples with external API integration
  - Updated documentation for new features and capabilities

## [1.13.0] - 2025-01-10

### ✨ Features

- **Advanced Analytics and Visualization**: Comprehensive analytics suite with publication metrics, citation analysis, and interactive dashboards
  - Author statistics and geographic analysis
  - Journal distribution and publication type analysis
  - Quality metrics and duplicate detection
  - Interactive visualization plots for trends and distributions

- **HTTP Caching System**: Robust caching with requests-cache and conditional GET support
  - Configurable cache backends (memory, disk, Redis)
  - Cache invalidation and TTL management
  - Conditional requests to minimize API calls

- **Content-Addressed Artifact Storage**: SHA-256 based storage with deduplication
  - Efficient storage of large documents and metadata
  - Automatic deduplication to save disk space
  - Metadata tracking and artifact management

- **Full Text XML Parser**: Advanced parsing for Europe PMC full-text XML documents
  - Metadata extraction and table parsing
  - Multiple output formats (JSON, Markdown, plain text)
  - Configurable parsing schemas and element patterns

- **Advanced Filtering Utilities**: Enhanced post-query result filtering
  - `filter_pmc_papers`: AND logic for precise filtering
  - `filter_pmc_papers_or`: OR logic for broad exploratory searches
  - Support for MeSH terms, keywords, and abstract matching

- **Full-Text Content Retrieval**: Comprehensive client for retrieving full-text articles
  - Support for multiple formats (XML, PDF, plain text)
  - Progress tracking and error handling
  - Batch processing capabilities

### 🔧 Maintenance

- **Major Codebase Restructuring**: Complete architectural overhaul for better maintainability
  - Modular design with clear separation of concerns
  - Enhanced error handling and type safety
  - Comprehensive test coverage improvements

- **CI/CD Pipeline Enhancements**: Automated testing and quality assurance
  - Pre-commit hooks for code quality
  - Automated dependency updates
  - Coverage reporting and benchmarking


## [1.10.1] - 2025-11-10

### Fixed

- **CodeScene Integration**: Added missing `run_delta_analysis` function to CodeScene analysis script

## [1.10.0] - 2025-11-10

### ✨ Features

- **Enhanced CodeScene Integration**: Secure environment management for code health analysis
  - Improved CodeScene CLI integration with proper environment setup
  - Enhanced code quality monitoring and analysis capabilities

## [1.9.1] - 2025-11-10

### 🔧 Maintenance

- **Dependency Updates**: Updated multiple development and runtime dependencies
  - Updated `requests` to 2.32.5 for security improvements
  - Updated `notebook` to 7.4.7 for compatibility
  - Updated `attrs` to 25.4.0 and `jupyterlab-widgets` to 3.0.16
  - Updated CI actions: `actions/checkout` to v5, `actions/upload-artifact` to v5, `actions/labeler` to v6, `codecov/codecov-action` to v5, `actions/ai-inference` to v2

## [1.9.0] - 2025-11-10

### ✨ Features

- **CodeScene CLI Integration**: Automated code health analysis and quality monitoring
  - Integrated CodeScene CLI for comprehensive code analysis
  - Enhanced CI workflows with code health tracking

### 🔧 Maintenance

- **Query Builder Refactoring**: Improved error handling and removed unnecessary flags
  - Enhanced QueryBuilder with better validation and error handling
  - Removed SEARCH_QUERY_AVAILABLE flag for cleaner implementation
  - Added comprehensive unit tests for QueryBuilder functionality

- **CI Workflow Improvements**: Enhanced testing and issue tracking automation
  - Updated CI workflows for better test coverage and issue management
  - Improved automated dependency management

### Fixed

- Code review fixes: documentation improvements, unused import removal, and exception handling enhancements

## [1.8.1] - 2025-11-06

### Added

- **Advanced Query Builder**: Complete fluent API for building complex Europe PMC search queries
  - Type-safe field specifications with 150+ searchable fields
  - Fluent method chaining for complex boolean logic (AND/OR/NOT)
  - Optional query validation using CoLRev search-query package
  - Load/save queries in standard JSON format
  - Cross-platform query translation (PubMed, Web of Science, etc.)
  - Query evaluation with recall/precision metrics

- **Systematic Review Tracking**: PRISMA/Cochrane-compliant search logging
  - `log_to_search()` method for tracking queries in systematic reviews
  - Integration with search logging utilities for audit trails
  - Raw results saving for reproducibility
  - PRISMA flow diagram data generation
  - Complete systematic review workflow support

- **Field Coverage Validation**: API field synchronization tools
  - `validate_field_coverage()` function to check API vs code field coverage
  - `get_available_fields()` for fetching current API fields
  - Automated field metadata validation

### Improved

- Enhanced type safety with comprehensive Literal types for all search fields
- Better error handling with specific error codes and context
- Improved documentation with extensive examples and API reference
- Graceful fallback when optional dependencies are missing

## [1.8.0] - 2025-10-15

### Added

- AI-powered Feature Suggester GitHub Action for automated feature suggestions

## [1.7.0] - 2025-09-20

### Added

- **Full Text XML Parser**: Comprehensive XML parsing with metadata extraction
  - Support for table and figure extraction from full-text XML
  - Multiple output format conversions
  - Enhanced metadata parsing capabilities

## [1.6.0] - 2025-08-25

### Added

- **Advanced Filtering Utilities**: Powerful post-query result filtering
  - `filter_pmc_papers()`: AND logic filtering with MeSH, keywords, and abstract matching
  - `filter_pmc_papers_or()`: OR logic filtering for broader result sets
  - Case-insensitive and partial matching support

## [1.5.0] - 2025-08-10

### Added

- **Optional Disk Cache Integration**: Performance optimization with safe fallbacks
  - Disk-based caching using diskcache library
  - Backward compatibility when diskcache is not installed
  - Type-safe implementation with proper error handling

## [1.4.0] - 2025-07-28

### Added

- **Comprehensive Test Suite**: Expanded testing coverage
  - Additional unit tests for all functionality
  - Improved test organization and coverage reporting

### Improved

- Enhanced documentation with detailed usage examples
- Better code organization and maintainability

## [1.3.0] - 2025-07-22

### Added

- **Full-Text Content Retrieval**: Complete full-text access implementation
  - `FullTextClient` for downloading PDF, XML, and HTML content
  - Multiple fallback endpoints for robust retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

## [1.2.0] - 2025-07-16

### Added

- **Full-Text Content Retrieval**: Complete implementation of full-text content access
  - `FullTextClient` class for downloading PDF, XML, and HTML content
  - Support for multiple fallback endpoints for robust content retrieval
  - Intelligent content availability checking
  - Atomic download operations with proper error handling

- **Bulk FTP Downloads**: Efficient bulk PDF downloads from Europe PMC FTP servers
  - `FTPDownloader` class for querying and downloading from FTP archives
  - Smart directory searching algorithm for optimal PMC ID location
  - Bulk download and extraction capabilities
  - ZIP file handling with automatic PDF extraction

- **Enhanced Test Coverage**: Comprehensive test suite with 200+ tests
  - Unit tests for all new functionality
  - Functional tests with realistic server responses
  - Edge case coverage and error handling validation

### Improved

- Enhanced error handling with specific error codes for full-text operations
- Updated documentation with full-text API reference
- Improved type annotations throughout the codebase
- Better rate limiting and respectful API usage

## [1.1.0] - 2025-06-25

### Added

- **Enhanced BaseAPIClient**: Improved session management and context support
- **Advanced Search Parameter Validation**: Better input validation and error handling
- **Unit Tests**: Comprehensive test coverage for search functionality
- **Copilot Instructions**: Coding standards and development guidelines

### Improved

- Enhanced EuropePMCParser error handling
- Better CI/CD pipeline with coverage reporting
- Improved documentation and usage examples

## [1.0.2] - 2025-06-15

### Fixed

- Minor bug fixes and improvements
- CI/CD pipeline refinements

## [1.0.1] - 2025-06-12

### Fixed

- Python setup and dependency configuration fixes
- Semantic release configuration updates

## [1.0.0] - 2025-06-10

### Initial Release

- Initial release with core search functionality
- Support for JSON, XML, and Dublin Core formats
- Comprehensive test suite (200+ tests)
- Complete documentation and examples
- Production-ready error handling and rate limiting

### Core Features

- Europe PMC search API integration
- Smart pagination for large result sets
- Context managers for resource management
- Type hints throughout codebase
- Built-in retry logic and connection handling

For how releases are made, see [docs/development/ci-and-release-workflow.md](docs/development/ci-and-release-workflow.md)
