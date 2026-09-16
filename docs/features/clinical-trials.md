# ClinicalTrials.gov client

`ClinicalTrialsClient` searches registered clinical studies through the ClinicalTrials.gov API v2 and returns them as `LiteratureResult` records with trial details in `extra_metadata`. The `ClinicalTrial` model gives a structured representation. No API key is needed.

## Search

```python
from pyeuropepmc.features.search import ClinicalTrialsClient

with ClinicalTrialsClient() as client:
    trials = client.search("chronic fatigue syndrome", limit=10)

for trial in trials:
    meta = trial.extra_metadata
    print(f"{meta['nct_id']}: {trial.title} [{meta['overall_status']}, {meta['phase']}]")
```

`search(query, limit=25, sort=None, **kwargs) -> list[LiteratureResult]`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | required | ClinicalTrials.gov search expression, sent as `query.term` |
| `limit` | `int` | `25` | Maximum records; capped at 100 |
| `sort` | `str` or `None` | `None` | `"relevance"`, `"last_update"`, `"first_post"` or `"enrollment"`, sent as `@relevance`, `@last_update`, `@first_post` or `@enrollment`; `@relevance` when `None` |
| `status` | `str` | not sent | Sent as `filter.overallStatus`, for example `"RECRUITING"` |
| `phase` | `str` | not sent | Sent as `filter.phase`, for example `"PHASE3"` |

Of these request values, `@relevance` and `filter.overallStatus` are described in the [ClinicalTrials.gov API documentation](https://clinicaltrials.gov/data-api/api); check the other sort values and `filter.phase` there before relying on them.

### Search by condition or intervention

```python
from pyeuropepmc.features.search import ClinicalTrialsClient

with ClinicalTrialsClient() as client:
    by_condition = client.search_by_condition("ME/CFS", limit=20)
    by_intervention = client.search_by_intervention("cognitive behavioral therapy", limit=20)

print(len(by_condition), len(by_intervention))
```

`search_by_condition(condition, limit=25, **kwargs)` searches `AREA[ConditionSearch] <condition>` and `search_by_intervention(intervention, limit=25, **kwargs)` searches `AREA[InterventionSearch] <intervention>`.

### Get a trial by NCT ID

```python
from pyeuropepmc.features.search import ClinicalTrialsClient

with ClinicalTrialsClient() as client:
    trial = client.get_paper("NCT04527549")

if trial:
    print(trial.title)
    print(trial.extra_metadata)
```

`get_paper(identifier) -> LiteratureResult | None` adds the `NCT` prefix when it is missing and returns `None` when the study does not exist.

## Result fields

| Field | Content |
|---|---|
| `source`, `source_id` | `"clinicaltrials"` and the NCT ID |
| `title` | Official title, or the brief title when there is none |
| `abstract` | Detailed description, or the brief summary |
| `publication_year` | Year of the study start date |
| `authors` | The study's overall officials |
| `pmid` | First PubMed ID among the references of type `RESULT` |
| `doi` | The study DOI, when registered |

`extra_metadata` holds:

| Key | Content |
|---|---|
| `nct_id` | NCT ID |
| `overall_status` | API v2 status value, for example `RECRUITING` or `COMPLETED` |
| `phase` | API v2 phase values joined with `", "`, for example `PHASE3` or `PHASE2, PHASE3`; empty when none |
| `study_type` | For example `INTERVENTIONAL` or `OBSERVATIONAL` |
| `conditions` | `list[str]` |
| `sponsor` | Name of the lead sponsor |
| `enrollment` | Enrollment count, or `None` |
| `start_date` | Study start date as given by the registry, for example `2025-01` |
| `completion_date` | Study completion date |

Interventions are not included in search results.

## ClinicalTrial model

```python
from pyeuropepmc.models import ClinicalTrial

trial = ClinicalTrial(
    nct_id="NCT04527549",
    title="CBT for ME/CFS",
    status="RECRUITING",
    phase="PHASE3",
    conditions=["Chronic Fatigue Syndrome"],
    interventions=[{"type": "BEHAVIORAL", "name": "Cognitive Behavioral Therapy"}],
    sponsors=[{"name": "NIH"}],
    enrollment=500,
    start_date="2025-01-01",
    completion_date="2027-12-31",
)

result = trial.to_literature_result()
print(result.journal, result.publication_year)  # Clinical Trial PHASE3 2025
print(result.extra_metadata["interventions"])   # ['Cognitive Behavioral Therapy']
```

| Field | Type | Default |
|---|---|---|
| `nct_id` | `str` | required |
| `title` | `str` | `""` |
| `status` | `str` | `"UNKNOWN"` |
| `phase` | `str` | `"NA"` |
| `conditions`, `mesh_conditions`, `mesh_interventions` | `list[str]` | `[]` |
| `interventions` | `list[dict]` | `[]` |
| `sponsors`, `locations`, `references` | `list[dict[str, str]]` | `[]` |
| `enrollment` | `int` or `None` | `None` |
| `design`, `start_date`, `completion_date`, `brief_summary`, `detailed_description`, `eligibility_criteria` | `str` or `None` | `None` |

The model accepts unknown keyword arguments and stores them unvalidated, so a misspelled name such as `brief_title` or `overall_status` leaves the real field at its default. Status, phase and design constants are defined in `pyeuropepmc.models.clinical_trial` as `TrialStatus`, `TrialPhase` and `TrialDesign`.

`to_literature_result()` builds a `LiteratureResult` with the sponsors as authors, the start year as `publication_year`, `"Clinical Trial <phase>"` as `journal` and `extra_metadata` keys `nct_id`, `status`, `phase`, `conditions`, `interventions` (names), `enrollment` and `sponsors`.

`ClinicalTrial.from_literature_result(result)` fills `nct_id`, `title`, `status`, `phase` and `conditions`. It reads the status from `extra_metadata["status"]`, as written by `to_literature_result()`, or from `extra_metadata["overall_status"]`, as written by `ClinicalTrialsClient`. A missing or empty status or phase falls back to `"UNKNOWN"` or `"NA"`.

```python
from pyeuropepmc.features.search import ClinicalTrialsClient
from pyeuropepmc.models import ClinicalTrial

with ClinicalTrialsClient() as client:
    result = client.get_paper("NCT04527549")

trial = ClinicalTrial.from_literature_result(result)
print(trial.nct_id, trial.status, trial.phase)
```

## Rate limit

`ClinicalTrialsClient(rate_limit_delay=0.5, timeout=30, cache_config=None)` waits 0.5 seconds between requests. `UnifiedSearch` replaces the delay with its own `rate_limit_delay`.

## See also

- [Multi-source search](multi-source-search.md)
