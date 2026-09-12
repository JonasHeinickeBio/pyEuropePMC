# Literature Review Automation Request

## Research Topic
{{ research_topic }}

## Scope
- **Time frame**: {{ time_frame }}
- **Key concepts**: {{ key_concepts | join(', ') }}
- **Excluded topics**: {{ excluded_topics | join(', ') }}

## Task
Create a comprehensive literature review covering:
1. Historical development of the topic
2. Key milestones and breakthroughs
3. Major research paradigms
4. Emerging trends and future directions

## Expected Output Format

### Historical Overview
- Timeline of key developments
- Foundational papers and their impact
- Evolution of research approaches

### Current State of Research
- Dominant theories and models
- Key findings and consensus
- Ongoing debates and controversies

### Research Trends
- Growth patterns over time
- Interdisciplinary connections
- Emerging subfields

### Future Directions
- Unanswered questions
- Methodological innovations
- Translational potential

### Key Papers
| Title | Authors | Year | DOI/PMID | Significance |
|-------|---------|------|----------|--------------|
{% for paper in papers %}
| {{ paper.title }} | {{ paper.authors }} | {{ paper.year }} | {{ paper.doi or paper.pmid }} | {{ paper.significance }} |
{% endfor %}

Please create a comprehensive literature review for this topic.
