# Preprint-Specific Analysis Request

## Paper Information
- **Title**: {{ paper.title }}
- **Authors**: {% for author in paper.authors %}{{ author.name }}{% if not loop.last %}, {% endif %}{% endfor %}
- **PMID**: {{ paper.pmid }}
- **Preprint Server**: {{ paper.preprint_server }}
- **Date Posted**: {{ paper.date_posted }}
- **Abstract**: {{ paper.abstract | truncate(500) }}

## Task
Analyze this preprint with special attention to preprint-specific considerations:
1. Methodological rigor assessment
2. Transparency and reproducibility
3. Data availability and code sharing
4. Conflict of interest disclosure
5. Limitations and biases

## Expected Output Format

### Methodology Assessment
- Study design quality
- Sample size adequacy
- Statistical methods
- Potential biases

### Transparency Indicators
- Data availability statement
- Code availability
- Preprint version history
- Author declarations

### Preprint Considerations
- How preprint status affects interpretation
- Potential limitations vs. peer-reviewed publication
- Recommendations for readers

Please provide a thorough preprint-specific analysis.
