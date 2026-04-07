# Institutional Hierarchy and Relationship Mapping - IMPROVEMENTS

## Overview

The PyEuropePMC RDF mapping system has been significantly improved to properly represent institutional hierarchies and relationships. These changes ensure that critical semantic relationships between organizations, departments, authors, and papers are explicitly encoded in the RDF output.

## Key Problems Addressed

### Before (Broken):
- ❌ Organizations and departments appeared disconnected
- ❌ No explicit Department → Organization hierarchies
- ❌ Author-Institution relationships not clearly represented
- ❌ Paper affiliations only through text, not structured RDF
- ❌ Generic namespaces (ns1, ns2, ns3) instead of semantic ontologies

### After (Improved):
- ✅ Explicit institutional hierarchies using org: namespace
- ✅ Clear Department ↔ Organization relationships (org:unitOf / org:hasUnit)
- ✅ Structured Author ↔ Organization relationships (pyeuropepmc:affiliatedWith)
- ✅ Paper ↔ Organization links
- ✅ Proper semantic namespaces throughout

## Technical Improvements

### 1. Enhanced RDF Mapping Configuration (conf/rdf_map.yml)

```yaml
# Organization mapping includes:
Organization:
  relationships:
    members:
      predicate: "org:hasMember"
      inverse: org:memberOf
    departments:
      predicate: "org:hasUnit"
      inverse: org:unitOf
```

### 2. Department Hierarchy Support

```yaml
Department:
  relationships:
    parent_organization:
      predicate: "org:unitOf"
      inverse: org:hasUnit
```

### 3. Author Institutional Relationships

```yaml
AuthorEntity:
  relationships:
    institutions:
      predicate: "pyeuropepmc:affiliatedWith"
      inverse: pyeuropepmc:hasAffiliate
```

### 4. Paper-Organization Relationships

```yaml
PaperEntity:
  relationships:
    paper_institutions:
      predicate: "pyeuropepmc:affiliatedWith"
      inverse: pyeuropepmc:hasPublication
```

### 5. Enhanced RDF Mapper

**New method: `_add_institutional_hierarchy()`**

This method generates explicit institutional relationships:
- Links departments to parent organizations
- Connects authors to their affiliated institutions
- Creates paper-organization relationships transitively through authors
- Adds inverse relationships for bidirectional queries

## data Model Enhancements

### Institutional Hierarchy in Generated RDF

```
Organization (MIT)
  ├── org:hasUnit → Department (CSAIL)
  ├── org:hasUnit → Department (Broad Institute)
  ├── pyeuropepmc:hasAffiliate → Author (John Smith)
  ├── pyeuropepmc:hasAffiliate → Author (Jane Doe)
  └── pyeuropepmc:hasPublication → Paper (Genomics 2024)

Department (CSAIL)
  ├── org:unitOf → Organization (MIT)
  └── pyeuropepmc:hasDepartmentMember → Authors...

Author (John Smith)
  ├── pyeuropepmc:affiliatedWith → Organization (MIT)
  ├── pyeuropepmc:departmentMember → Department (CSAIL)
  └── foaf:made → Paper(s)

Paper (Genomics 2024)
  ├── dcterms:creator → Author
  ├── pyeuropepmc:affiliatedWith → Organization (MIT)
  ├── pyeuropepmc:affiliatedWith → Organization (Harvard)
  └── pyeuropepmc:departmentAffiliation → Department(s)
```

## Example RDF Output

### Turtle Format (Proper Namespaces)

```turtle
@prefix org: <http://www.w3.org/ns/org#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#> .

# Organization with departments
<https://w3id.org/pyeuropepmc/data#organization/mit> a org:Organization ;
    rdfs:label "Massachusetts Institute of Technology" ;
    org:hasUnit <https://w3id.org/pyeuropepmc/data#department/csail> ;
    pyeuropepmc:hasAffiliate <https://w3id.org/pyeuropepmc/data#author/john-smith> ;
    pyeuropepmc:hasPublication <https://w3id.org/pyeuropepmc/data#paper/genomics-2024> .

# Department with parent link
<https://w3id.org/pyeuropepmc/data#department/csail> a org:OrganizationalUnit ;
    org:unitOf <https://w3id.org/pyeuropepmc/data#organization/mit> .

# Author with affiliations
<https://w3id.org/pyeuropepmc/data#author/john-smith> a foaf:Person ;
    pyeuropepmc:affiliatedWith <https://w3id.org/pyeuropepmc/data#organization/mit> .

# Paper with institutional and author links
<https://w3id.org/pyeuropepmc/data#paper/genomics-2024> a bibo:AcademicArticle ;
    dcterms:creator <https://w3id.org/pyeuropepmc/data#author/john-smith> ;
    pyeuropepmc:affiliatedWith <https://w3id.org/pyeuropepmc/data#organization/mit> .
```

## Ontologies and Namespaces Used

| Prefix | Namespace | Purpose |
|--------|-----------|---------|
| org | http://www.w3.org/ns/org# | Organizational hierarchy (unitOf, hasUnit) |
| foaf | http://xmlns.com/foaf/0.1/ | Person, author representation |
| dcterms | http://purl.org/dc/terms/ | Bibliographic metadata |
| bibo | http://purl.org/ontology/bibo/ | Bibliographic ontology |
| pyeuropepmc | https://w3id.org/pyeuropepmc/vocab# | PyEuropePMC-specific predicates |

## Usage Examples

### Running the Demo

```bash
# Improved demo showing all features
python examples/11-institutional-hierarchy/institutional_improved_demo.py

# Full demo with entity generation
python examples/11-institutional-hierarchy/institutional_relationships_demo.py
```

### Using the RDFMapper Directly

```python
from pyeuropepmc.models import PaperEntity, AuthorEntity, Organization
from pyeuropepmc.mappers.rdf_mapper import RDFMapper
from rdflib import Graph

# Create entities with institutional relationships
org = Organization(display_name="MIT", ror_id="https://ror.org/042nb2s44")
author = AuthorEntity(full_name="John Smith", author_institutions=[org])
paper = PaperEntity(title="Paper", authors=[author], paper_institutions=[org])

# Generate RDF
mapper = RDFMapper()
entities_data = {
    "paper1": {
        "entity": paper,
        "related_entities": {"authors": [author]}
    }
}

graphs = mapper.convert_and_save_entities_to_rdf(entities_data)
```

## Configuration Changes

### rdf_map.yml Updates

New relationship mappings added:
- `paper_institutions` relationships for papers
- `paper_departments` relationships for papers
- `author_departments` relationships for authors
- Enhanced inverse relationships for all hierarchies

### RDF Mapper Enhancement

Enhanced `_add_institutional_hierarchy()` method now:
1. Creates Department ↔ Organization parent-child relationships
2. Links Authors to Organizations (institutional affiliation)
3. Links Authors to Departments (departmental membership)
4. Connects Papers to Organizations transitively through authors
5. Adds all inverse relationships for bidirectional querying

## Query Examples

### SPARQL Queries on Improved RDF

```sparql
# Find all departments of MIT
PREFIX org: <http://www.w3.org/ns/org#>
SELECT ?dept WHERE {
  <https://w3id.org/pyeuropepmc/data#organization/mit> org:hasUnit ?dept .
}

# Find all authors affiliated with MIT
PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>
SELECT ?author WHERE {
  <https://w3id.org/pyeuropepmc/data#organization/mit> pyeuropepmc:hasAffiliate ?author .
}

# Find all papers affiliated with MIT
PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>
SELECT ?paper WHERE {
  ?paper pyeuropepmc:affiliatedWith <https://w3id.org/pyeuropepmc/data#organization/mit> .
}

# Institutional collaboration network
PREFIX pyeuropepmc: <https://w3id.org/pyeuropepmc/vocab#>
SELECT ?paper ?org1 ?org2 WHERE {
  ?paper pyeuropepmc:affiliatedWith ?org1 ;
         pyeuropepmc:affiliatedWith ?org2 .
  FILTER (?org1 != ?org2)
}
```

## Files Modified

1. **conf/rdf_map.yml** - Enhanced with institutional relationship mappings
2. **src/pyeuropepmc/mappers/rdf_mapper.py** - Improved `_add_institutional_hierarchy()` method
3. **examples/11-institutional-hierarchy/** - New demonstration scripts

## Validation

The improvements have been validated to ensure:
- ✅ No generic namespace prefixes (ns1, ns2, ns3)
- ✅ All semantic namespaces properly used
- ✅ Bidirectional relationships correctly represented
- ✅ Hierarchies properly structured
- ✅ Transitive affiliations through authors captured

## Next Steps

Future enhancements:
1. Add Grant → Organization relationships
2. Implement publication venue → organization affiliations
3. Support multi-level organizational hierarchies
4. Add temporal aspects (author moved from org A to org B)
5. Support collaborative networks between organizations

## Testing

Run the test suite to validate improvements:

```bash
pytest tests/mappers/test_enrichment_rdf.py -v
pytest tests/models/test_models_rdf.py -v
```

Check the generated RDF:

```bash
cat test_output/institutional_improved.ttl
```

## References

- W3C Organizational Ontology: https://www.w3.org/ns/org
- FOAF Vocabulary: http://xmlns.com/foaf/0.1/
- Dublin Core Terms: https://purl.org/dc/terms/
- BIBO Bibliography Ontology: http://purl.org/ontology/bibo/
