# Changelog

All notable changes to PyEuropePMC are documented here.

## [Unreleased]

### 💥 Breaking Changes

- **The lxml backend is removed.** `LXMLParser` and `is_lxml_available` are no
  longer exported from `pyeuropepmc.features.fulltext.extensions`.
  `FullTextXMLParser` parses exactly as before. The backend was opt-in, lxml was
  never a declared dependency, and CI never ran its tests. Measured on 36 papers
  it was no faster end to end, and it crashed building structured output for 15
  of them, ran words together, and returned no sections for JATS that uses a
  default namespace.

### 🔒 Security

- **All XML is parsed with defusedxml.** The arXiv and PubMed sources, figure
  extraction, the JATS normalizer, local-file and bioRxiv-manifest parsing and
  the benchmark metrics called the standard-library parser directly. They now
  use defusedxml, as full-text and search-result parsing already did, so a
  document that declares entities is refused instead of expanded. The arXiv,
  PubMed and figure paths treat it like any other unparseable response. Ruff now
  reports any other XML parser (rules S313-S319, and a ban on importing lxml).

### 🐛 Bug Fixes

- **`FigureExtractor` finds the figures.** It searched for elements in the
  JATS1 XML namespace, which Europe PMC documents do not use, so it returned
  nothing for every article: 0 of 25 figures, 8 tables and 19 supplementary
  files across five papers. It now parses through `FullTextXMLParser`, so both
  the DTD-based JATS Europe PMC serves and schema-based JATS in a default
  namespace are matched. The MCP tool `paper_figures`, which reported
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

- **A table or figure inside a paragraph gets a block of its own.** JATS
  allows a `<table-wrap>` or `<fig>` inside a `<p>`, and
  `get_full_text_sections_structured()` folded it into the paragraph block:
  no table or figure block, so the rows and caption were out of reach, and the
  cells ran together with nothing between them. PMC12311175 nests seven tables
  and nine figures that way; its structured output had no table or figure
  block at all, and 703 cell boundaries ran together. The paragraph is now split
  around the element: the text before it, a table or figure block with label,
  caption and rows, then the text after.

- **`to_plaintext()` keeps the cells of such a table apart again**, as 2.0.0
  did. 2.2 built a paragraph's text with a walker of its own that put nothing
  around block-level elements, where `get_text_content()` puts a space, so
  the same 703 boundaries ran together ("miRNARole") and a figure's label ran
  into its caption ("Fig. 1Mechanisms of immune"). Both now use the one walker.

- **A caption's title no longer runs into its text** in the figure and table
  blocks built from it ("Overview of the study.a The workflow"). Eight
  figure captions in PMC12738713 joined that way.

- **The article title and abstract are labelled `section_type="front"`**, not
  `"body"`, so keeping only body sections no longer returns them a second time
  alongside the metadata. `front` is added to `SectionType` in the LinkML
  schema. Code that relied on the old label needs to accept `front`.

### 📚 Documentation

- **The documentation matches the code again.** Audits of README.md and every
  page in docs/ found that most examples raised or used classes, methods,
  parameters and commands that do not exist. Each page was checked against the
  code and rewritten, merged or removed, and every Python example on the
  rewritten pages runs offline against mocked HTTP. README.md is a shorter front
  page whose links work on PyPI; docs/SUMMARY.md lists every page; new pages
  cover error codes, how the docs are published and the XML parser internals;
  `.gitbook.yaml` lets GitBook Git Sync publish docs/. Code defects found on the
  way are documented as known limitations where readers would hit them.

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

For detailed release information, see [docs/development/release-analysis.md](docs/development/release-analysis.md)
