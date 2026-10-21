# MCP server

`pyeuropepmc-mcp` lets an AI agent search Europe PMC, read papers and export references through the [Model Context Protocol](https://modelcontextprotocol.io/). This page shows how the tools fit together, gives a workflow for the common jobs, and lists the Europe PMC behaviours that the tools work around. The [package README](../../src/pyeuropepmc/mcp/README.md) has the flags, the transports and the reference table of every tool.

## Connect a client

The server is part of the base install. Most clients start it themselves:

```bash
claude mcp add pyeuropepmc -- uvx pyeuropepmc mcp     # Claude Code, no install needed
pyeuropepmc-mcp                                       # stdio, for any client that spawns it
pyeuropepmc-mcp --transport streamable-http           # HTTP at http://127.0.0.1:8000/mcp
```

For Claude Desktop, Cursor and VS Code, add `"command": "pyeuropepmc-mcp"` (or `"command": "uvx"` with `"args": ["pyeuropepmc", "mcp"]`) to the client's MCP configuration; the [README](../../README.md#-mcp-server) shows the file for each. The server has no authentication of its own: keep the HTTP transport on `127.0.0.1` or put an authenticating proxy in front of it.

Two tools need configuration. `find_open_access` reads `UNPAYWALL_EMAIL` (Unpaywall asks for a contact address), and the LLM tools need the `agentic` extra and an `OPENAI_API_KEY`. A tool whose dependency is missing stays in the tool list and answers with the `pip install` line it needs.

## Which tool for which job

| You want to | Use |
|---|---|
| Check a query before running it | `validate_query`, then `count_papers` |
| Write a query from parts | `build_query` |
| Run the same search on PubMed or another database | `translate_query` |
| Test a query against papers you already know | `evaluate_query` |
| Search | `search_papers` (Europe PMC), `unified_search` (several sources, duplicates merged), `search_authors` |
| Look up papers you have identifiers for | `get_paper_details` (one), `get_papers_batch` (up to 100) |
| Read a paper | `get_paper_fulltext`, `get_papers_fulltext_batch`, `paper_figures` |
| Find a free copy of a paper that is not open access in Europe PMC | `find_open_access` |
| Find genes, chemicals, diseases | `get_paper_annotations`, `find_papers_by_entity` |
| Find where the data is | `get_paper_data_links`, `get_paper_lab_links` |
| Follow citations | `get_paper_citations`, `get_paper_references`, `citation_snowball` |
| Get references into a reference manager | `export_papers` |
| Find out why something failed | `epmc_status`, `cache_status`, `clear_cache` |

## Workflows

### Search without surprises

Europe PMC does not reject a malformed query; it answers a different one. An unclosed parenthesis is ignored, `a AND b OR c` returns the hits for `a` alone, and an unknown field name gives zero hits. Run the query through `validate_query` first: it reports each problem with its position, suggests the field you probably meant, and says what Europe PMC will do with the query as written. `build_query` produces queries that pass this check by construction.

```text
validate_query   query="CRISPR AND (TITLE:base editing"
count_papers     query="CRISPR AND TITLE:\"base editing\"", date_from="2020-01-01", open_access=true
search_papers    query="CRISPR AND TITLE:\"base editing\"", limit=25, sort="cited"
```

For a systematic review, give `evaluate_query` the PMIDs of papers that must be found and, optionally, papers that must not. It returns the recall, the PMIDs the query misses, and the excluded papers it still finds. `translate_query` rewrites the final query for PubMed and reports what it could not translate.

### Search to reference manager

`export_papers` writes BibTeX, RIS, CSL-JSON, CSV, JSON or Markdown for a search `query` or a list of `ids`. Nothing is written to disk; the text comes back in the response.

```text
export_papers  query="malaria AND TITLE:vaccine", format="bibtex", limit=50
export_papers  ids=["16004729", "PMC5321187", "10.1038/s41579-019-0296-0"], format="ris"
```

BibTeX keys look like `vasiliou2005analysis`, are unique within an export, and stay the same when an export is cut to size. A record is never cut in the middle: when the response is full, `truncated` is true and `next_skip` (for a query) or `remaining` (for `ids`) says where to continue. Identifiers that Europe PMC does not know are listed in `skipped` with the reason, in the order you gave them.

### Read a paper

```text
get_paper_details        pmid="16004729"
get_paper_fulltext       pmcid="PMC5321187", format="sections", sections=["Methods"], max_chars=20000
```

`format` is `markdown`, `sections` (typed blocks) or `outline`. `max_chars` cuts the text at a block boundary and sets `truncated`, so a long paper fits in one response. `get_papers_fulltext_batch` reads up to 20 papers within a size budget and reports each paper's status (`ok`, `not_open_access`, `not_in_pmc`, `no_matching_section`, `skipped_budget`, ...).

Europe PMC serves full-text XML only for papers in its open-access set. For any other paper, `find_open_access` asks Unpaywall where a free copy is (publisher, repository or preprint) and returns the best link, the licence and a few alternatives.

### Entities, data and supplements

```text
get_paper_annotations   pmid="16004729", annotation_type="Chemicals", limit=20
find_papers_by_entity   entity="CHEBI:16236", limit=8
get_paper_data_links    pmid="32257953", category="SNPs"
get_paper_lab_links     pmcid="PMC3257301", provider="genome"
paper_figures           pmcid="PMC5321187"
```

`get_paper_annotations` groups the text-mined entities of one paper with their mention counts, sections and examples. `find_papers_by_entity` goes the other way and pages through articles that mention an entity, one to eight per page. `get_paper_data_links` lists accession numbers that Europe PMC found in the text (dbSNP, RefSeq, OMIM, ClinicalTrials.gov, cited DOIs) and records that providers link to the paper, each with its `category`, `kind` and `origin`; Altmetric pages are in the list too, marked `kind: altmetrics`. Supplementary files are part of `paper_figures`, with their download URLs.

### Citations

`citation_snowball` walks the citation graph forwards, backwards or both from one paper, with limits per level and a minimum citation count. `get_paper_citations` and `get_paper_references` return one step.

## What Europe PMC does that the tools work around

These were measured against the live service in October 2026. The tools handle them for you; they are listed so that the results make sense.

- **Queries are never rejected.** See above; `validate_query` exists for this reason.
- **A leading wildcard** (`*cancer`) gives HTTP 503. `validate_query` flags it.
- **Full text of a paper outside the open-access set** gives HTTP 500 after about 20 seconds, which looks like an outage. The tools look at the open-access flag first and answer at once with the real reason.
- **`CITES:` works with PMIDs only.** `build_query(cites=...)` takes a PMID for that reason.
- **The Annotations API** returns between one and eight articles per page for an entity search, and ignores the type, provider and section filters, so the tools apply those filters themselves.
- **`labsLinks` ignores its provider filter** and `datalinks` ignores its page size. `get_paper_lab_links` and `get_paper_data_links` filter and limit on the server side.
- **Unknown identifiers** get an empty answer with HTTP 200 from the link services. Identifiers are checked before the request, and a paper without links gives an empty list, which is a valid result.

## When something fails

Call `epmc_status` first. It makes one request to each of the four endpoints the tools depend on (search, full text, citations, annotations) and answers `ok`, `degraded`, `down` or `unknown` with the HTTP status and the time of each. The answer is kept for 30 seconds, so asking again does not add load to a service that may be struggling. If Europe PMC is healthy and a result looks stale, `cache_status` shows the hit rate of the in-memory caches and `clear_cache` empties one of them (`search`, `article`, `annotations`, `xml` or `all`); nothing on disk is touched.

A failed call comes back with `isError: true` and a message that names the cause. In the batch tools, a failure for one identifier does not fail the call: every input gets its own status in the order it was given.

## Limits

| Tool | Limit |
|---|---|
| `get_papers_batch` | 100 identifiers per call, looked up 50 at a time |
| `get_papers_fulltext_batch` | 20 papers, within `max_chars_per_paper` and `max_total_chars` |
| `evaluate_query` | 200 included and 200 excluded PMIDs |
| `export_papers` | 1,000 records per call; continue with `skip` or the `remaining` ids |
| `find_papers_by_entity` | 1 to 8 articles per page, continued with `cursor` |
| `get_paper_fulltext` | `max_chars` up to 500,000 |
