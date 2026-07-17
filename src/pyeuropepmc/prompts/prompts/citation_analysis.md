# Citation Analysis Request

## Paper Details
- **Title**: {{ paper.title }}
- **Authors**: {% for author in paper.authors %}{{ author.name }}{% if not loop.last %}, {% endif %}{% endfor %}
- **PMID**: {{ paper.pmid }}
- **DOI**: {{ paper.doi }}
- **Year**: {{ paper.publication_year }}
- **Journal**: {{ paper.journal }}

## Citation Context
{{ context }}

## Analysis Task
{{ task }}

## Expected Output Format
- Summary of citations in 2-3 sentences
- Key insights about citation patterns
- Methodology notes
- Limitations or caveats

Please provide a comprehensive analysis of the citation context for this paper.
