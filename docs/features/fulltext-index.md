# Full-text index (SQLite FTS5)

`FullTextIndex` stores paper metadata and text in a local SQLite database and searches it with SQLite's FTS5 full-text engine. Use it to search papers you have already downloaded or parsed, without calling a web service.

## Create an index and add papers

```python
from pyeuropepmc.features.fulltext import FullTextIndex, IndexEntry

index = FullTextIndex(":memory:")

rowid = index.add(
    IndexEntry(
        doi="10.1000/example",
        pmid="12345678",
        title="My Research Paper",
        authors="Smith, John; Doe, Jane",
        abstract="This paper discusses biomarkers for chronic fatigue syndrome.",
        year=2025,
        journal="Journal of Medical Research",
        source="europepmc",
    )
)
added = index.add_many(
    [
        IndexEntry(doi="10.1000/1", title="Paper 1", abstract="CRISPR screening of biomarkers"),
        IndexEntry(doi="10.1000/2", title="Paper 2", abstract="Unrelated"),
    ]
)
print(rowid, added, index.count())
```

Output:

```text
1 2 3
```

- `add()` returns the row ID of the new document. If the index already holds the document, `add()` stores nothing and returns the stored row's ID. A stored row is the same document when it has the entry's PMID; for an entry without a PMID, its DOI; for an entry with neither, its `source_id`. An entry with none of the three is always added. Use `update()` to replace a document.
- `add_many()` adds the entries one at a time, logs and skips an entry that fails, and returns the number added, not counting entries already in the index.
- `FullTextIndex()` without a path opens `~/.pyeuropepmc/fts_index.db`, creating the directory and file if needed. Pass a file path to choose the location, or `":memory:"` for an index that disappears when it is closed.

## Search

```python
results = index.search("biomarkers")
print(index.count("biomarkers"), "matches")
for hit in results:
    print(hit.rowid, hit.title, "|", hit.snippets["abstract"])
```

Output:

```text
2 matches
2 Paper 1 | CRISPR screening of <b>biomarkers</b>
1 My Research Paper | This paper discusses <b>biomarkers</b> for chronic fatigue syndrome.
```

`search()` returns a list of `SearchResult`, ordered by FTS5 `rank` (lower is more relevant). The query uses [FTS5 query syntax](https://www.sqlite.org/fts5.html#full_text_query_syntax); the index tokenizes with `porter unicode61`, so matching ignores case and English word endings ("expressions" matches "expression").

```python
print([hit.title for hit in index.search('"chronic fatigue syndrome"')])  # phrase
print([hit.title for hit in index.search("biomarker*")])                  # prefix
print([hit.title for hit in index.search("biomarkers NOT CRISPR")])       # boolean
print([hit.title for hit in index.search("title:Paper")])                 # one column
```

Output:

```text
['My Research Paper']
['Paper 1', 'My Research Paper']
['My Research Paper']
['Paper 2', 'Paper 1', 'My Research Paper']
```

The searchable columns are `title`, `abstract`, `full_text`, `authors`, `journal`, `doi`, `pmid`, `pmcid` and `source`. A query with invalid syntax logs an error and returns `[]`.

`search(query, limit=25, offset=0, highlighted=True)`:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | FTS5 query |
| `limit` | `int` | `25` | Maximum number of results |
| `offset` | `int` | `0` | Results to skip, for paging |
| `highlighted` | `bool` | `True` | Fill `snippets`; with `False` it is `{}` |

`SearchResult` fields:

| Field | Type | Description |
|---|---|---|
| `rank` | `float` | FTS5 rank; lower is more relevant |
| `title`, `abstract`, `authors`, `journal` | `str` | Stored values |
| `doi`, `pmid`, `pmcid`, `source` | `str` | Stored values |
| `year` | `int \| None` | Publication year |
| `citation_count` | `int` | Citation count |
| `snippets` | `dict[str, str]` | Keys `title`, `abstract` and `authors`: excerpts of up to 40 tokens from those columns, with matches wrapped in `<b>`…`</b>` |
| `rowid` | `int` | Row ID, as used by `get()` and `delete()` |

`count(query=None)` returns the number of documents, or the number matching `query`.

## Look up, update and delete

```python
record = index.get_by_doi("10.1000/example")
print(record["title"], record["year"], record["id"])

replaced = index.update(
    IndexEntry(doi="10.1000/1", title="Updated Title", abstract="CRISPR screening of biomarkers")
)
print(replaced, [(hit.rowid, hit.title) for hit in index.search("CRISPR")])

print(index.delete(rowid), index.delete(rowid), index.count())
print(index.stats())
```

Output:

```text
My Research Paper 2025 1
True [(4, 'Updated Title')]
True False 2
{'total_documents': 2, 'source_distribution': {'': 2}, 'db_path': ':memory:'}
```

| Method | Returns | Description |
|---|---|---|
| `get(rowid)` | `dict \| None` | The stored row: `id`, `title`, `abstract`, `full_text`, `authors`, `journal`, `doi`, `pmid`, `pmcid`, `source`, `source_id`, `year`, `citation_count`, `indexed_at`, `metadata_json` and the decoded `metadata` |
| `get_by_doi(doi)`, `get_by_pmid(pmid)` | `dict \| None` | The first row with that DOI or PMID, in the same form as `get()` |
| `update(entry)` | `bool` | Finds the first row whose PMID equals `entry.pmid` (if set), otherwise whose DOI equals `entry.doi`, otherwise whose `source_id` equals `entry.source_id`; deletes it and adds `entry` as a new row with a new row ID, then returns `True`. If nothing matches, adds `entry` and returns `False` |
| `delete(rowid)` | `bool` | `True` if a row with that ID existed and was deleted |
| `clear()` | `None` | Deletes every document |
| `stats()` | `dict` | `total_documents`, `source_distribution` (documents per `source` value) and `db_path` |
| `close()` | `None` | Closes the database connection |

## Keep an index on disk

```python
from pyeuropepmc.features.fulltext import IndexEntry, create_index, open_index

index = create_index("literature.db")
index.add(IndexEntry(doi="10.1000/1", title="Persisted Paper", abstract="Stored on disk"))
index.close()

with open_index("literature.db") as index:
    print([hit.title for hit in index.search("Persisted")])
```

Output:

```text
['Persisted Paper']
```

`create_index(db_path=None)` is `FullTextIndex(db_path, create=True)`; it creates the tables if they do not exist. `open_index(db_path=None)` is `FullTextIndex(db_path, create=False)` and does not create them. `FullTextIndex` works as a context manager and closes the connection on exit.

## Index parsed full text

```python
from pathlib import Path

from pyeuropepmc import FullTextXMLParser
from pyeuropepmc.features.fulltext import FullTextIndex, IndexEntry

parser = FullTextXMLParser(Path("PMC3258128.xml").read_text(encoding="utf-8"))
meta = parser.extract_metadata()

with FullTextIndex(":memory:") as index:
    index.add(
        IndexEntry(
            title=meta["title"],
            abstract=meta.get("abstract") or "",
            full_text=parser.to_plaintext(),
            doi=meta.get("doi") or "",
            pmcid=meta.get("pmcid") or "",
            source="europepmc",
        )
    )
    print([hit.title for hit in index.search("PRKRA AND microarray")])
```

Output:

```text
['Hepato-specific microRNA-122 facilitates accumulation of newly synthesized miRNA through regulating PRKRA']
```

`PMC3258128.xml` is the full-text XML of that article; download it with `FullTextClient().download_xml_by_pmcid("PMC3258128")` (see [Full-text retrieval](fulltext/README.md)).

## Index search results

`IndexEntry.from_literature_result()` converts a `LiteratureResult` from the multi-source search. It joins author names with `"; "`, copies `extra_metadata` into `metadata` and leaves `full_text` empty. `LiteratureResult` requires `source` and `source_id`.

```python
from pyeuropepmc.features.fulltext import FullTextIndex, IndexEntry
from pyeuropepmc.models import LiteratureResult

result = LiteratureResult(
    title="My Paper",
    doi="10.1000/example",
    authors=[{"name": "Smith, J"}],
    abstract="A paper about biomarkers",
    source="europepmc",
    source_id="PMC1234567",
)
entry = IndexEntry.from_literature_result(result)

with FullTextIndex(":memory:") as index:
    index.add(entry)
    print(entry.authors, entry.source_id, [hit.title for hit in index.search("biomarkers")])
```

Output:

```text
Smith, J PMC1234567 ['My Paper']
```

## IndexEntry fields

| Field | Type | Default |
|---|---|---|
| `title` | `str` | `""` |
| `abstract` | `str` | `""` |
| `full_text` | `str` | `""` |
| `authors` | `str` | `""` |
| `journal` | `str` | `""` |
| `doi` | `str` | `""` |
| `pmid` | `str` | `""` |
| `pmcid` | `str` | `""` |
| `source` | `str` | `""` |
| `source_id` | `str` | `""` |
| `year` | `int \| None` | `None` |
| `citation_count` | `int` | `0` |
| `metadata` | `dict` | `{}`; stored as JSON |

`source_id` and `metadata` are stored but not searchable.

## Known limitations

- `update()` gives the replaced document a new row ID.
