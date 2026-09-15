# ORCID and NIH iCite clients

`OrcidClient` reads researcher profiles and works from the ORCID public API, and `ICiteClient` reads citation metrics for PubMed articles from NIH iCite. Both are enrichment clients that look up known identifiers; they are not [multi-source search](multi-source-search.md) sources. Neither needs authentication.

```python
from pyeuropepmc.features.enrich import ICiteClient, OrcidClient
```

## ORCID

`OrcidClient(rate_limit_delay=1.0, timeout=15, cache_config=None)` reads public records from the ORCID public API v3.0 (`https://pub.orcid.org/v3.0`).

### Profiles

```python
from pyeuropepmc.features.enrich import OrcidClient

with OrcidClient() as client:
    profile = client.get_profile("0000-0002-1825-0097")

if profile:
    print(profile["name"])
    print(f"{len(profile['works'])} works")
    for work in profile["works"][:5]:
        print(f"  {work['year']}: {work['title']} (DOI: {work['doi']})")
```

`get_profile(orcid)` returns a `dict`, or `None` when the iD cannot be read or the record cannot be retrieved. `enrich(identifier)` returns the same dict.

| Key | Type | Content |
|---|---|---|
| `name` | `str` | Given and family names |
| `given_name`, `family_name` | `str` | |
| `credit_name` | `str` or `None` | Published name |
| `other_names`, `keywords` | `list[str]` | |
| `biography` | `str` or `None` | |
| `urls` | `dict[str, str]` | Link name to URL |
| `employments`, `educations` | `list[dict]` | Dicts with `organization`, `department`, `role`, `start` and `end` |
| `works` | `list[dict]` | Works as returned by `get_works()`; repeated DOIs are dropped |

### Works

```python
from pyeuropepmc.features.enrich import OrcidClient

with OrcidClient() as client:
    works = client.get_works("https://orcid.org/0000-0002-1825-0097")

for work in works:
    print(work["year"], work["type"], work["title"])
```

`get_works(orcid)` returns a list of dicts with `title`, `doi` (normalized, or `None`), `year` (`int` or `None`), `type`, `journal_title`, `visibility` and `path`, or an empty list when the iD cannot be read or the request fails.

### Identifier formats

`0000-0002-1825-0097`, `https://orcid.org/0000-0002-1825-0097` and `orcid.org/0000-0002-1825-0097` are all accepted; the first iD found in the string is used.

### Known limitations

- `employments` and `educations` are read from `employment-summary` and `education-summary` lists. ORCID API v3.0 nests these entries in `affiliation-group` objects, so both lists come back empty.
- A record whose biography is `null` in the ORCID response makes `get_profile()` and `enrich()` raise `AttributeError`.
- `journal_title` is ORCID's value object, for example `{"value": "Journal of Psychoceramics"}`, not a string.

## NIH iCite

`ICiteClient(rate_limit_delay=0.5, timeout=15)` reads metrics from the iCite API (`https://icite.od.nih.gov/api`).

```python
from pyeuropepmc.features.enrich import ICiteClient

with ICiteClient() as client:
    metrics = client.enrich_many(["32791984", "32882182"])
    single = client.enrich("32791984")

for pmid, values in metrics.items():
    print(f"PMID {pmid}: {values['citation_count']} citations, "
          f"RCR {values['rcr']}, NIH percentile {values['percentile']}")
```

| Method | Returns |
|---|---|
| `enrich(identifier)` | Metrics dict for one PMID, or `None` |
| `enrich_many(pmids)` | `dict[str, dict]` keyed by PMID, from one request; PMIDs iCite does not know are absent |
| `get_rcr(pmid)`, `get_percentile(pmid)`, `get_citation_count(pmid)` | One value or `None`; each call makes a request |

Each metrics dict has these keys:

| Key | Type | Content |
|---|---|---|
| `pmid` | `str` | |
| `rcr` | `float` or `None` | Relative Citation Ratio |
| `percentile`, `nih_percentile` | `float` or `None` | NIH percentile of the RCR |
| `citation_count` | `int` or `None` | Citations counted by iCite |
| `citations_per_year` | `float` or `None` | |
| `expected_citations` | `float` or `None` | Expected citations per year for the article's field |
| `field_citation_ratio` | `float` or `None` | |
| `is_research_article`, `provisional` | `bool` | |
| `year` | `int` or `None` | Publication year |

### ICiteMetrics model

The client returns dicts. `pyeuropepmc.models.ICiteMetrics` is a separate Pydantic model with the fields `pmid`, `rcr`, `percentile`, `citation_count`, `expected_citations`, `field_citation_ratio`, `nih_percentile` and `is_controversial`; every field except `pmid` defaults to `0`, `0.0` or `False`. It accepts extra keys without validating them, so use these exact names:

```python
from pyeuropepmc.models import ICiteMetrics

metrics = ICiteMetrics(pmid="32791984", citation_count=42, rcr=1.5, percentile=85.0, expected_citations=28.0)
print(metrics.rcr, metrics.field_citation_ratio)  # 1.5 0.0
```

## See also

- [Enrichment guide](../guides/enrichment.md)
- [Multi-source search](multi-source-search.md)
