# Automated Paper Screening Request

## Research Context
- **Research Question**: {{ research_question }}
- **Inclusion Criteria**: {{ inclusion_criteria | join(', ') }}
- **Exclusion Criteria**: {{ exclusion_criteria | join(', ') }}

## Paper Details
{% for paper in papers %}
### Paper {{ loop.index }}
- **Title**: {{ paper.title }}
- **Authors**: {% for author in paper.authors %}{{ author.name }}{% if not loop.last %}, {% endif %}{% endfor %}
- **PMID**: {{ paper.pmid }}
- **PMCID**: {{ paper.pmicid }}
- **DOI**: {{ paper.doi }}
- **Year**: {{ paper.publication_year }}
- **Journal**: {{ paper.journal }}
- **Abstract**: {{ paper.abstract | truncate(500) }}
{% endfor %}

## Task
Classify each paper as: INCLUDE, EXCLUDE, or UNDECIDED based on the inclusion/exclusion criteria.
For each classification, provide reasoning based on the paper's content.

## Expected Output Format
For each paper, provide:
1. Classification (INCLUDE/EXCLUDE/UNDECIDED)
2. Reasoning (2-3 sentences explaining why)
3. Evidence (key quotes or findings from the paper)

Please screen the papers according to the specified criteria.
