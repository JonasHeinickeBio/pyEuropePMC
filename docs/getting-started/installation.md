# Installation

This page covers installing pyEuropePMC from PyPI, choosing extras for optional features, setting up a development environment, and checking that the installation works.

## Requirements

- Python 3.10–3.13
- Windows, macOS or Linux

## Install from PyPI

```bash
pip install pyeuropepmc
```

The base install includes search, full-text download, XML parsing, query building, deduplication, caching, rdflib, the `pyeuropepmc` command and the `pyeuropepmc-mcp` server.

## Extras

Some features need packages that the base install leaves out. Install them as extras. Quote the argument so that shells such as zsh do not treat the brackets as a pattern:

```bash
pip install "pyeuropepmc[analytics]"
pip install "pyeuropepmc[analytics,visualization]"
```

| Extra | Installs | Needed for |
|---|---|---|
| `analytics` | numpy, pandas | DataFrames and publication statistics |
| `visualization` | matplotlib, numpy, pandas, seaborn | Plots |
| `export` | pandas, tabulate, xlsxwriter | Excel and Markdown-table export |
| `rdf` | rdflib-jsonld | JSON-LD output; rdflib itself is in the base install |
| `ui` | flask, tornado | The claim-review web interface |
| `signing` | cryptography | Signed search logs |
| `bibliography` | bibtexparser | Reading and writing BibTeX |
| `zotero` | pyzotero | Zotero library sync |
| `agentic` | jinja2, langchain, langchain-openai, langgraph, openai | LLM agents and claim verification |
| `semanticscholar` | semanticscholar | The library-backed Semantic Scholar client |
| `enrichment` | cryptography, semanticscholar | Enrichment clients |
| `standard` | the `analytics`, `visualization` and `export` packages, plus ipykernel, ipython, ipywidgets, jupyterlab, notebook, requests-cache and rich | Everyday notebook work |
| `all` | every package in the rows above | All optional features |

When a feature needs a package that is not installed, pyEuropePMC raises `OptionalDependencyError` with a message in this form:

```text
The '<package>' package is required for <feature>.
Install it with: <install command>
```

RML mapping (`pyeuropepmc.mappers.rml_rdfizer`) also needs the `rdfizer` package, which no extra installs: `pip install rdfizer`.

## Install from source

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
pip install -e .
```

## Development setup

The development tools (pytest, ruff, mypy, pre-commit and others) are a PEP 735 dependency group named `dev` in `pyproject.toml`, not an extra, so installing pyEuropePMC with extras does not install them. Poetry installs the `dev` group by default:

```bash
git clone https://github.com/JonasHeinickeBio/pyEuropePMC.git
cd pyEuropePMC
poetry install --all-extras
poetry run pre-commit install
poetry run pytest
```

`--all-extras` gives the same packages as the main CI test job. The [development guide](../development/README.md#setup) also shows how to install with uv, as CI does.

## Check the installation

```python
import pyeuropepmc
from pyeuropepmc import SearchClient

print(pyeuropepmc.__version__)

with SearchClient() as client:
    count = client.get_hit_count("malaria")

print(f"Europe PMC is reachable: {count} results for 'malaria'")
```

## Troubleshooting

- **`ModuleNotFoundError: No module named 'pyeuropepmc.search'`** (or `.clients`, `.processing`): these are 1.x import paths. Import from the top level, for example `from pyeuropepmc import SearchClient`, or see [Migrating from 1.x to 2.0](../migration/v1-to-v2.md).
- **`OptionalDependencyError`:** install the extra that the message names.
- **`zsh: no matches found: pyeuropepmc[all]`:** quote the argument: `pip install "pyeuropepmc[all]"`.
- **Network errors:** pyEuropePMC calls `https://www.ebi.ac.uk/europepmc/webservices/rest/`. Check that your network allows it; behind a proxy, set the `HTTPS_PROXY` environment variable, which `requests` reads.
- **HTTP 429 (rate limiting):** each client waits `rate_limit_delay` seconds between requests (default 1.0). Increase it, for example `SearchClient(rate_limit_delay=2.0)`.

## Next steps

- [Quick start](quickstart.md)
- [SearchClient API](../api/search-client.md)
