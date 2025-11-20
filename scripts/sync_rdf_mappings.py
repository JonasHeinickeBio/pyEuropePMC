#!/usr/bin/env python3
"""
Synchronize RML mappings from YAML configuration.

This script reads rdf_map.yml as the source of truth and generates
rml_mappings.ttl to keep both mapping files synchronized.
"""

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_yaml_config(yaml_path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_rml_header(prefixes: dict[str, str]) -> str:
    """Generate RML header with namespace prefixes."""
    lines = [
        "@prefix rr: <http://www.w3.org/ns/r2rml#> .",
        "@prefix rml: <http://semweb.mmlab.be/ns/rml#> .",
        "@prefix ql: <http://semweb.mmlab.be/ns/ql#> .",
    ]
    
    # Add custom namespace prefixes from YAML
    for prefix, uri in prefixes.items():
        # Special handling for some prefixes that need short forms in RML
        if prefix == "dct":
            lines.append(f"@prefix dcterms: <{uri}> .")
        else:
            lines.append(f"@prefix {prefix}: <{uri}> .")
    
    lines.extend([
        "@prefix ex: <http://example.org/> .",
        "@prefix data: <http://example.org/data/> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "# RML Mappings for PyEuropePMC Data Models",
        "# Auto-generated from rdf_map.yml - DO NOT EDIT MANUALLY",
        "# Run 'python scripts/sync_rdf_mappings.py' to regenerate",
        "",
    ])
    
    return "\n".join(lines)


def get_rml_prefix(predicate: str) -> str:
    """Convert YAML predicate to RML prefix notation."""
    # Special case for dct -> dcterms in RML
    if predicate.startswith("dct:"):
        return predicate.replace("dct:", "dcterms:")
    return predicate


def generate_entity_mapping(
    entity_name: str, entity_config: dict[str, Any], is_last: bool = False
) -> str:
    """Generate RML mapping for a single entity."""
    lines = []
    
    # Determine source file name
    source_file = f"{entity_name.lower().replace('entity', '')}.json"
    if entity_name == "TableRowEntity":
        source_file = "table_rows.json"
    elif entity_name == "AuthorEntity":
        source_file = "authors.json"
    elif entity_name == "InstitutionEntity":
        source_file = "institutions.json"
    elif entity_name == "SectionEntity":
        source_file = "sections.json"
    elif entity_name == "ReferenceEntity":
        source_file = "references.json"
    elif entity_name == "TableEntity":
        source_file = "tables.json"
    elif entity_name == "FigureEntity":
        source_file = "figures.json"
    
    # Header
    lines.append(f"# ===== {entity_name} Mapping =====")
    lines.append(f"<#{entity_name}Map>")
    lines.append("    rml:logicalSource [")
    lines.append(f'        rml:source "{source_file}" ;')
    lines.append("        rml:referenceFormulation ql:JSONPath ;")
    lines.append('        rml:iterator "$[*]"')
    lines.append("    ] ;")
    lines.append("")
    
    # Subject map with rdf:type
    rdf_types = entity_config.get("rdf:type", [])
    if isinstance(rdf_types, list) and rdf_types:
        rdf_type = get_rml_prefix(rdf_types[0])
    else:
        rdf_type = "ex:Entity"
    
    lines.append("    rr:subjectMap [")
    lines.append('        rr:template "http://example.org/data/' + 
                 entity_name.lower().replace("entity", "") + '/{id}" ;')
    lines.append(f"        rr:class {rdf_type}")
    lines.append("    ] ;")
    lines.append("")
    
    # Fields mapping
    fields = entity_config.get("fields", {})
    for field_name, predicate in fields.items():
        rml_predicate = get_rml_prefix(predicate)
        lines.append("    rr:predicateObjectMap [")
        lines.append(f"        rr:predicate {rml_predicate} ;")
        
        # Check if field should be IRI (for URIs)
        if field_name in ["source_uri", "orcid", "ror_id", "openalex_id", "website"]:
            lines.append(f'        rr:objectMap [ rml:reference "{field_name}" ; rr:termType rr:IRI ]')
        else:
            lines.append(f'        rr:objectMap [ rml:reference "{field_name}" ]')
        lines.append("    ] ;")
        lines.append("")
    
    # Multi-value fields mapping
    multi_value_fields = entity_config.get("multi_value_fields", {})
    for field_name, predicate in multi_value_fields.items():
        rml_predicate = get_rml_prefix(predicate)
        lines.append("    rr:predicateObjectMap [")
        lines.append(f"        rr:predicate {rml_predicate} ;")
        lines.append(f'        rr:objectMap [ rml:reference "{field_name}[*]" ]')
        lines.append("    ] ;")
        lines.append("")
    
    # Add label mapping if not already present
    if "label" not in fields:
        lines.append("    rr:predicateObjectMap [")
        lines.append("        rr:predicate rdfs:label ;")
        lines.append('        rr:objectMap [ rml:reference "label" ]')
        lines.append("    ] ;")
        lines.append("")
    
    # Remove trailing " ;" from last predicateObjectMap and add " ."
    if lines[-2].strip().endswith("] ;"):
        lines[-2] = lines[-2].replace("] ;", "] .")
    
    # Remove extra blank line at end
    while lines and lines[-1] == "":
        lines.pop()
    
    lines.append("")
    
    return "\n".join(lines)


def sync_mappings(yaml_path: Path, rml_path: Path) -> None:
    """
    Synchronize RML mappings from YAML configuration.
    
    Parameters
    ----------
    yaml_path : Path
        Path to rdf_map.yml
    rml_path : Path
        Path to rml_mappings.ttl to be generated
    """
    print(f"Loading YAML configuration from {yaml_path}")
    config = load_yaml_config(yaml_path)
    
    # Extract prefixes
    prefixes = config.get("_@prefix", {})
    
    # Generate RML content
    print("Generating RML mappings...")
    rml_content = []
    
    # Add header
    rml_content.append(generate_rml_header(prefixes))
    
    # Generate mappings for each entity
    entity_names = [key for key in config.keys() if key.endswith("Entity")]
    for i, entity_name in enumerate(entity_names):
        entity_config = config[entity_name]
        is_last = (i == len(entity_names) - 1)
        rml_content.append(generate_entity_mapping(entity_name, entity_config, is_last))
    
    # Write to file
    full_content = "\n".join(rml_content)
    print(f"Writing RML mappings to {rml_path}")
    with open(rml_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    
    print("✓ Successfully synchronized RML mappings from YAML configuration")
    print(f"  Generated {len(entity_names)} entity mappings")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Synchronize RML mappings from YAML configuration"
    )
    parser.add_argument(
        "--yaml",
        type=Path,
        default=Path("conf/rdf_map.yml"),
        help="Path to YAML configuration file (default: conf/rdf_map.yml)",
    )
    parser.add_argument(
        "--rml",
        type=Path,
        default=Path("conf/rml_mappings.ttl"),
        help="Path to RML output file (default: conf/rml_mappings.ttl)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files are in sync without modifying",
    )
    
    args = parser.parse_args()
    
    # Validate paths
    if not args.yaml.exists():
        print(f"Error: YAML file not found: {args.yaml}")
        return 1
    
    if args.check:
        # TODO: Implement check mode
        print("Check mode not yet implemented")
        return 1
    
    # Sync mappings
    try:
        sync_mappings(args.yaml, args.rml)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
