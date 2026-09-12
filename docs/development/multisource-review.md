# Multi-source search / enrichment / full-text review

Review of how pyEuropePMC federates external APIs, against three goals:

1. **Europe PMC is the base.** Every pipeline starts from an EPMC record and
   other services only *add* what EPMC is missing.
2. **Everything modular and optional.** No source pulls a hard dependency into
   the core; a missing optional package produces a helpful hint, not a crash.
3. **Optimal use of each API** (right endpoint, right batch size, parallel,
   cached, rate-limit-aware).

Checked 2026-09-10 on `feature/modular-literature-tools`.

---

## 1. Unified search (`features/search/`)

### What's already good

- `registry.py` — `SourceSpec` + `register_source` + entry-point loading. Sources
  are pluggable, dependency-aware (`OptionalDependencyError` names the extra),
  and nothing is imported at module load.
- `unified_search.py` — parallel `ThreadPoolExecutor` fan-out, per-source query
  translation (`query_translation.py`), per-source timings/errors in
  `report.metadata`, `LiteratureMerger` dedup afterwards.
- `europepmc` is in `_DEFAULT_SOURCES` and first in the list.

### Fixed in this pass

| Issue | Fix |
|-------|-----|
| `LiteratureResult.source` pattern/validator did **not** list `europepmc`, so every EPMC hit raised `ValidationError` and `UnifiedSearch` silently got **zero** results from its home API. | Added `europepmc` (+ `icite`) to the pattern and the validator set; the adapter now skips one bad record instead of dropping the batch. |
| `SOURCE_PRIORITY` in the merger had no `europepmc` key → EPMC records scored `"unknown"` (10, the lowest) and lost every field tie-break to PubMed/CrossRef. | `europepmc = 110` (highest); filled in the other registered sources; added `europepmc` to the `publication_year` preferred sources. |

### Still worth doing

- **Per-source `limit`.** `search()` sends the same `limit` to every source.
  EPMC (the base) should be asked for more (e.g. `2×limit`) and the satellites
  for less, so the merged set is EPMC-shaped.
- **Uniform `search()` contract.** `_run_sources` calls
  `client.search(query=…, limit=…, sort=…, **kwargs)` for every source. Sources
  that don't accept `sort` (or a stray `kwarg`) raise `TypeError`, which is
  caught and recorded as a *source failure* — the source silently drops out.
  Either (a) filter kwargs per-source like `registry.load_source` already does
  for constructors, or (b) define a strict `LiteratureSource` Protocol and adapt
  each client to it.
- **`search_all()` swallows errors** (`per_source, _, _`). Return the error dict
  too, or attach it to the result.
- **"Enrich, don't merge" mode.** Today all sources are peers and dedup picks
  one canonical record. Add `UnifiedSearch(primary="europepmc")`: keep the EPMC
  result set as the spine, use the others only to (1) fill missing fields on
  matched records (`LiteratureResult.merge`, which already prefers `self`) and
  (2) append records EPMC didn't have, tagged with their origin. This is the
  literal reading of "europepmc as base, get everything else from the others".
- **No cross-source cache.** Each client caches its own HTTP calls, but an
  identical `UnifiedSearch.search(...)` re-runs the whole fan-out. A short-TTL
  `diskcache` on `(sorted(sources), query, limit)` would help notebooks.

---

## 2. Enrichment (`features/enrich/`)

### What's already good

- Client-per-source (`crossref`, `datacite`, `unpaywall`, `semantic_scholar`,
  `openalex`, `ror`), all `BaseEnrichmentClient` with shared caching / rate
  limiting.
- `PaperEnricher._resolve_to_doi()` already uses **Europe PMC** to turn a PMCID
  into a DOI — EPMC is the resolver.
- `EnrichmentConfig` gates every source behind an `enable_*` flag; optional
  packages (`semanticscholar`) degrade to a hint.

### Gaps vs. the goals

- **Europe PMC is not an enrichment *source*.** It is used only to resolve an
  identifier. The base record (title, abstract, authors, MeSH, grants,
  full-text links, `citedByCount`, `isOpenAccess`) should come from EPMC
  *first*, then CrossRef/OpenAlex/S2/iCite fill gaps. Add an
  `EuropePMCEnrichmentClient` (wraps `ArticleClient` / `SearchClient`) and make
  it `enable_europepmc = True` by default and merged with the highest priority.
- **`iCite` is implemented but not wired in.** `sources/icite.py` (`ICiteClient`,
  RCR + citation percentile, PMID-based, free, no key) has no `enable_icite`
  flag and is never constructed by `PaperEnricher`. Add it — it is the best free
  citation-context signal for biomedical papers and complements EPMC's
  `citedByCount`.
- **Enrichment is sequential.** `enrich_paper()` loops
  `for source, client in self.clients.items(): client.enrich(...)` — each call
  is separately rate-limited, so 5 sources ≈ 5 × the slowest source. Fan out
  with a `ThreadPoolExecutor` exactly like `UnifiedSearch._run_sources`
  (the clients are independent and thread-safe for reads).
- **One bad client aborts construction.** Every `__init__` block does
  `except Exception: … raise`. If CrossRef init throws, you get no enricher at
  all. Log and skip, like `UnifiedSearch._get_or_init_clients`.
- **`save_responses=True` by default**, writing `raw_*.json` + `merged_*.json`
  into `<repo>/examples/enrichment_responses/` on *every* call
  (`_save_responses`, path built from `Path(__file__).parents[5]`). A library
  should not write into its own source tree; default this to `False` and, when
  enabled, default the dir to `Path.cwd()` or a temp dir.
- **Unpaywall email.** `enricher` passes `config.unpaywall_email` correctly, but
  `fulltext_client._try_unpaywall_xml` / `_try_unpaywall_pdf` hard-code
  `email="user@example.com"` — against Unpaywall's ToS and rate-limited
  globally. Thread the configured email through.
- **Batch endpoints unused.** OpenAlex (`filter=ids.openalex:…|…`, 50/page),
  Semantic Scholar (`POST /paper/batch`, 500 ids), iCite
  (`?pmids=comma,list`, 1000) and Unpaywall all support batch lookups.
  `BatchEnricher` still calls the single-item `enrich()` in a loop.

---

## 3. XML full-text downloader (`features/fulltext/fulltext_client.py`)

### Current chain (`download_xml_by_pmcid`)

1. cache
2. **Europe PMC REST** `…/PMC{id}/fullTextXML`
3. Europe PMC **FTP OA bulk** `.xml.gz`
4. Europe PMC **`fulltextRepo`** endpoint
5. **Unpaywall** via DOI (but saves a PDF into the `.xml` path — see below)

EPMC-first is correct. Coverage is roughly the PMC OA subset + EPMC preprints.

### Bugs to fix

- **No content sniff before cache.** `_try_xml_rest_api` writes and caches
  `response.text` without checking it is JATS XML — a 200 HTML error page or a
  JSON `{"error": …}` gets cached as `PMC….xml`. Check
  `content-type`/first bytes (`<?xml` / `<article`) before `atomic_write`.
- **`_try_unpaywall_xml` mislabels PDFs.** It follows `url_for_pdf` and writes
  the bytes to the `.xml` path if `content-type` merely *contains* `"pdf"`.
  Split: XML fallbacks write XML; a PDF hit belongs in the PDF chain.
- Hard-coded `email="user@example.com"` (see §2).

### Expansion — additional XML sources (all optional, EPMC still first)

| Order | Source | Endpoint | Adds |
|------:|--------|----------|------|
| after 2 | **PMC OA Web Service** | `https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC…` → tgz with `.nxml` | the parts of the PMC OA subset EPMC's mirror lags on; also bundles figures |
| after 3 | **NCBI E-utilities efetch** | `efetch.fcgi?db=pmc&id=…&rettype=xml` | NCBI's own JATS; different freshness than EPMC |
| after 4 | **BioC-PMC** | `…/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/PMC…/unicode` | full text as BioC XML when JATS isn't released |
| new | **DOI content negotiation** | `GET https://doi.org/{doi}` with `Accept: application/vnd.jats+xml, text/xml` | publisher-hosted JATS for non-PMC articles (base record still from EPMC) |
| new | **bioRxiv/medRxiv API** | `https://api.biorxiv.org/details/biorxiv/{doi}` → JATS/`.xml` | preprint full text keyed by the DOI EPMC gives you |
| new | **PubMed Central FTP "author manuscript"** (`oa_package` vs `manuscript`) | already have the FTP client — also try the `manuscript/` tree | NIHMS author manuscripts not in the OA subset |

Design: a `XmlFetchStrategy` protocol (`name`, `available` (dep/credential
check), `fetch(pmcid_or_doi, out) -> bool`) and an ordered list, EPMC strategies
pinned first. Each new strategy in its own module; the ones needing extra
packages (none of the above do — all are `requests`) or credentials degrade
quietly. Same pattern the search `registry` already uses.

---

## Suggested order of work

1. *(done)* EPMC-as-source validation bug + merger priority.
2. Wire `iCite` into `PaperEnricher`; add `EuropePMCEnrichmentClient`.
3. Parallelise `PaperEnricher`; make client init non-fatal; flip
   `save_responses` default.
4. `UnifiedSearch(primary="europepmc")` enrich-don't-merge mode + per-source
   limits.
5. Full-text: content sniff + PDF/XML split + the `XmlFetchStrategy` refactor,
   then add PMC-OA / efetch / BioC / DOI-negotiation / bioRxiv strategies.
6. Batch enrichment endpoints.
