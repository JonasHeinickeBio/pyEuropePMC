# pyeuropepmc MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
Europe PMC (and related literature-search) functionality as tools for AI agents:
search with a query linter, open-access full text, text-mined annotations, data
links, citation graph traversal, BibTeX/RIS/CSV export, clinical trials, full-text
indexing, figure extraction, bibliography tooling, service diagnostics and optional
LLM-powered analysis. This page is the reference; the
[MCP server guide](../../../docs/features/mcp-server.md) shows the workflows.

Built on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
(`MCPServer` in SDK 2.x, `FastMCP` in 1.x; both are supported), not a hand-rolled JSON-RPC loop, so it gets spec-compliant error
semantics, concurrent async tool execution (blocking network/disk calls are
offloaded to a thread pool, so one slow request never stalls the others), and a
choice of transports out of the box.

## Installation

The MCP server ships as part of the core package — `mcp` is a required (not
optional) dependency, since the `pyeuropepmc-mcp` console script is always
installed:

```bash
pip install pyeuropepmc
```

Most tools need nothing beyond that. The `bib_*` tools need the `bibliography`
extra and the LLM tools the `agentic` extra plus a provider (see "Tool
availability" below); `pyeuropepmc[all]` unlocks every tool.

## Running the server

```bash
pyeuropepmc-mcp                              # stdio transport (default) — Claude Desktop and similar
pyeuropepmc-mcp --transport streamable-http  # HTTP transport — remote / non-desktop agents
pyeuropepmc-mcp --transport sse              # SSE transport
python -m pyeuropepmc.mcp.server --help      # full CLI reference
```

| Flag | Env var | Default | Notes |
|---|---|---|---|
| `--transport` | `PYEUROPEPMC_MCP_TRANSPORT` | `stdio` | `stdio`, `sse`, or `streamable-http` |
| `--host` | `PYEUROPEPMC_MCP_HOST` | `127.0.0.1` | bind host for `sse`/`streamable-http` |
| `--port` | `PYEUROPEPMC_MCP_PORT` | `8000` | bind port for `sse`/`streamable-http` |
| `--allowed-host` | `PYEUROPEPMC_MCP_ALLOWED_HOSTS` | none | bare host names to accept on `sse`/`streamable-http` as `Host` and as `http`/`https` `Origin`; repeatable, comma separated in the variable (spaces are ignored). SDK 2.x only (see below) |
| `--log-level` | `PYEUROPEPMC_MCP_LOG_LEVEL` | `INFO` | written to stderr, never stdout |

`stdio` is what process-managed clients like Claude Desktop expect. Use
`streamable-http` (or `sse`) to run the server as a standalone network service
that any MCP-capable agent — not just Claude — can connect to over HTTP.

### Without an install

`uvx pyeuropepmc mcp` runs the same server with no install, which is what the
MCP Registry entry tells clients to run. Claude Code:

```bash
claude mcp add pyeuropepmc -- uvx pyeuropepmc mcp
```

Cursor (`.cursor/mcp.json`) and VS Code (`.vscode/mcp.json`, under `"servers"`)
take `"command": "uvx"` and `"args": ["pyeuropepmc", "mcp"]`.

### Claude Desktop configuration

```json
{
  "mcpServers": {
    "pyeuropepmc": {
      "command": "pyeuropepmc-mcp"
    }
  }
}
```

### Remote / HTTP agents

Start the server with `--transport streamable-http --host 0.0.0.0 --port 8000`
and point any MCP HTTP client at `http://<host>:<port>/mcp`. The server speaks plain
HTTP, so put TLS termination in front of it for anything beyond a trusted network.

**Authentication is opt-in.** With no token the HTTP transports accept every request (the
server logs a warning when it listens on a non-loopback address without one). To require a
bearer token:

```bash
( umask 077; pyeuropepmc-mcp --generate-token > mcp.token )
pyeuropepmc-mcp --transport streamable-http --host 0.0.0.0 --auth-token-file mcp.token
# client: Authorization: Bearer <the token>
```

The token can also come from `PYEUROPEPMC_MCP_AUTH_TOKEN` (comma separated for several) or
`PYEUROPEPMC_MCP_AUTH_TOKEN_FILE`. There is deliberately no `--auth-token VALUE`: a command line
is readable by every user of the machine. Tokens need at least 16 printable characters; a
variable that is set but empty stops the server instead of opening it. Requests without a valid
token get HTTP 401 before the MCP server sees them; stdio is never checked. See the
[guide](../../../docs/features/mcp-server.md#running-it-as-a-network-service) for the threat
model and token rotation.

MCP SDK 2.x checks the `Host` header on the loopback addresses (DNS-rebinding
protection) and answers HTTP 421 to a name it does not know, so a reverse proxy that
forwards `Host: mcp.example.org` to `127.0.0.1:8000` needs
`--allowed-host mcp.example.org` (loopback names and origins stay allowed; a browser client's `Origin` for that name is accepted too). SDK 1.x has no such
option; there, run behind a proxy that rewrites the header.

## Tools

| Tool | Description | Needs |
|---|---|---|
| `unified_search` | Multi-source search (PubMed, arXiv, Semantic Scholar, OpenAlex, ClinicalTrials.gov) with cross-source dedup. A failing source does not fail the call; `diagnostics: true` adds `sources` (per source: `ok`, `empty`, `error`, `rate_limited` or `unavailable`, with count, seconds, the query sent and the error) and `matched_sources` on each record. Overlapping calls to one source run one at a time (`source_concurrency`), and arXiv, DBLP and Zenodo are paced at 3 s | — (the Semantic Scholar source needs `semanticscholar`) |
| `search_papers` | \[Legacy\] single-source Europe PMC search, capped at `limit`; optional filters `date_from`/`date_to`, `open_access`, `has_fulltext`, `source`, `synonym` | — |
| `count_papers` | Number of Europe PMC hits for a query (same filters), without fetching them | — |
| `analyze_search` | Aggregates over a search without returning its records: `by_year` (one Europe PMC count per year), `open_access` and the `thresholds` of `citations` (cited at least 1, 10, 100, 1000 times) are `basis: exact`, counted over all `hit_count` records; `journals`, `authors`, `types`, `countries`, `funders` and the `citations` statistics are `basis: sample`, computed from the first `limit` records (default 500, at most 1,000) in the order given by `sort`, and are `exact` only when `limit` covers the whole result. Takes the filters of `count_papers`. The response carries `hit_count`, `limit`, `records_read` and, for a sample, a `sample_note` | `analytics` for the sample metrics; `by_year` and `open_access` need nothing |
| `get_paper_details` | Resolve a paper by PMID / PMCID / DOI | — |
| `search_authors` | Author search | — |
| `get_paper_citations` | Papers citing a given paper (any Europe PMC source: MED, PMC, PPR) | — |
| `get_paper_references` | Reference list of a paper (backward citations) | — |
| `citation_snowball` | Forward/backward/both citation-graph walk | — |
| `clinical_trial_search` | ClinicalTrials.gov search by condition/intervention/keyword | — |
| `fulltext_index_query` | Search a local SQLite FTS5 full-text index | — |
| `get_paper_fulltext` | Structured full text of an open-access paper by PMCID / PMID / DOI: `markdown`, typed `sections`, or an `outline`; filter by section title, cap with `max_chars` (cut at a block boundary, `truncated` says so), optional parsed references | — |
| `tag_paper_sentences` | The sentences of an open-access paper's body by what they do: `background`, `motivation`, `method`, `result`, `claim`, `limitation`, `conclusion` (or `unknown` where no rule is sure). Excludes front matter, references, captions and administrative sections; `roles`, `sections`, `min_confidence` and `max_chars` filter; sentences come in reading order, are never cut, and `truncated` says whether some were left out; `statistics` counts the whole body. Rule-based: the section sets the default role and cues in the sentence correct it. On 93 hand-labelled sentences 82 got the right role (precision 0.92 to 1.00 per role); a paper without recognisable headings gets only background, method and conclusion (see the guide). `use_llm` asks the configured LLM about up to 40 `unknown` sentences | `agentic` + an LLM provider only for `use_llm` |
| `paper_figures` | Figures, tables and supplementary files of a PMC Open Access article, with Europe PMC download URLs | — |
| `epmc_status` | Is Europe PMC up? Probes the four endpoints this server depends on (search, full text, citations, annotations) at once with a short timeout and one request each, and answers `ok`, `degraded`, `down` or `unknown` with the HTTP status and milliseconds of each. Kept for 30 seconds (`cached`), so asking again is not load on a struggling service. No URLs or bodies in the answer | — |
| `cache_status` | Entries, capacity, size, hits, misses and hit rate of the search, article and annotation caches and the full-text XML cache. Counts only: no cache keys (they can hold query text), no content, no file paths. Offline | — |
| `clear_cache` | Empties one in-memory cache (`search`, `article`, `annotations`, `xml`) or `all`. Declared as changing state (`readOnlyHint: false`, not destructive, idempotent), so a client may ask for approval; every cleared entry is fetched again from Europe PMC. Never touches files on disk | — |
| `validate_query` | Checks a Europe PMC query for the mistakes it silently accepts (it answers a different query instead of an error): unclosed parentheses or quotes, dangling or doubled operators, unknown fields (with a suggestion), flags that are not `y`/`n`, date ranges with a missing or reversed bound, a bare leading wildcard (HTTP 503), and AND mixed with OR without parentheses. Each problem has a position; returns a normalised query. Offline | — |
| `build_query` | Builds a query from structured input (`all_of`, `any_of`, `none_of`, dates, open access, full text, source, `cites`) with a plain-language explanation, and refuses a result that would not validate. Offline | — |
| `translate_query` | Rewrites a Europe PMC query for PubMed (field codes mapped, constructs without an equivalent named in `warnings`/`dropped`, `exact` says whether the translation is faithful) or, as a keyword approximation, for arXiv, OpenAlex, Semantic Scholar and Crossref. Offline | — |
| `evaluate_query` | Scores a query against papers you already know (up to 200 included and 200 excluded PMIDs): recall, the PMIDs it misses, excluded papers it still finds, precision and F1 on the seeds. Runs the query on Europe PMC itself | — |
| `export_papers` | Exports papers for a reference manager or a spreadsheet: BibTeX, RIS or CSL-JSON (Zotero, Mendeley, EndNote, Pandoc) or CSV, JSON or Markdown, for a search `query` or a list of `ids`. BibTeX keys look like `vasiliou2005analysis`, are unique and do not change when the export is cut to size; text LaTeX reads as syntax (`& % # _ $`) is escaped; a consortium stays one author; RIS has separate `SP`/`EP` pages; a paper with more than 100 authors lists the first 100. Never cut inside a record (`truncated`, `next_skip` or `remaining` say where to continue). Writes nothing to disk | — |
| `get_papers_batch` | Metadata of up to 100 papers by PMID, PMCID or DOI (mixed) in one call: one combined Europe PMC query per 50 identifiers, a result with a status (`ok`, `not_found`, `invalid`, `error`) for every input in the order given, and a choice of fields (`abstract` optional) | — |
| `get_papers_fulltext_batch` | Markdown full text of up to 20 papers in one call within a size budget (`max_chars_per_paper`, `max_total_chars`): papers that are not open access are reported without being downloaded, the rest are fetched four at a time, and once the budget is used up the remaining papers are `skipped_budget` and not downloaded | — |
| `find_open_access` | Where a paper can be read for free: Unpaywall open-access status (gold, green, hybrid, bronze, closed), the best copy with PDF link and licence, a few alternatives, and whether `get_paper_fulltext` will work. By DOI, PMID or PMCID | `UNPAYWALL_EMAIL` in the server's environment |
| `get_paper_annotations` | Text-mined genes, proteins, chemicals, diseases, organisms and GO terms of a paper, grouped by entity with mention counts, sections and example mentions; filter by type, section, provider | — |
| `find_papers_by_entity` | Articles in which an entity (`CHEBI:16236`, `ethanol`, a gene) is mentioned, with how often and where; 1 to 8 articles per page, cursor paging | — |
| `get_paper_data_links` | Where the data of a paper is: accession numbers Europe PMC text-mined from the full text (dbSNP, RefSeq, OMIM, ClinicalTrials.gov, cited DOIs) and records providers link to it (BioStudies, model-organism databases), as a flat list with category, kind, scheme, URL and origin; filter by category or scheme. Supplementary files are in `paper_figures` | — |
| `get_paper_lab_links` | Links third parties publish for a paper, grouped by provider with a description (BioStudies, GO annotations, Faculty Opinions, Altmetric); the provider filter is applied by the server because Europe PMC ignores it | — |
| `enrich_paper` | One merged, compact record for a paper (by PMCID, PMID or DOI) from Europe PMC, Crossref, OpenAlex, Semantic Scholar, iCite and, with `UNPAYWALL_EMAIL`, Unpaywall, queried at the same time. `include` picks the field groups: `impact` (citation counts per source, relative citation ratio and percentile, topics), `funding` (funders, awards, grants), `affiliations` (authors with their institutions: name, country, ROR ID; `ror_details` adds city, country code, website and coordinates from ROR), `oa` (open-access status, licence, links) and `updates` (corrections and retractions, `is_retracted`). `sources` limits the sources. The answer has a `sources` map: `ok`, `empty`, `error` (with the reason), `timeout` (still running when `time_budget` ended, 30 s by default) or `unavailable` (a missing extra or e-mail address); a failed source gives a partial record. How long it takes, source by source, is in the [guide](../../../docs/features/mcp-server.md#how-long-enrich_paper-takes). Typically 2 to 7 KB. Read-only: nothing is written to disk | — (`semanticscholar` extra for Semantic Scholar) |
| `pico_decompose` | Splits a research question into PICO, PICOS, PICOT or SPIDER elements and builds a Europe PMC query. Rule-based, offline, no model or key. Every element is a verbatim piece of the question with its position; an element the question does not state is listed under `missing` / `optional_missing`, never filled in. The query is an AND of population (its condition) and intervention by default (`query_elements` chooses; `mesh` adds MeSH groups from the snapshot) and is checked with the `validate_query` linter (`query_check`). Covers the usual clinical phrasings; on questions phrased differently it finds fewer than half of the elements (see the guide), so check `elements` and `missing` before using the query | — |
| `mesh_expand` | MeSH descriptor (ID, heading, tree numbers), entry terms and a ready `(MESH:"..." OR "..." ...)` fragment for each term, joined with AND or OR into a checked query. Offline by default from a bundled snapshot of 244 common clinical headings taken from NLM's published MeSH (`scripts/build_mesh_snapshot.py` rebuilds it); a term it does not know is `matched: false` and searched as written. `use_api` asks the NLM MeSH service instead (network, up to five requests per term, all of MeSH; `time_budget` bounds the call and skipped terms are reported) | — |
| `analyze_citations`, `compare_citations`, `summarize_citations` | LLM-powered citation analysis | `agentic` + an LLM provider |
| `paper_screening` | PRISMA-style automated screening | `agentic` + an LLM provider |
| `research_question_analysis`, `preprint_analysis`, `literature_review`, `knowledge_graph` | LLM-powered research tooling | `agentic` + an LLM provider |
| `bib_parse_string`, `bib_validate`, `bib_to_ris`, `bib_to_csl`, `bib_merge` | BibTeX parsing/validation/conversion/merging | `bibliography` |
| `ref_resolve_doi`, `ref_resolve_pmid` | Resolve a DOI/PMID to bibliographic metadata | — |

Run `pyeuropepmc-mcp` and call `tools/list` (or open it in any MCP client) for
the full, current input schema of each tool — schemas are generated directly
from the tool functions' type hints. This table is written by hand;
`tests/mcp/unit/test_mcp_docs.py` fails when a tool is missing from it.
For workflows and the Europe PMC behaviours the tools work around, see the
[MCP server guide](../../../docs/features/mcp-server.md).

## Resources and prompts

Tools stay the main interface. The server also offers three resource templates and three prompts for clients that support them.

| Resource | Content |
|---|---|
| `epmc://paper/{pmcid}` | Markdown full text of an open-access paper, with the same size limit as `get_paper_fulltext` (30,000 characters); a cut text ends with how to get the rest |
| `epmc://paper/{pmcid}/references` | The parsed reference list as JSON (`reference_count`, `returned`, `truncated`, `references`); cut at an entry after 100,000 characters |
| `epmc://paper/{pmcid}/outline` | Section titles, block counts and sizes in characters as JSON |

Example: `epmc://paper/PMC3525259`. A resource runs the code of the tool behind it, so it has the same open-access check, XML cache and error messages: a paper that is not open access fails with "PMC... is not Open Access" and a malformed id with "pmcid must look like PMC1234567". They are templates, so `resources/templates/list` shows them and `resources/list` is empty. They go through the same transport as the tools, so whatever protects an HTTP deployment protects them too.

There is no `epmc://search/{query}` resource: a query contains slashes, quotes, brackets and spaces, clients disagree on how to encode them into a URI, and `search_papers` already does the job with a proper schema.

| Prompt | Arguments | Workflow |
|---|---|---|
| `literature_review` | `topic`, `years` (`2020` or `2019-2024`, default any), `max_papers` (1 to 100, default 20) | `count_papers`, `search_papers`, screen, `get_paper_fulltext`, a cited review with the counts |
| `critical_appraisal` | `pmcid` | `get_paper_fulltext` (outline, methods, results), `tag_paper_sentences` for limitations, `enrich_paper`, a verdict on design, sample, bias and limitations |
| `citation_trace` | `pmid`, `direction` (`both`, `forward` or `backward`, default `both`) | `get_paper_details`, `get_paper_references`, `get_paper_citations`, the most cited neighbours, `citation_snowball` for `both` |

A test reads every tool and parameter out of the prompt texts and checks them against `list_tools()`, so a renamed tool or parameter fails the build instead of the model.

### Tool availability

A tool whose feature module isn't importable, or whose optional runtime
dependency (e.g. `bibtexparser` for the bibliography tools, an LLM provider
for the LLM tools) isn't configured, doesn't disappear from `tools/list` — it
still advertises its schema, but calling it returns a clear
`pip install pyeuropepmc[<extra>]` (or provider-configuration) error instead
of a stack trace.

### LLM-powered tools

The `analyze_citations` / `paper_screening` / `literature_review` / … family
needs an LLM provider configured in the server's environment — see
[`pyeuropepmc.agentic.llm_client.create_llm_client`](../agentic/llm_client.py)
for supported providers and the relevant environment variables. Without one
configured, these tools report the missing configuration rather than failing
silently.

## Design notes

- **Concurrency.** Every underlying client (`SearchClient`, `CitationWalker`, …)
  does synchronous I/O. Each tool call offloads that work to a worker thread
  (`anyio.to_thread.run_sync`) instead of blocking the event loop, so the
  server can serve multiple agents / concurrent tool calls without one slow
  Europe PMC request head-of-line-blocking everything else.
- **Cached clients.** Underlying clients (`SearchClient`, `CitationWalker`,
  the LLM agent, …) are constructed once per process and reused — not just
  for speed, but for correctness: a fresh `CitationWalker` per call would
  reset its own internal rate limiter, and a fresh LLM agent per call would
  never hit its own analysis cache.
- **Errors.** A tool signals failure by raising (typically
  `ToolError` for an expected/user-facing
  condition, e.g. a missing identifier; imported from `mcp.server.mcpserver.exceptions`
  in SDK 2.x and `mcp.server.fastmcp.exceptions` in 1.x). The SDK turns that into a spec-
  compliant `CallToolResult` with `isError: true` — callers can reliably tell
  success from failure without string-sniffing the response text.
- **Structured content.** Tools return typed Python values (`dict`, `list`,
  `str`, …), not pre-serialized JSON strings — the SDK derives an output
  schema and returns both `structuredContent` (for programmatic consumption)
  and a human-readable text rendering.
- **Progress/logging.** A few longer-running tools (`unified_search`,
  `citation_snowball`, `paper_screening`, `literature_review`) accept an
  injected `Context` and emit `ctx.info(...)` notifications mid-call, so a
  client that surfaces MCP logging notifications can show progress instead of
  going silent for the duration of a multi-source search.

## Testing

```bash
pytest tests/mcp/unit                              # hermetic, no network
pytest tests/mcp/e2e -m "e2e and not network"       # real subprocess + real MCP client, mocked I/O boundary
pytest tests/mcp/e2e -m e2e --run-real              # + real Europe PMC calls
```

Unit tests call the tool functions directly (the `@mcp.tool()` decorator
returns the original callable unchanged) with the underlying clients mocked
via the module's lazy-singleton caches. The e2e tests spawn the real
`pyeuropepmc.mcp.server` module as a subprocess and drive it with the official
MCP client (`mcp.client.stdio` + `ClientSession`) — protocol framing is the
SDK's concern, not something to hand-roll in a test.

## See also

- [MCP specification](https://modelcontextprotocol.io/specification)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Registry](https://registry.modelcontextprotocol.io/) — published as `io.github.JonasHeinickeBio/pyeuropepmc` on every tagged release, see [`server.json`](../../../server.json)
- [pyeuropepmc documentation](https://jonasheinickebio.github.io/pyEuropePMC/)
- [Europe PMC REST API](https://europepmc.org/docs/REST_API)

## License

Distributed under the MIT License. See [LICENSE](../../../LICENSE) for details.
