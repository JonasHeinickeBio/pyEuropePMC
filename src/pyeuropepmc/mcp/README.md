# pyeuropepmc MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes
Europe PMC (and related literature-search) functionality — search, citation graph
traversal, clinical trials, full-text indexing, figure extraction, bibliography
tooling, and optional LLM-powered analysis — as tools for AI agents.

Built on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
(`FastMCP`), not a hand-rolled JSON-RPC loop, so it gets spec-compliant error
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
| `--log-level` | `PYEUROPEPMC_MCP_LOG_LEVEL` | `INFO` | written to stderr, never stdout |

`stdio` is what process-managed clients like Claude Desktop expect. Use
`streamable-http` (or `sse`) to run the server as a standalone network service
that any MCP-capable agent — not just Claude — can connect to over HTTP.

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
(behind whatever auth/TLS termination your deployment requires — the server
itself does not implement auth) and point any MCP HTTP client at
`http://<host>:<port>/mcp`.

## Tools

| Tool | Description | Needs |
|---|---|---|
| `unified_search` | Multi-source search (PubMed, arXiv, Semantic Scholar, OpenAlex, ClinicalTrials.gov) with cross-source dedup | — (the Semantic Scholar source needs `semanticscholar`) |
| `search_papers` | \[Legacy\] single-source Europe PMC search | — |
| `get_paper_details` | Resolve a paper by PMID / PMCID / DOI | — |
| `search_authors` | Author search | — |
| `get_paper_citations` | Papers citing a given paper | — |
| `citation_snowball` | Forward/backward/both citation-graph walk | — |
| `clinical_trial_search` | ClinicalTrials.gov search by condition/intervention/keyword | — |
| `fulltext_index_query` | Search a local SQLite FTS5 full-text index | — |
| `paper_figures` | Figures, tables and supplementary files of a PMC Open Access article, with Europe PMC download URLs | — |
| `analyze_citations`, `compare_citations`, `summarize_citations` | LLM-powered citation analysis | `agentic` + an LLM provider |
| `paper_screening` | PRISMA-style automated screening | `agentic` + an LLM provider |
| `research_question_analysis`, `preprint_analysis`, `literature_review`, `knowledge_graph` | LLM-powered research tooling | `agentic` + an LLM provider |
| `bib_parse_string`, `bib_validate`, `bib_to_ris`, `bib_to_csl`, `bib_merge` | BibTeX parsing/validation/conversion/merging | `bibliography` |
| `ref_resolve_doi`, `ref_resolve_pmid` | Resolve a DOI/PMID to bibliographic metadata | — |

Run `pyeuropepmc-mcp` and call `tools/list` (or open it in any MCP client) for
the full, current input schema of each tool — schemas are generated directly
from the tool functions' type hints, so this table and the server can never
drift apart.

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
  `mcp.server.fastmcp.exceptions.ToolError` for an expected/user-facing
  condition, e.g. a missing identifier). The SDK turns that into a spec-
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
