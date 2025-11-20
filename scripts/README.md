# PyEuropePMC Scripts

This directory contains utility scripts for maintaining and working with PyEuropePMC.

## RDF Mapping Synchronization

### sync_rdf_mappings.py

**Purpose**: Automatically synchronize RML mappings from the YAML configuration file.

The YAML file (`conf/rdf_map.yml`) is the **source of truth** for all RDF mappings. This script reads the YAML configuration and generates the corresponding RML Turtle file (`conf/rml_mappings.ttl`).

**Usage**:

```bash
# Sync mappings (default paths)
python scripts/sync_rdf_mappings.py

# Specify custom paths
python scripts/sync_rdf_mappings.py --yaml conf/rdf_map.yml --rml conf/rml_mappings.ttl

# Show help
python scripts/sync_rdf_mappings.py --help
```

**When to run**:
- After modifying `conf/rdf_map.yml`
- After adding new entity types
- After changing field mappings or predicates

**What it does**:
1. Reads the YAML configuration (`conf/rdf_map.yml`)
2. Extracts namespace prefixes
3. Generates RML mappings for each entity type
4. Writes the complete RML file (`conf/rml_mappings.ttl`)

**Important notes**:
- The generated RML file includes a header indicating it's auto-generated
- Do not manually edit `conf/rml_mappings.ttl` - changes will be overwritten
- Always edit `conf/rdf_map.yml` instead
- Run this script after making changes to keep files in sync

**Example workflow**:

```bash
# 1. Edit the YAML configuration
vim conf/rdf_map.yml

# 2. Sync the RML mappings
python scripts/sync_rdf_mappings.py

# 3. Verify changes
git diff conf/rml_mappings.ttl

# 4. Test the mappings
python -m pytest tests/mappers/
```

## Other Scripts

### xml_to_rdf.py
Converts XML documents to RDF using the YAML-based RDFMapper.

### xml_to_rdf_rml.py
Converts XML documents to RDF using the RML-based RMLRDFizer.

---

For more information, see the main [PyEuropePMC documentation](../README.md).
