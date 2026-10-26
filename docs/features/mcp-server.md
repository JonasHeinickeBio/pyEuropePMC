# MCP server

`pyeuropepmc-mcp` lets an AI agent search Europe PMC, read papers and export references through the [Model Context Protocol](https://modelcontextprotocol.io/). This page shows how the tools fit together, gives a workflow for the common jobs, and lists the Europe PMC behaviours that the tools work around. The [package README](../../src/pyeuropepmc/mcp/README.md) has the flags, the transports and the reference table of every tool.

## Connect a client

The server is part of the base install. Most clients start it themselves:

```bash
claude mcp add pyeuropepmc -- uvx pyeuropepmc mcp     # Claude Code, no install needed
pyeuropepmc-mcp                                       # stdio, for any client that spawns it
pyeuropepmc-mcp --transport streamable-http           # HTTP at http://127.0.0.1:8000/mcp
```

For Claude Desktop, Cursor and VS Code, add `"command": "pyeuropepmc-mcp"` (or `"command": "uvx"` with `"args": ["pyeuropepmc", "mcp"]`) to the client's MCP configuration; the [README](../../README.md#-mcp-server) shows the file for each. The server has no authentication of its own: keep the HTTP transport on `127.0.0.1` or put an authenticating proxy in front of it. Behind a proxy that forwards its public host name, add `--allowed-host mcp.example.org` (MCP SDK 2.x answers HTTP 421 to unknown `Host` headers).

Two tools need configuration. `find_open_access` reads `UNPAYWALL_EMAIL` (Unpaywall asks for a contact address), and the LLM tools need the `agentic` extra and an `OPENAI_API_KEY`. A tool whose dependency is missing stays in the tool list and answers with the `pip install` line it needs.

## Which tool for which job

| You want to | Use |
|---|---|
| Check a query before running it | `validate_query`, then `count_papers` |
| Write a query from parts | `build_query` |
| Turn a research question into a query | `pico_decompose` (PICO, PICOS, PICOT, SPIDER), then `mesh_expand` |
| See how a search is distributed over years, journals, authors, countries, funders and open access | `analyze_search` (exact counts where Europe PMC can count, a labelled sample otherwise) |
| Run the same search on PubMed or another database | `translate_query` |
| Test a query against papers you already know | `evaluate_query` |
| Search | `search_papers` (Europe PMC), `unified_search` (several sources, duplicates merged), `search_authors` |
| Look up papers you have identifiers for | `get_paper_details` (one), `get_papers_batch` (up to 100) |
| See impact, funders, institutions and retractions of one paper | `enrich_paper` |
| Read a paper | `get_paper_fulltext`, `get_papers_fulltext_batch`, `paper_figures` |
| Pull the methods, results or limitations out of a paper whatever its headings say | `tag_paper_sentences` |
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

### From a question to a search

```text
pico_decompose  question="In adults with type 2 diabetes, does metformin reduce cardiovascular mortality compared with placebo?"
mesh_expand     terms=["type 2 diabetes", "metformin"]
```

`pico_decompose` splits a question into PICO, PICOS, PICOT or SPIDER elements and builds a query from them, with no model, key or request. Each element is a verbatim piece of the question with its position (`start`, `end`), so you can check it; an element the question does not state is listed in `missing` (required for the framework) or `optional_missing`, never filled in. The query is an AND of one group per element and is checked with the same linter as `validate_query` (`query_check`). By default it uses the population (the condition, not the demographics: `adults with type 2 diabetes` becomes `"type 2 diabetes"`) and the intervention, because outcome and comparison terms are rarely indexed and cut recall; `query_elements` chooses others, and `mesh=true` replaces the terms it knows with MeSH groups.

| Framework | Complete when it has |
|---|---|
| `PICO` | population, intervention, outcome (comparison is optional) |
| `PICOS` | those and a study design |
| `PICOT` | those and a time frame |
| `SPIDER` | sample, phenomenon of interest, evaluation (design and research type are optional) |

The rules know the usual clinical phrasings: `In P, does I reduce O compared with C?`, `What is the effect of I on O in P?`, `Is I more effective than C for O?`, `Is I associated with O?`, `Effectiveness of I for O in P` and `P treated with I`. A question phrased another way is understood only in part, and the answer says so in `notes` and `missing`: ask the user to restate it before relying on the query. `Is I effective for X?` reads X as the outcome; if X is the condition treated, it belongs to the population.

Measured on 36 gold questions (`tests/fixtures/pico`, `benchmarks/evaluate_pico_parser.py`), counting only elements the question states:

| Question set | Rules, found exactly | Older parser (`features.review.pico`), found exactly |
|---|---|---|
| 12 questions used while writing the rules | 39 of 39 | 2 of 39 |
| 12 questions written before the rules and run once afterwards | 39 of 39 | 2 of 39 |
| 12 questions phrased outside the patterns | 11 of 28 | 1 of 28 |

The rules never extracted text that is not in the question and never filled an element the question leaves out (0 of 46 unstated elements on the three sets). The second set was written by the same person as the rules, so it shows that the patterns are not fitted to the first set, not how it fares on questions from elsewhere; the third set is the realistic warning: outside the known phrasings fewer than half of the elements are found. The older parser takes the rest of the sentence for each element, so its elements overlap and its query contains words such as `does` and `with`; the MCP tool does not use it.

`mesh_expand` returns, for each term, the MeSH descriptor (ID, heading, tree numbers), its entry terms and a ready fragment such as `(MESH:"Diabetes Mellitus, Type 2" OR "Diabetes Mellitus, Type 2" OR "type 2 diabetes" OR "NIDDM" ...)`, and joins the fragments with AND (or OR, `combine="or"`) into a query that is checked like `validate_query`. By default it works offline from a snapshot of 244 common clinical headings (conditions, drugs, interventions, populations, outcomes and study designs) taken from NLM's published MeSH, with entry terms and tree numbers as NLM lists them. A term that is not in the snapshot comes back with `matched: false` and is searched as written; nothing is guessed. `use_api=true` asks the NLM MeSH service instead (up to four requests per term, so it needs the network and takes longer) and covers all of MeSH; a request that fails, or a term not reached within `time_budget` (30 seconds for the whole call, 2 to 120), is reported for that term and does not fail the call. Europe PMC's `MESH:` field is much narrower than PubMed's MeSH index (3,477 hits for `MESH:"Diabetes Mellitus, Type 2"` against 561,715 for the phrase `"type 2 diabetes"`), which is why each fragment also searches the heading and the entry terms as phrases. `scripts/build_mesh_snapshot.py` rebuilds the snapshot from the NLM service.

### Aggregates over a search

```text
analyze_search  query="malaria", date_from="2015", date_to="2024"
analyze_search  query="CRISPR AND TITLE:therapy", metrics=["by_year", "open_access"]
analyze_search  query="malaria", metrics=["journals", "funders"], limit=1000, sort="CITED desc"
```

`analyze_search` answers "how is this search distributed?" without returning thousands of records. Every metric says in `basis` where its numbers come from, because Europe PMC can count some things over the whole result set and the rest has to be read off records:

| Metric | `basis` | How |
|---|---|---|
| `by_year` | `exact` | One count per first-publication year (`FIRST_PDATE:[Y TO Y]`), from the oldest to the newest record. A span of more than 60 years is counted for its latest 60 years plus one `before` bucket. `undated` is what the years do not account for, so years + `before` + `undated` is `hit_count` |
| `open_access` | `exact` | Open-access and other records, and the share |
| `citations` `thresholds` | `exact` | Records cited at least 1, 10, 100 and 1,000 times (`CITED:[n TO *]`) |
| `citations` `statistics`, `journals`, `authors`, `types`, `countries`, `funders` | `sample` | Computed with the library's analytics functions from the first `limit` records of the search, in relevance order or the order `sort` gives. They describe those records only: the journals of the first 500 hits are not the journals of 120,000 |

When `limit` is at least `hit_count` the records are the whole result and the sample metrics are `exact` too. Otherwise the response has a `sample_note` that says how many records of how many were read. On a live search for `malaria` from 2015 to 2024 (22 October 2026), `hit_count` was 123,390, `by_year` summed to exactly 123,390 and 89,994 records were open access, while the sample of 200 records had 42 articles in *Malaria Journal*: a statement about those 200 records, not about the decade.

The sample metrics need `pip install "pyeuropepmc[analytics]"` (pandas and numpy); without it the call fails before any request and says so, while `by_year` and `open_access` work in a core install. `countries` takes the last comma-separated part of each affiliation, so a record without an affiliation is not counted and a few countries may be misread; `types` counts a record once per type it has, and Europe PMC types a record differently by source (`Journal Article` for MEDLINE records, `research-article` for PMC ones). `lite` records are read unless `countries` or `funders` is asked for, which need `core` records.

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

### Pull the methods or results of a paper

```text
tag_paper_sentences  pmcid="PMC8658482", roles=["method"], sections=["methods"]
tag_paper_sentences  doi="10.3390/jcm10235527", roles=["result", "limitation"]
```

`tag_paper_sentences` splits the body of an open-access paper into sentences and says what each one does: `background`, `motivation` (aim, hypothesis, gap), `method`, `result`, `claim` (the authors' interpretation), `limitation` or `conclusion`. Front matter, the reference list, figure and table captions and administrative sections (acknowledgments, funding, conflicts of interest, ethics and consent statements) are left out. It uses the same download and cached XML as `get_paper_fulltext`. `roles` and `sections` filter what is returned (`statistics` always counts the whole body), sentences come in reading order and are never cut, and `truncated` says whether `max_chars` left some out. A sentence no rule is sure about is `unknown`; `min_confidence` raises the bar further.

It uses rules, not a model: the section a sentence is in gives its default role (methods describe what was done, results what was found) and cues in the sentence move it where a section mixes roles (a discussion restates results, cites earlier work, admits limits). The older `RhetoricalHighlighter` of the library has keyword rules written for computer-science papers; it labelled 13 of the 93 test sentences correctly, so the tool does not use it. `use_llm=true` asks the configured LLM about up to 40 sentences the rules left `unknown` (it needs the `agentic` extra and a provider like the other LLM tools, and the sentences are sent to it); that path is tested with a fake client only.

Measured on 93 sentences from three open-access papers (a retrospective cohort, a yeast study, a randomized trial), labelled by hand by one annotator (`tests/fixtures/rhetoric`, `benchmarks/evaluate_rhetoric_roles.py`):

| Role | Given | Precision | Gold | Recall |
|---|---|---|---|---|
| background | 18 | 0.94 | 20 | 0.85 |
| motivation | 3 | 1.00 | 4 | 0.75 |
| method | 16 | 1.00 | 17 | 0.94 |
| result | 26 | 0.92 | 26 | 0.92 |
| claim | 12 | 0.92 | 13 | 0.85 |
| limitation | 6 | 1.00 | 7 | 0.86 |
| conclusion | 5 | 1.00 | 6 | 0.83 |

82 of the 93 sentences got the right role and 7 were `unknown`. By set: 43 of 46 on the sentences used while writing the rules, 22 of 23 on a paper labelled before the rules were run, and 17 of 24 on a harder sample of introduction, results and discussion sentences labelled before the rules saw them. The discussion is the hard part: a sentence there with no cue at all is `unknown`, because guessing `background` was right in only 2 of 7 such cases. The test set is small and one person labelled it and wrote the rules, so read the table as what the rules can do on ordinary biomedical papers, not as a guarantee; the precision of a role on your papers may be lower.

A paper without recognisable headings (a letter, a short report) has no section to start from. Then only the sentence cues work, and only the roles they were precise for are returned: on the same 93 sentences `background` (17 of 22 given) , `method` (6 of 7) and `conclusion` (3 of 3); result, claim, limitation and motivation stay `unknown` (61 of 93 sentences), and the answer carries a note saying so.

### Impact, funding and retractions

```text
enrich_paper  doi="10.1016/S0140-6736(97)11096-0", include=["updates", "impact"]
enrich_paper  pmid="26017442", sources=["crossref", "openalex"], time_budget=20
```

`enrich_paper` asks Europe PMC, Crossref, OpenAlex, Semantic Scholar and iCite (and Unpaywall once `UNPAYWALL_EMAIL` is set) at the same time and merges their answers into one record of a few kilobytes, usually in two seconds (see [how long it takes](#how-long-enrich_paper-takes)). `ror_details=true` adds each institution's city, country code, website and coordinates from ROR, at about 0.3 seconds per distinct institution. `include` picks the groups: `impact`, `funding`, `affiliations`, `oa` and `updates`. `updates` lists correction and retraction notices from Crossref and Europe PMC and sets `is_retracted`; it means that no retraction notice was found there, not that none exists anywhere.

Look at `sources` before trusting a gap. Each source is `ok`, `empty` (it answered without data), `error` (with the reason, for example a Semantic Scholar rate limit), `timeout` (still running when `time_budget` ended, 30 seconds by default) or `unavailable` (the extra or e-mail address it needs is missing). `complete` is true only when every source answered. A failed source gives a partial record, never an error.

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

## Resources and prompts

Clients that support MCP resources can attach a paper without asking the model to call a tool: `epmc://paper/PMC3525259` is its Markdown full text, `epmc://paper/PMC3525259/outline` its sections with sizes and `epmc://paper/PMC3525259/references` its parsed reference list. Each runs the same code as `get_paper_fulltext`, so an article that is not open access fails with the same "not Open Access" message, and the text is cut at the same 30,000 characters (the end of a cut text names the call that returns a section). They are URI templates: a client lists them with `resources/templates/list`. A search as a resource (`epmc://search/{query}`) is deliberately not offered; `search_papers` takes the query as a typed argument instead of encoding it into a URI.

Three prompts encode workflows that would otherwise be improvised. They name only tools of this server, and a test checks every tool and parameter they mention against the live tool list.

```text
literature_review  topic="statins and dementia", years="2018-2024", max_papers=15
critical_appraisal pmcid="PMC3525259"
citation_trace     pmid="22745249", direction="backward"
```

`literature_review` sizes the topic with `count_papers`, searches, screens by title and abstract with the dropped papers listed, reads the selected papers with `get_paper_fulltext`, and writes a review that cites every claim and ends with the counts. `critical_appraisal` reads the outline, methods and results of one open-access paper, collects the limitations its authors state with `tag_paper_sentences`, checks funders and retractions with `enrich_paper`, and ends with a verdict. `citation_trace` follows the references and citations of a PMID and inspects the most cited neighbours.

## Running it as a network service

stdio, the default, needs no protection: the client starts the process and owns its pipes. The `streamable-http` and `sse` transports open a port, and then anyone who can reach it can call every tool, which means spending your Europe PMC, Crossref and OpenAlex quota, filling the server's caches, and (with `OPENAI_API_KEY` set) running the LLM tools on your key. The tools themselves are read-only and write nothing on the server's disk except the caches.

**Safe defaults.** The server binds to `127.0.0.1` and has no token until you set one. If you bind to another address without a token it logs a warning at startup. stdio ignores tokens.

**Bearer token.** Authentication is a bearer token checked on every HTTP request, before the MCP server sees it:

```bash
( umask 077; pyeuropepmc-mcp --generate-token > /etc/pyeuropepmc/mcp.token )   # 256 random bits, never world-readable
pyeuropepmc-mcp --transport streamable-http --host 0.0.0.0 --auth-token-file /etc/pyeuropepmc/mcp.token
```

A client sends `Authorization: Bearer <token>`; any other request, including a missing, malformed or wrong header, gets HTTP 401 with `WWW-Authenticate: Bearer` and the same body whatever the reason. The server logs the refused method and path, never a token. Tokens are compared in constant time. The token goes in a file (`--auth-token-file`, one token per line, `#` comments) or in `PYEUROPEPMC_MCP_AUTH_TOKEN` (comma separated); there is no command-line value because `ps` shows it to every user. A token must be at least 16 printable characters without spaces, and a variable or file that is set but empty is an error: a typo cannot turn into an open server.

**Rotation.** Several tokens are accepted at once. Add the new token on a second line, restart, move the clients over, then remove the old one and restart.

**Behind a proxy.** Terminate TLS in the proxy (the server speaks plain HTTP), forward to `127.0.0.1:8000`, and add `--allowed-host mcp.example.org` for the public name (SDK 2.x). With the token on, the proxy can pass the `Authorization` header through unchanged; if the proxy authenticates users itself (OAuth, mTLS, an identity-aware proxy) you can leave the token off and keep the server on loopback.

**What this does not do.** It is one shared secret, not per-user identity: every holder has the same access, nothing is rate limited per client, and a token sent over plain HTTP can be read on the wire, so use TLS. It is not OAuth; clients that insist on an OAuth flow need a proxy that provides it. Resources and prompts go through the same checks as the tools.

## What Europe PMC does that the tools work around

These were measured against the live service in October 2026. The tools handle them for you; they are listed so that the results make sense.

- **Queries are never rejected.** See above; `validate_query` exists for this reason.
- **A leading wildcard** (`*cancer`) gives HTTP 503. `validate_query` flags it.
- **Full text of a paper outside the open-access set** gives HTTP 500 after about 20 seconds, which looks like an outage. The tools look at the open-access flag first and answer at once with the real reason.
- **`CITES:` works with PMIDs only.** `build_query(cites=...)` takes a PMID for that reason.
- **The Annotations API** returns between one and eight articles per page for an entity search, and ignores the type, provider and section filters, so the tools apply those filters themselves.
- **`labsLinks` ignores its provider filter** and `datalinks` ignores its page size. `get_paper_lab_links` and `get_paper_data_links` filter and limit on the server side.
- **Unknown identifiers** get an empty answer with HTTP 200 from the link services. Identifiers are checked before the request, and a paper without links gives an empty list, which is a valid result.

## How long `enrich_paper` takes

Measured on 21 October 2026 with `benchmarks/benchmark_enrich_paper.py`: three papers (a retracted paper with 24 authors, a three-author paper from a DOI, an open-access paper), three calls each, one at a time against the live services. One Linux machine, Python 3.10, no API keys and no e-mail addresses configured (so Semantic Scholar, OpenAlex and Crossref ran without their polite or authenticated pools), no caching. Public services vary by network and by day: read these as the order of magnitude, not as a guarantee. Run the script to measure your own setup.

**Time of a whole call**, in seconds, median (fastest to slowest of 9 calls). Every call also asks Europe PMC, which resolves the identifier first; that lookup takes about 1.4 s of every figure below.

| Sources asked | Call | Answer size |
|---|---|---|
| Europe PMC only | 1.8 (1.7 to 4.9) | 3.0 KB (the merged record, without the tool's framing) |
| + Crossref | 1.7 (1.7 to 3.7) | 2.9 KB |
| + OpenAlex | 1.9 (1.7 to 31.9) | 4.4 KB |
| + Semantic Scholar | 1.8 (1.7 to 4.5) | 1.8 KB |
| + iCite | 1.9 (1.6 to 4.2) | 1.8 KB |
| **All sources (default)** | **2.0** (1.6 to 74.4) | 5.6 KB |
| All sources + `ror_details` | 5.3 (1.9 to 32.3) | 7.8 KB |

The sources run at the same time, so asking for all of them costs about as much as the slowest one, not their sum. Adding a source mostly adds data, not time. The answer is 2 to 8 KB, well under 15 KB; the size depends on the number of authors, institutions and funders more than on the sources.

**Time of each source** inside those calls (its own request, seconds, median and range over 9 to 63 calls):

| Source | Median | Range |
|---|---|---|
| Europe PMC | 0.4 | 0.4 to 33.7 |
| Crossref | 0.1 | 0.1 to 35.8 |
| iCite | 0.3 | 0.1 to 36.2 |
| OpenAlex | 0.4 | 0.3 to 73.0 |
| Semantic Scholar | 0.4 | 0.3 to 2.9 |
| ROR (`ror_details`) | about 0.3 per distinct institution | 0.1 to 0.3 s for 1 institution, 1.3 to 1.7 s for 5, 3.4 to 7.4 s for 12 |

**ROR details cost about 0.3 s per distinct institution.** For the three papers the median call went from about 2 s to 3.6, 4.0 and 5.4 s. A later single pass (one call per paper) gave 8.5 s as the median with ROR, with the ROR step between 0.3 and 6.7 s, so expect a few seconds with a wide spread. The lookup runs once, after the merge, and each institution is fetched once however many authors share it (the retracted paper has 13 author-institution pairs but one institution, so one request). An earlier version fetched every institution twice, once inside the OpenAlex client and once in the enricher, and once per author-institution pair inside OpenAlex: 14 ROR requests for the retracted paper instead of 1, 29 instead of 12 for the open-access paper, and a median of 8.4 s instead of 5.3 s with ROR on.

**Slow outliers.** 4 of the 72 calls (the 63 of the first pass and 9 repeats of the ROR row after the change) had a source wait 30 to 36 s before it answered: OpenAlex in all four and, in one of them, Europe PMC, Crossref and iCite as well (74 s in all). The cause is the measuring machine, not the services: it has no working IPv6 route, and a Python client tries the IPv6 address of a host first and waits for it to time out before it tries IPv4 (Python waited 61 s for NLM's service, forcing IPv4 made the same request take 1.1 s, and `curl` falls back at once and took 0.6 s). It hits any host that has an IPv6 address; most of the calls above were fast because a connection that is reused is not delayed again, and OpenAlex was the host most often affected. With the default `time_budget` of 30 s such a call is reported as `timeout` for the sources still waiting, and the rest of the record is returned. These measurements predate the connection fallback: since then the clients start the IPv4 address 0.25 s after the IPv6 one and use whichever connects first (see the [FAQ](../getting-started/faq.md#why-is-the-first-request-to-a-service-30-to-60-seconds-slow-and-later-ones-fast)), so such a stall no longer happens in the clients' own sessions. If you still see `timeout` entries, raise `time_budget` (up to 120) if you would rather wait than get a partial record.

**Failures.** Semantic Scholar did not know the DOI-only paper and answered "not found" in all 9 calls for it, which shows up as `error` in `sources` and does not affect the rest. No rate limit (HTTP 429) occurred in these calls without an API key; if one does, the source shows `error` with the reason and the record is partial.

**Cost control.** Pass `sources` to leave out sources you do not need, keep `ror_details` off unless you want an institution's place or website, and lower `time_budget` for an interactive answer. A slow request that misses the budget keeps its worker thread until it ends; each enricher allows at most four requests per source in flight, so repeated calls against a stalled service queue up, and are reported as `timeout`, instead of starting more threads.

## When something fails

Call `epmc_status` first. It makes one request to each of the four endpoints the tools depend on (search, full text, citations, annotations) and answers `ok`, `degraded`, `down` or `unknown` with the HTTP status and the time of each. The answer is kept for 30 seconds, so asking again does not add load to a service that may be struggling. If Europe PMC is healthy and a result looks stale, `cache_status` shows the hit rate of the in-memory caches and `clear_cache` empties one of them (`search`, `article`, `annotations`, `xml` or `all`); nothing on disk is touched.

A failed call comes back with `isError: true` and a message that names the cause. In the batch tools, a failure for one identifier does not fail the call: every input gets its own status in the order it was given.

## Limits

| Tool | Limit |
|---|---|
| `analyze_search` | `limit` 1 to 1,000 records (500 by default) for the sample metrics; `top_n` 1 to 100; one count request per year for `by_year`, at most 61 |
| `get_papers_batch` | 100 identifiers per call, looked up 50 at a time |
| `get_papers_fulltext_batch` | 20 papers, within `max_chars_per_paper` and `max_total_chars` |
| `evaluate_query` | 200 included and 200 excluded PMIDs |
| `pico_decompose` | questions up to 2,000 characters; offline |
| `tag_paper_sentences` | `max_chars` 1,000 to 500,000 (30,000 by default), whole sentences; `use_llm` looks at 40 sentences at most |
| `mesh_expand` | 20 terms per call; offline unless `use_api` is set |
| `enrich_paper` | `time_budget` 2 to 120 seconds (30 by default); at most 30 authors, 20 funders and 20 notices in the answer; at most four requests per source in flight |
| `export_papers` | 1,000 records per call; continue with `skip` or the `remaining` ids |
| `find_papers_by_entity` | 1 to 8 articles per page, continued with `cursor` |
| `get_paper_fulltext` | `max_chars` up to 500,000 |
