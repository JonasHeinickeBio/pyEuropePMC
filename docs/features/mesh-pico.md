# MeSH models, MeSH expansion and PICO decomposition

This page covers the data models for MeSH (Medical Subject Headings) terms in Europe PMC records, the MeSH query-expansion helpers, and the heuristic parser that splits clinical questions into PICO (Population, Intervention, Comparison, Outcome) elements.

## MeSH data models

`MeSHHeadingEntity` and `MeSHQualifierEntity` are dataclasses in `pyeuropepmc.models`.

```python
from pyeuropepmc.models import MeSHHeadingEntity, MeSHQualifierEntity

heading = MeSHHeadingEntity(
    descriptor_name="Neoplasms",
    major_topic=True,
    qualifiers=[MeSHQualifierEntity(qualifier_name="diagnosis", abbreviation="DI", major_topic=False)],
    descriptor_ui="D009369",
)

print(heading.get_full_term())  # Neoplasms/diagnosis
print(heading.to_dict())
# {'descriptor_name': 'Neoplasms', 'major_topic': True, 'qualifiers': [{'qualifier_name': 'diagnosis',
#  'abbreviation': 'DI', 'major_topic': False}], 'descriptor_ui': 'D009369'}
```

| Class | Fields and defaults |
|---|---|
| `MeSHQualifierEntity` | `qualifier_name: str`, `abbreviation: str or None = None`, `major_topic: bool = False` |
| `MeSHHeadingEntity` | `descriptor_name: str`, `major_topic: bool = False`, `qualifiers: list[MeSHQualifierEntity] = []`, `descriptor_ui: str or None = None` |

`get_full_term()` returns the descriptor followed by each qualifier name, separated by `/`.

### From Europe PMC records

`MeSHHeadingEntity.from_dict(data)` reads one entry of a record's `meshHeadingList.meshHeading` list: `descriptorName`, `majorTopic_YN` (`"Y"` or `"N"`), `descriptorUI` and `meshQualifierList.meshQualifier`, whose entries have `qualifierName`, `abbreviation` and `majorTopic_YN`.

```python
from pyeuropepmc.models import MeSHHeadingEntity

data = {
    "descriptorName": "Neoplasms",
    "majorTopic_YN": "Y",
    "meshQualifierList": {
        "meshQualifier": [{"qualifierName": "therapy", "abbreviation": "TH", "majorTopic_YN": "N"}]
    },
}
print(MeSHHeadingEntity.from_dict(data).get_full_term())  # Neoplasms/therapy
```

MeSH headings are only included in `resultType="core"` search results. `EuropePMCParser.extract_mesh_headings(record)` converts all headings of a record:

```python
from pyeuropepmc import EuropePMCParser, SearchClient

with SearchClient() as client:
    records = client.search("cancer fatigue", resultType="core")["resultList"]["result"]

for record in records:
    headings = EuropePMCParser.extract_mesh_headings(record)
    if headings:
        print(record["id"], [heading.get_full_term() for heading in headings[:4]])
        break
```

## MeSH query expansion

`pyeuropepmc.features.review` suggests MeSH headings for common terms and adds them to a query.

```python
from pyeuropepmc.features.review import expand_with_mesh, translate_to_mesh

expansion = expand_with_mesh("heart attack AND diabetes")
print(expansion.mesh_terms)
# ['Myocardial Infarction', 'Myocardial Ischemia', 'Diabetes Mellitus', 'Diabetes Mellitus, Type 1', 'Diabetes Mellitus, Type 2']
print(expansion.expanded_query)
# ("heart attack" OR "Myocardial Infarction" OR "Myocardial Ischemia") AND (diabetes OR ...)

print(translate_to_mesh(["heart attack", "unknown term"]))
# {'heart attack': ['Myocardial Infarction', 'Myocardial Ischemia']}
```

| Function | Returns | Description |
|---|---|---|
| `expand_with_mesh(query, use_api=False)` | `MeSHExpansionResult` | `original_query`, `expanded_query`, `mesh_terms` and `term_suggestions` (term to headings) |
| `suggest_mesh_terms(term, max_suggestions=5, use_api=False)` | `list[str]` | Headings for one term |
| `translate_to_mesh(terms, use_api=False)` | `dict[str, list[str]]` | Headings for each term that has suggestions |
| `lookup_mesh_descriptor(mesh_heading)` | `dict` or `None` | Descriptor record from the NLM MeSH lookup service (network); `None` on failure |

`MeSHExpander(use_api=False, max_suggestions=5)` provides the same through `expand(query)`.

Without `use_api`, suggestions come from a built-in list of about twenty common terms, such as "cancer", "diabetes", "heart attack" and "machine learning"; other terms get no suggestions. With `use_api=True`, terms are looked up with the NLM MeSH suggestion service and the built-in list is the fallback.

The query is split into terms at `AND`, `OR`, `NOT`, quotes and parentheses, so `cancer gene therapy` is a single term with no suggestions while `cancer AND gene therapy` is two. `expanded_query` keeps the original operators and parentheses and replaces each term that has suggestions with a group of the term and its headings; terms and headings of more than one word are quoted:

```python
print(expand_with_mesh("heart attack AND diabetes").expanded_query)
# ("heart attack" OR "Myocardial Infarction" OR "Myocardial Ischemia") AND (diabetes OR "Diabetes Mellitus" OR "Diabetes Mellitus, Type 1" OR "Diabetes Mellitus, Type 2")
```

Text without suggestions is kept as written. Field-qualified parts such as `TITLE:cancer`, `TITLE:"gene therapy"` or `PUB_YEAR:[2020 TO 2024]` are not expanded. A heading that repeats the term in another case, such as `Obesity` for `obesity`, is left out of the group.

## PICO decomposition

```python
from pyeuropepmc.features.review import pico_decompose, pico_to_pubmed_query, pico_to_query

pico = pico_decompose(
    "In patients with diabetes, does metformin reduce cardiovascular risk compared to placebo?"
)
print(pico.population)    # diabetes, does metformin reduce cardiovascular risk compared to placebo
print(pico.intervention)  # (empty)
print(pico.comparison)    # placebo
print(pico.outcome)       # reduce cardiovascular risk compared to placebo
print(round(pico.confidence, 2), pico.is_complete())  # 0.7 False

print(pico_to_query(pico))
# (diabetes, OR does OR metformin OR reduce OR cardiovascular) AND (reduce OR cardiovascular OR risk OR compared OR to) AND (placebo)
print(pico_to_pubmed_query(pico, use_mesh=True))
# (diabetes, does metformin reduce cardiovascular risk compared to placebo[MeSH]) AND (reduce cardiovascular risk compared to placebo[MeSH]) AND (placebo[MeSH])
```

The parser matches regular expressions for cue words such as "patients with", "compared to" and "reduce". It often captures too much or too little: in the example the intervention is missing and the population runs to the end of the sentence, and "Does exercise help depression?" yields no elements at all. Treat the elements and the generated queries as a draft for manual review.

| Name | Description |
|---|---|
| `pico_decompose(question)` | `PICOElements` for a question, using `PICOParser` |
| `PICOParser(patterns=None)` | `parse(question)` returns `PICOElements`; `patterns` replaces the built-in regular expressions |
| `PICOElements` | Dataclass with `population`, `intervention`, `comparison`, `outcome`, `study_design`, `time_frame`, `setting`, `original_question`, `confidence` (0.0 to 1.0) and `identifiers_used`; `is_complete()` is `True` when population, intervention and outcome are set; `to_dict()` |
| `pico_to_query(pico, use_boolean=True)` | Each element as up to five words joined with `OR` (three for comparison), elements joined with `AND` |
| `pico_to_pubmed_query(pico, use_mesh=True)` | Each element tagged `[MeSH]`, or `[tiab]` with `use_mesh=False`, joined with `AND` |
| `PICOSDecomposer`, `PICOTDecomposer` | Same behaviour as `PICOParser`; `study_design` is filled by every parser |
| `SPIDERDecomposer` | `parse(question)` returns a dict with the SPIDER elements it finds (`sample`, `phenomenon_of_interest`, `design`, `evaluation`, `research_type`) and `original_question` |

`time_frame` is filled from phrases such as "within 30 days" or "over 12 months": `PICOTDecomposer().parse("... reduce mortality within 30 days?").time_frame` is `"30 days"`. A custom `patterns` dict is keyed by the `PICOElements` field each pattern fills; the key `"time"` is accepted for `time_frame`.

## See also

- [Searching Europe PMC](search/README.md)
- [EuropePMCParser](../api/parser.md)
