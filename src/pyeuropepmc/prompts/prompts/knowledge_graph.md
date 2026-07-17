# Knowledge Graph Builder Request

## Research Domain
{{ research_domain }}

## Entities to Map
{% for entity in entities %}
- {{ entity.name }} ({{ entity.type }})
{% endfor %}

## Relationships to Identify
{% for relationship in relationships %}
- {{ relationship.source }} → {{ relationship.target }}: {{ relationship.type }}
{% endfor %}

## Task
Build a comprehensive knowledge graph representing relationships in this research domain.

## Expected Output Format

### Knowledge Graph Structure

#### Nodes
{% for node in nodes %}
- **{{ node.id }}**: {{ node.label }} ({{ node.type }})
  - Properties: {{ node.properties }}
{% endfor %}

#### Edges
{% for edge in edges %}
- **{{ edge.source }}** → **{{ edge.target }}**: {{ edge.type }}
  - Evidence: {{ edge.evidence }}
{% endfor %}

### Graph Analysis
- Central concepts
- Knowledge gaps
- Connected components
- Potential new relationships

#### GraphML Format
```xml
<graphml>
<!-- Graph structure in GraphML format -->
</graphml>
```

#### JSON Format
```json
{
  "nodes": [],
  "edges": []
}
```

Please construct a comprehensive knowledge graph for this research domain.
