# MeSH Models & PICO Decomposition

Structured representations of MeSH terms and clinical question parsing for evidence-based literature search.

## MeSH Models

PyEuropePMC provides Pydantic-like data models for MeSH (Medical Subject Headings) terms extracted from Europe PMC annotations.

### MeSHHeadingEntity

Represents a complete MeSH heading with descriptor and qualifiers:

```python
from pyeuropepmc.models import MeSHHeadingEntity, MeSHQualifierEntity

# From structured data
heading = MeSHHeadingEntity(
    descriptor_name="Neoplasms",
    major_topic=True,
    qualifiers=[MeSHQualifierEntity("diagnosis", "DI", False)],
    descriptor_ui="D009369",
)

print(heading.full_term)
# "Neoplasms/diagnosis"

print(heading.descriptor_name)
# "Neoplasms"
```

### MeSHQualifierEntity

Represents a MeSH qualifier (subheading) that refines a descriptor:

```python
qualifier = MeSHQualifierEntity(
    name="therapy",
    abbreviation="TH",
    major_topic=False,
)
```

### Parsing from API Response

```python
# From Europe PMC API response
data = {
    "descriptorName": "Neoplasms",
    "majorTopic_YN": "Y",
    "meshQualifierList": {
        "meshQualifier": [
            {"qualifierName": "diagnosis", "qualifierUI": "Q000175", "majorTopic_YN": "N"},
        ]
    },
}

heading = MeSHHeadingEntity.from_dict(data)
```

## PICO Decomposition

Decompose clinical research questions into PICO (Population, Intervention, Comparison, Outcome) elements for structured literature search.

### Basic Parsing

```python
from pyeuropepmc.features.literature import pico_decompose, PICOElements

pico = pico_decompose(
    "In patients with diabetes, does metformin reduce cardiovascular risk compared to placebo?"
)

print(f"Population:   {pico.population}")    # "patients with diabetes"
print(f"Intervention: {pico.intervention}")  # "metformin"
print(f"Comparison:   {pico.comparison}")    # "placebo"
print(f"Outcome:      {pico.outcome}")       # "reduce cardiovascular risk"
```

### Converting to Search Queries

```python
from pyeuropepmc.features.literature import pico_to_query, pico_to_pubmed_query

# Generic boolean query
query = pico_to_query(pico)
print(query)
# "(diabetes) AND (metformin) AND (cardiovascular risk) AND (placebo)"

# PubMed-optimized with MeSH hints
pubmed_query = pico_to_pubmed_query(pico, use_mesh=True)
print(pubmed_query)
# "(diabetes[MeSH]) AND (metformin[MeSH]) AND (cardiovascular risk) AND (placebo)"
```

### Parser Variants

```python
from pyeuropepmc.features.literature import PICOParser, PICOSDecomposer, PICOTDecomposer

# Standard PICO
parser = PICOParser()
pico = parser.parse("In children with asthma, does exercise improve lung function?")

# PICOS (with Study Design)
parser = PICOSDecomposer()
pico = parser.parse("In elderly patients, does aspirin prevent stroke? A randomized trial")

# PICOT (with Time frame)
parser = PICOTDecomposer()
pico = parser.parse("In ICU patients, does early mobilization reduce length of stay within 30 days?")
```

### Confidence Scoring

```python
pico = pico_decompose("Does exercise help depression?")
print(f"Population: {pico.population}")
print(f"Confidence: {pico.confidence:.2f}")
```

### Command-Line PICO

```bash
python -m pyeuropepmc.features.review.pico "In patients with diabetes, does metformin reduce cardiovascular risk?"
```

## Use Cases

- **Systematic reviews**: Structure clinical questions for precise searching
- **Evidence-based practice**: Convert clinical queries to PubMed search strings
- **Clinical decision support**: Parse and categorize clinical questions
- **Medical education**: Teach PICO formulation
