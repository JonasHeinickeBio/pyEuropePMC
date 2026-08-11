# ClinicalTrials.gov Integration

Search and retrieve clinical trial protocols from ClinicalTrials.gov.

## Basic Search

```python
from pyeuropepmc.features.search import ClinicalTrialsClient

with ClinicalTrialsClient() as client:
    # Search by keyword
    trials = client.search("chronic fatigue syndrome", limit=10)
    for trial in trials:
        nct = trial.extra_metadata.get("nct_id")
        status = trial.extra_metadata.get("overall_status")
        print(f"{nct}: {trial.title} [{status}]")
```

## Search by Condition

```python
# Find trials for a specific condition
trials = client.search_by_condition("ME/CFS", limit=20)
```

## Search by Intervention

```python
# Find trials testing a specific intervention
trials = client.search_by_intervention("cognitive behavioral therapy", limit=20)
```

## Get Trial by NCT ID

```python
trial = client.get_paper("NCT04527549")
print(trial.extra_metadata)
# {
#     "nct_id": "NCT04527549",
#     "overall_status": "Recruiting",
#     "phase": "Phase 3",
#     "sponsor": "National Institutes of Health",
#     "enrollment": 500,
#     "conditions": ["Chronic Fatigue Syndrome"],
#     ...
# }
```

## ClinicalTrial Model

Search results can also be obtained as structured `ClinicalTrial` objects:

```python
from pyeuropepmc.models import ClinicalTrial

# Via search_and_normalize, results are LiteratureResult
# Via the ClinicalTrial model directly:
trial_data = {
    "nct_id": "NCT04527549",
    "brief_title": "CBT for ME/CFS",
    "overall_status": "Recruiting",
    "phase": "Phase 3",
    "conditions": ["Chronic Fatigue Syndrome"],
    "interventions": ["Cognitive Behavioral Therapy"],
    "start_date": "2025-01-01",
    "completion_date": "2027-12-31",
    "enrollment": 500,
    "sponsor": "NIH",
}
trial = ClinicalTrial(**trial_data)

# Convert to LiteratureResult for unified processing
result = trial.to_literature_result()
```

## Extra Metadata

Clinical trial results include additional metadata in the `extra_metadata` field:

| Field | Description |
|-------|-------------|
| `nct_id` | ClinicalTrials.gov identifier |
| `overall_status` | Trial status (Recruiting, Active, Completed) |
| `phase` | Trial phase (Phase 1, Phase 2, etc.) |
| `sponsor` | Lead sponsor or collaborator |
| `enrollment` | Target enrollment number |
| `conditions` | List of medical conditions studied |
| `interventions` | List of interventions tested |
| `start_date` | Study start date |
| `completion_date` | Primary completion date |
