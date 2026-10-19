# PyEuropePMC

[![PyPI version](https://img.shields.io/pypi/v/pyeuropepmc.svg?logo=pypi&logoColor=white)](https://pypi.org/project/pyeuropepmc/)
[![Python versions](https://img.shields.io/pypi/pyversions/pyeuropepmc.svg?logo=python&logoColor=white)](https://pypi.org/project/pyeuropepmc/)
[![CI](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/cdci.yml/badge.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/actions/workflows/cdci.yml)
[![codecov](https://codecov.io/gh/JonasHeinickeBio/pyEuropePMC/branch/main/graph/badge.svg)](https://codecov.io/gh/JonasHeinickeBio/pyEuropePMC)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/LICENSE)
[![MCP server](https://img.shields.io/badge/MCP-server-30A46C?logo=modelcontextprotocol&logoColor=white)](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/mcp/README.md)

**PyEuropePMC** is a Python client for [Europe PMC](https://europepmc.org/). It searches the literature, downloads open-access full text, and parses JATS XML into metadata, plain text and structured sections. It also ships a command-line tool and an MCP server for AI agents.

## ✨ Features

- **Europe PMC search** with plain queries or a fluent [`QueryBuilder`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/api/query-builder.md), pagination, and results as JSON, XML or Dublin Core. [Search guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/search/README.md)
- **Ten more sources in one search**, with duplicates merged: PubMed, arXiv, ClinicalTrials.gov, OpenAlex, Semantic Scholar, CORE, DBLP, DOAJ, HAL and Zenodo. Semantic Scholar needs the `semanticscholar` extra and CORE an API key. [Multi-source search](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/multi-source-search.md)
- **Full text**: XML (Europe PMC first, then other open sources), PDF and HTML, plus bulk PDF downloads from the Europe PMC FTP site. [Full-text retrieval](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/fulltext/README.md)
- **JATS XML parsing**: metadata, authors, tables, figures and references; plain text and Markdown; typed sections for retrieval-augmented generation (RAG); JATS normalization and BioC export. [XML parsing](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/parsing/README.md), [JATS normalization](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/parsing/jats-normalization.md)
- **Text-mining annotations** for genes, diseases, chemicals and their relationships. [Examples](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples/10-annotations)
- **Citations and metadata**: walk citation graphs, and enrich records from Crossref, Unpaywall, OpenAlex, Semantic Scholar, DataCite, ORCID, ROR and iCite. [Citation walking](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/citation-walking.md), [Enrichment](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/guides/enrichment.md)
- **Analysis**: pandas DataFrames, citation statistics, duplicate detection, plots, and PRISMA-style search logs for systematic reviews. [Analytics](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/api/analytics-visualization.md), [Review tracking](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/systematic-review-tracking.md)
- **RDF knowledge graphs** from parsed articles, mapped by the [`rdf_map.yml`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/conf/rdf_map.yml) that ships with the package; pass `RDFMapper(config_path=...)` or `PipelineConfig(rdf_config_path=...)` to use your own. [Data models and RDF](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/reference/models.md)
- **A command line and an MCP server**, described below.

## 📦 Installation

```bash
pip install pyeuropepmc                              # core
pip install "pyeuropepmc[analytics,visualization]"   # add extras (quote the brackets)
pip install "pyeuropepmc[all]"                       # every optional feature
```

PyEuropePMC supports Python 3.10 to 3.13. The core install covers search, full-text download, XML parsing, RDF, the command line and the MCP server. The extras add:

| Extra | Installs | Adds |
|---|---|---|
| `analytics` | pandas, numpy | `to_dataframe`, `citation_statistics`, `quality_metrics`, `remove_duplicates` and CSV export |
| `visualization` | matplotlib, seaborn, pandas, numpy | The `plot_*` functions and `create_summary_dashboard` |
| `export` | pandas, tabulate, xlsxwriter | Excel and Markdown-table export (`pyeuropepmc.utils.export`) |
| `semanticscholar` | semanticscholar | `SemanticScholarClient` and the `semantic_scholar` search source |
| `enrichment` | semanticscholar | Semantic Scholar data in `PaperEnricher` |
| `bibliography` | bibtexparser | BibTeX parsing, validation and RIS/CSL conversion, including the `bib_*` MCP tools |
| `zotero` | pyzotero | The Zotero client |
| `agentic` | openai, langchain, langchain-openai, langgraph, jinja2 | LLM analysis, the LLM MCP tools and `pyeuropepmc claim` |
| `ui` | flask, tornado | The web UI (`pyeuropepmc claim serve`) |
| `signing` | cryptography | Signed search logs for systematic reviews |
| `benchmark` | huggingface-hub | Downloading the published benchmark datasets (`pyeuropepmc benchmark download`) |
| `rdf` | nothing | Kept so existing installs keep working; the core rdflib writes JSON-LD itself |
| `standard` | jupyterlab, notebook, ipykernel, ipython, ipywidgets, matplotlib, seaborn, pandas, numpy, tabulate, xlsxwriter, requests-cache, rich | Jupyter plus the analytics, plotting and export packages |
| `all` | all of the above | Every optional feature |

Upgrading from 1.x? The [migration guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/migration/v1-to-v2.md) lists what moved into extras.

## 🚀 Quick start

```python
from pyeuropepmc import FullTextClient, FullTextXMLParser, QueryBuilder, SearchClient

# 1. Search Europe PMC for open-access articles ("CRISPR AND OPEN_ACCESS:y")
query = QueryBuilder().keyword("CRISPR").and_().field("open_access", True).build()
with SearchClient() as search:
    hits = search.search_and_parse(query, pageSize=10)
pmcid = next(hit["pmcid"] for hit in hits if hit.get("pmcid"))

# 2. Download the article's JATS XML (raises an error if no source has it)
with FullTextClient() as fulltext:
    xml_path = fulltext.download_xml_by_pmcid(pmcid, output_path=f"articles/{pmcid}.xml")

# 3. Parse it
parser = FullTextXMLParser(xml_path.read_text(encoding="utf-8"))
metadata = parser.extract_metadata()
print(metadata["title"])
print(", ".join(metadata["authors"][:3]))
text = parser.to_plaintext()  # or parser.to_markdown()

# 4. Collect text blocks with their section path, ready to chunk and embed for RAG
chunks = []
for section in parser.get_full_text_sections_structured():
    if section["section_type"] not in ("front", "body"):  # skip back matter and appendices
        continue
    for block in section["content"]:
        if block.get("text"):
            path = section.get("section_path", section["title"])
            chunks.append({"section": path, "type": block["type"], "text": block["text"]})
print(f"{len(chunks)} text blocks")
```

`section_type` is `front` for the title and abstract, then `body`, `back` or `appendix`. Each block has a `type` such as `paragraph`, `list`, `table` or `figure`. Tables and figures carry `label` and `caption`, and tables also carry `rows`. The [XML parsing guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/parsing/README.md) covers the other extractors.

## 🔒 Safe XML parsing

PyEuropePMC parses every XML document it reads with [defusedxml](https://pypi.org/project/defusedxml/): full-text articles, Europe PMC search results, arXiv and PubMed responses, and local files. A DOCTYPE declaration is accepted, but a document that declares entities, internal or external, is refused rather than expanded; `FullTextXMLParser` raises `ParsingError`. lxml is not used and does not need to be installed.

## 💻 Command line

| Command | What it does |
|---|---|
| `pyeuropepmc unified_search` | `search` several sources with deduplication, or `compare-sources` to see each source's results |
| `pyeuropepmc normalize` | Turn JATS XML into clean text (`text`), sections (`sections`) or BioC JSON (`bioc`); `classify` a heading; `batch` a directory |
| `pyeuropepmc benchmark` | Score and profile the XML parser on a local folder or a published dataset |
| `pyeuropepmc claim` | Check the claims in a text against Europe PMC literature with LLM agents (needs the `agentic` extra and an API key) |

```bash
pyeuropepmc unified_search search "CRISPR base editing" --limit 10 --output results.json
pyeuropepmc benchmark list-datasets
```

`unified_search search` queries Europe PMC, PubMed and arXiv unless you pass `--source`. Add `--help` to any command for its options.

## 🤖 MCP server

`pyeuropepmc-mcp` serves 27 tools over the [Model Context Protocol](https://modelcontextprotocol.io/): multi-source search with date, open-access and source filters, hit counts, paper details, citations and references, open-access full text as markdown or typed sections (with a section filter and a size cap, so a long paper fits in one response), citation-graph walking, ClinicalTrials.gov search, figure extraction, a local full-text index, bibliography conversion and LLM-powered analysis. The server is part of the core install. `pip install "pyeuropepmc[all]"` enables every tool; otherwise the `bib_*` tools need `bibliography`, and the LLM tools need `agentic` plus an OpenAI-compatible API key (see Configuration below).

```bash
pyeuropepmc-mcp                                # stdio, for Claude Desktop and similar clients
pyeuropepmc mcp                                # the same server, through the CLI
pyeuropepmc-mcp --transport streamable-http    # HTTP at http://127.0.0.1:8000/mcp
```

For Claude Desktop and other clients that start the server themselves:

```json
{
  "mcpServers": {
    "pyeuropepmc": {
      "command": "pyeuropepmc-mcp"
    }
  }
}
```

Without an install, `"command": "uvx"` with `"args": ["pyeuropepmc", "mcp"]` does the same; this is what the MCP Registry entry tells clients to run. For Claude Code, one command adds it:

```bash
claude mcp add pyeuropepmc -- uvx pyeuropepmc mcp
```

Cursor (`.cursor/mcp.json`) and VS Code (`.vscode/mcp.json`, under `"servers"` instead of `"mcpServers"`) take the same `command` and `args`.

The server has no authentication of its own, so keep the HTTP transport on 127.0.0.1 or put an authenticating proxy in front of it. The [MCP server guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/src/pyeuropepmc/mcp/README.md) lists every tool. The server is listed in the [MCP Registry](https://registry.modelcontextprotocol.io/) as `io.github.JonasHeinickeBio/pyeuropepmc`.

<!-- The MCP Registry confirms this PyPI package belongs to the server by finding the next line in its README. Keep it. -->
<!-- mcp-name: io.github.JonasHeinickeBio/pyeuropepmc -->

## ⚙️ Configuration

Europe PMC needs no API key. Other services read these environment variables. A value passed in code, such as `FullTextClient(email=...)` or `EnrichmentConfig(unpaywall_email=...)`, takes precedence.

| Variable | Used for |
|---|---|
| `UNPAYWALL_EMAIL`, `CROSSREF_EMAIL` | Contact e-mail for Unpaywall and Crossref. `FullTextClient` needs one of them for its Unpaywall fallback. |
| `OPENALEX_EMAIL`, `DATACITE_EMAIL`, `ROR_EMAIL`, `ROR_CLIENT_ID` | The other enrichment sources |
| `SEMANTIC_SCHOLAR_API_KEY` | Semantic Scholar, with higher rate limits |
| `CORE_API_KEY` | The `core` search source |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | LLM features, with any OpenAI-compatible API; the model defaults to `gpt-4o-mini` |
| `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LOCAL` | The Zotero client |
| `PYEUROPEPMC_MCP_TRANSPORT`, `PYEUROPEPMC_MCP_HOST`, `PYEUROPEPMC_MCP_PORT`, `PYEUROPEPMC_MCP_LOG_LEVEL` | Defaults for the `pyeuropepmc-mcp` options |

The `pyeuropepmc` command also loads the first `.env` file it finds in the current directory, one of its parents, or `~/.config/pyeuropepmc/`. Variables that are already set keep their values.

## 📚 Documentation

The guides are in [`docs/`](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/docs). Start with [installation](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/getting-started/installation.md) and the [quick start](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/getting-started/quickstart.md), or go straight to the [API reference](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/api/README.md), [caching](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/features/caching/README.md), the [example scripts](https://github.com/JonasHeinickeBio/pyEuropePMC/tree/main/examples) and the [changelog](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/CHANGELOG.md).

**Parser benchmark.** On the 55 JATS articles in `benchmark_xmls/xml`, the parser's mean composite quality score is 0.998 (measured on 2026-09-15). The [benchmarking guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/guides/benchmarking.md) explains the metrics. To reproduce the score from a source checkout, or to score a published dataset:

```bash
pyeuropepmc benchmark run local --local-path benchmark_xmls/xml --limit 55
pyeuropepmc benchmark download PLOS_1000   # 1,000 articles, 1.3 GB
pyeuropepmc benchmark run PLOS_1000
```

The weekly benchmark workflow times the API clients and opens a pull request that refreshes the section below.

<!-- BENCHMARK-RESULTS:START -->
## 📊 Performance

> Last updated: 2026-10-19

| Metric | Value |
|--------|-------|
| **Benchmarked methods** | 10 |
| **Total requests** | 224 |
| **Mean call time** | 0.926s |
| **Success rate** | 100.0% |

<details>
<summary>📈 View full benchmark report</summary>

# 🚀 pyEuropePMC Benchmark Suite
**Generated:** 2026-10-19 07:32:23

## 📊 Summary

- **Total Benchmarks:** 6
- **Total Methods:** 10
- **Successful Runs:** 10
- **Failed Runs:** 0
- **Cache Enabled:** 5

## ArticleClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | 1.675s | 0.243s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.557s · p95: 2.058s · ops: 0.60/s · runs: 30</sub>
| get_citations | 1.646s | 0.117s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.603s · p95: 1.962s · ops: 0.61/s · runs: 30</sub>

## ArticleClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| get_article_details | <1ms | <1ms | 0.0MB | ✅ | 1 | 0 |
<sub>p50: 11µs · p95: 15µs · ops: 84862.99/s · runs: 30</sub>
| get_citations | <1ms | <1ms | 0.0MB | ✅ | 1 | 0 |
<sub>p50: 12µs · p95: 15µs · ops: 77084.96/s · runs: 30</sub>

## SearchClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | 2.055s | 0.241s | 0.1MB | ❌ | 31 | 0 |
<sub>p50: 2.006s · p95: 2.552s · ops: 0.49/s · runs: 30</sub>
| get_hit_count | 2.048s | 0.408s | 0.0MB | ❌ | 31 | 0 |
<sub>p50: 1.884s · p95: 2.913s · ops: 0.49/s · runs: 30</sub>

## SearchClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| search | <1ms | <1ms | 0.0MB | ✅ | 1 | 0 |
<sub>p50: 72µs · p95: 93µs · ops: 13426.99/s · runs: 30</sub>
| get_hit_count | <1ms | <1ms | 0.0MB | ✅ | 1 | 0 |
<sub>p50: 75µs · p95: 91µs · ops: 12874.50/s · runs: 30</sub>

## FullTextClient_NoCache

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | 1.833s | 1.327s | 0.0MB | ❌ | 93 | 0 |
<sub>p50: 1.303s · p95: 5.034s · ops: 0.55/s · runs: 30</sub>

## FullTextClient_Cached

| Method | Mean Time | Std Dev | Mean Memory | Cache | Requests | Errors |
|---|---:|---:|---:|:--:|---:|---:|
| check_fulltext_availability | <1ms | <1ms | 0.0MB | ✅ | 3 | 0 |
<sub>p50: 14µs · p95: 16µs · ops: 66591.20/s · runs: 30</sub>

## 🔁 Cache vs No-Cache Comparison

### ArticleClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_article_details | 1.675s | <1ms | >16749.4x |
| get_citations | 1.646s | <1ms | >16459.2x |

### FullTextClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| check_fulltext_availability | 1.833s | <1ms | >18330.5x |

### SearchClient — cached vs no-cache

| Method | No-Cache Mean | Cached Mean | Speedup (no/cache) |
|---|---:|---:|---:|
| get_hit_count | 2.048s | <1ms | >20482.1x |
| search | 2.055s | <1ms | >20553.2x |

---
_Notes: Means are computed over measured iterations; '-' indicates missing data. Values like '<1ms' indicate very fast cached responses. Speedups shown as lower-bounds when cached times are too small to measure precisely._

## ⚙️ How to reproduce

Run the modular benchmark locally and regenerate these artifacts:

```bash
pytest tests/benchmark_article_client.py::test_modular_benchmark_system -m benchmark --force-enable-socket --timeout=3600
```

- Detailed JSON results: `MODULAR_BENCHMARK_RESULTS.json`

</details>
<!-- BENCHMARK-RESULTS:END -->

## 🤝 Contributing

Contributions are welcome. The [development guide](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/docs/development/README.md) covers setup, testing, code quality and the release process. Report bugs and suggest features in the [issue tracker](https://github.com/JonasHeinickeBio/pyEuropePMC/issues).

## 📝 Citation

If PyEuropePMC supports your research, please cite it and give the version you used (`pip show pyeuropepmc` prints it):

```bibtex
@software{pyeuropepmc,
  author = {Heinicke, Jonas},
  title  = {{PyEuropePMC}: a Python toolkit for Europe PMC},
  url    = {https://github.com/JonasHeinickeBio/pyEuropePMC}
}
```

The literature itself comes from [Europe PMC](https://europepmc.org/); please acknowledge it as your data source.

## 📄 License

PyEuropePMC is released under the [MIT License](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/LICENSE). Articles you retrieve keep their own licences, which `FullTextXMLParser.extract_license()` reads from the XML.
