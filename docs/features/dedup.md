# Deduplication with LiteratureMerger

`LiteratureMerger` combines records from several sources into one list. It removes retracted and non-paper entries, groups records that share identifiers, finds remaining duplicates by PMID, DOI and fuzzy title matching, and merges each duplicate's fields into the record it keeps. `UnifiedSearch` and `CitationWalker` use it internally.

```python
from pyeuropepmc.features.enrich.merger import DedupConfig, DedupMode, LiteratureMerger
```

## Quick start

```python
from pyeuropepmc.features.enrich.merger import DedupConfig, DedupMode, LiteratureMerger

pubmed = [
    {"title": "CRISPR screens identify cancer dependencies", "doi": "10.1000/crispr.1", "pmid": "111",
     "authors": [{"name": "Smith, John"}], "publication_year": 2021, "journal": "Nature", "source": "pubmed"},
    {"title": "Metformin and cardiovascular outcomes in type 2 diabetes", "doi": "10.1000/met.2", "pmid": "222",
     "authors": [{"name": "Doe, Jane"}], "publication_year": 2020, "journal": "Lancet", "source": "pubmed"},
    {"title": "Retracted: A flawed study", "pmid": "333", "publication_year": 2019, "source": "pubmed"},
]
europepmc = [
    {"title": "CRISPR screens identify cancer dependencies.", "doi": "https://doi.org/10.1000/CRISPR.1",
     "pmcid": "PMC999", "authors": [{"name": "Smith, John"}], "publication_year": 2021, "journal": "Nature",
     "citation_count": 42, "source": "europepmc"},
    {"title": "Table of Contents", "publication_year": 2021, "source": "europepmc"},
]
arxiv = [
    {"title": "Metformin and cardiovascular outcome in type 2 diabetes", "authors": [{"name": "Doe, Jane"}],
     "publication_year": 2020, "source": "arxiv"},
]

merger = LiteratureMerger(config=DedupConfig(mode=DedupMode.BALANCED))
merged, report = merger.merge_results([pubmed, europepmc, arxiv])

print(report.summary())
# {'total_input': 6, 'total_output': 2, 'duplicates_removed': 4, 'dedup_rate': 0.6667,
#  'by_match_level': {'PMID_EXACT': 1, 'NON_PAPER': 1, 'DOI_EXACT': 1, 'FUZZY_TITLE': 1}}
for record in report.records:
    print(record.match_level.name, record.removed_source, "->", record.kept_source, "|", record.reason)
for paper in merged:
    print(paper["source"], paper["title"], paper.get("dedup_id"))
```

`merge_results(results_list)` takes a list of record lists, one per source, and returns `(merged_records, report)`. `LiteratureMerger(config=None)` uses `DedupConfig()` when no configuration is given; the mode is set on the configuration, not on the merger.

## Input records

Records are dicts; `LiteratureResult.model_dump()` produces a suitable one. The merger reads:

| Keys | Used for |
|---|---|
| `doi`, `pmid`, `pmcid`, `arxiv_id` or `arxiv`, `mag_id`, `who_covidence_id` or `covidence_id`, `external_ids` | Identifier matching |
| `title`, `publication_year`, `authors` (dicts with `name` as `"Last, First"`, or strings), `journal` | Fuzzy matching |
| `source` | Source priority |
| `license`, `is_oa`, `oa_status`, `pmcid`, `fulltext_url`, `pdf_url`, `oa_url`, `has_fulltext`, `abstract` | Choosing the record to keep in an identifier group |
| `title`, `journal`, `status`, `retraction` | Retraction detection |

## Pipeline

`merge_results()` runs these steps in order:

1. **Retracted records** (`remove_retracted`): records whose title, journal, `status` or `retraction` value, or a value in their raw source payload, contains "retracted", "retraction" or "withdrawn" are removed.
2. **Non-paper entries** (`filter_non_papers`): titles such as "Table of contents", "Index", "Editorial board", "Instructions for authors", "Cover image", "In memoriam", "Obituary" or "Correction to" are removed.
3. **Identifier groups** (`use_identifier_dedup`): records that share any DOI, PMID, PMCID, arXiv, MAG or WHO/Covidence identifier are grouped. Each group keeps one record and merges the others into it.
4. **PMID match**: records with the same PMID.
5. **DOI match**: records with the same normalized DOI.
6. **Fuzzy title match**: titles with a `SequenceMatcher` similarity at or above the threshold, published within `year_window` years of each other, subject to the author and journal checks of the mode. Titles where only one has a part marker such as "Part II" or "Supplement 1" have their similarity reduced.

## Modes

| Mode | Title similarity threshold | Author overlap required | Same journal required |
|---|---|---|---|
| `DedupMode.BALANCED` (default) | 0.90 | yes | no |
| `DedupMode.FOCUSED` | 0.80 | no | no |
| `DedupMode.RELAXED` | 0.95 | yes | yes |

Author overlap means that at least 30% of the combined author surnames are shared. Both checks pass when either record has no authors or no journal.

## DedupConfig

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `DedupMode` | `DedupMode.BALANCED` | Sets the threshold and checks below when they are `None` |
| `fuzzy_threshold` | `float` or `None` | `None` | Title similarity threshold, 0.0 to 1.0 |
| `year_window` | `int` | `2` | Maximum difference in publication year for a fuzzy match |
| `remove_retracted` | `bool` | `True` | Step 1 |
| `source_priority` | `dict[str, int]` or `None` | `None` | Replaces `SOURCE_PRIORITY` |
| `field_preferences` | `dict` or `None` | `None` | Replaces the field-level merge rules |
| `require_author_overlap` | `bool` or `None` | `None` | Author check for fuzzy matches |
| `require_journal_overlap` | `bool` or `None` | `None` | Journal check for fuzzy matches |
| `keep_provenance` | `bool` | `True` | Record in `_provenance` which source supplied merged fields |
| `use_identifier_dedup` | `bool` | `True` | Step 3 |
| `strict_identifier_conflicts` | `bool` | `False` | Do not group records that share one identifier but disagree on another |
| `prefer_open_access` | `bool` | `True` | Use licence and full-text availability when choosing the record to keep |
| `filter_non_papers` | `bool` | `True` | Step 2 |
| `persist_dedup_ids` | `bool` | `True` | Add a `dedup_id` to records kept from identifier groups |

```python
from pyeuropepmc.features.enrich.merger import DedupConfig, DedupMode, LiteratureMerger

config = DedupConfig(mode=DedupMode.FOCUSED, fuzzy_threshold=0.85, year_window=5, strict_identifier_conflicts=True)
merger = LiteratureMerger(config=config)
print(merger.config.fuzzy_threshold, merger.config.require_author_overlap)  # 0.85 False
```

## Identifier groups

```python
from pyeuropepmc.features.enrich.merger import deduplicate_by_identifier

papers = [
    {"doi": "10.1000/a", "pmid": "1"},
    {"doi": "10.1000/b"},
    {"doi": "10.1000/a", "pmid": "2"},
    {"pmcid": "PMC5"},
]
print(deduplicate_by_identifier(papers))                         # [[0, 2], [1], [3]]
print(deduplicate_by_identifier(papers, strict_conflicts=True))  # [[0], [1], [2], [3]]
```

`deduplicate_by_identifier(papers, strict_conflicts=False)` returns groups of list indices. With `strict_conflicts=True`, records 0 and 2 stay apart because their PMIDs differ.

In each group the record to keep is the one with the highest licence score, then the most full-text availability (PMCID, full-text or PDF URL, open-access flag, abstract), then the highest source priority. With `prefer_open_access=False` only source priority counts. The kept record receives a `dedup_id` such as `CORD-87685AEB21211374`, derived from the group's identifiers; records without duplicates get none.

Known limitation: CC-BY-SA, CC-BY-NC and CC-BY-ND licences receive the same score as CC-BY.

## Source priority

`SOURCE_PRIORITY` in `pyeuropepmc.features.enrich.merger` ranks sources when choosing a record to keep and when field values disagree:

```text
europepmc 110, pubmed 100, crossref 90, openalex 80, semanticscholar 70, icite 65, unpaywall 60,
arxiv 50, core 45, doaj 40, hal 40, zenodo 35, dblp 30, clinicaltrials 30, unknown 10
```

Pass `DedupConfig(source_priority={...})` to change it. `UnifiedSearch` raises its primary source above all others.

## MergeReport

| Member | Type | Content |
|---|---|---|
| `total_input`, `total_output` | `int` | Record counts before and after |
| `records` | `list[MergeRecord]` | One entry per removed record |
| `metadata` | `dict` | `identifier_groups` and `deduped_papers` when step 3 grouped records; `UnifiedSearch` adds its own keys |
| `duplicates_removed` | `int` property | `len(records)` |
| `dedup_rate` | `float` property | `duplicates_removed / total_input` |
| `summary()` | `dict` | `total_input`, `total_output`, `duplicates_removed`, `dedup_rate` (4 decimals) and `by_match_level` |

`by_match_level` counts records by `MatchLevel` name: `PMID_EXACT`, `DOI_EXACT`, `PMCID_EXACT`, `ARXIV_EXACT`, `IDENTIFIER_MATCH`, `FUZZY_TITLE` or `NON_PAPER`. Known limitation: removed retracted records are counted as `PMID_EXACT`, with the reason `"Retracted paper"`.

`MergeRecord` fields:

| Field | Type |
|---|---|
| `kept_index`, `removed_index` | `int` or `None`, `int` |
| `match_level` | `MatchLevel` |
| `reason` | `str`, for example `"Duplicate by fuzzy title (±2yr, sim=0.991)"` |
| `kept_source`, `removed_source` | `str` or `None` |
| `kept_title`, `removed_title` | `str` or `None` |
| `similarity_score` | `float` or `None`; set for fuzzy matches |

## Provenance

With `keep_provenance=True`, a kept record that received values from a duplicate carries `_provenance`, a dict mapping each such field to the source it came from, for example `{"pmid": "pubmed"}`.

## PaperMatcher

`PaperMatcher` checks records one at a time against those it has already seen, for streams of records:

```python
from pyeuropepmc.features.enrich.merger import PaperMatcher

matcher = PaperMatcher(fuzzy_threshold=0.85, require_author_overlap=True)
incoming = [
    {"title": "Metformin and cardiovascular outcomes in type 2 diabetes", "doi": "10.1000/met.2",
     "authors": [{"name": "Doe, Jane"}], "publication_year": 2020},
    {"title": "Metformin and cardiovascular outcome in type 2 diabetes",
     "authors": [{"name": "Doe, Jane"}], "publication_year": 2020},
]

kept = []
for paper in incoming:
    is_duplicate, level = matcher.match(paper)
    if not is_duplicate:
        kept.append(paper)
    print(is_duplicate, level.name)
# False NO_MATCH
# True FUZZY_TITLE
```

`PaperMatcher(fuzzy_threshold=0.90, year_window=2, require_author_overlap=True, require_journal_overlap=False)` checks PMID, then DOI, then fuzzy title. `match(paper)` returns `(is_duplicate, MatchLevel)` and remembers the record; `deduplicate(papers)` returns the records that are not duplicates. It does not group identifiers, filter retractions or merge fields.

`LiteratureMerger.merge(papers)` deduplicates a single list and returns only the merged records.

## See also

- [Multi-source search](multi-source-search.md)
- [Citation graph walking](citation-walking.md)
