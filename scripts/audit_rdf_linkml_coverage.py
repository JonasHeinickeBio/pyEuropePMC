#!/usr/bin/env python3
"""
Audit script to compare rdf_map.yml mappings against LinkML schema definitions.

This script provides a comprehensive gap analysis to determine:
1. Which mappings in rdf_map.yml are covered by the LinkML schema
2. Which mappings are missing from the LinkML schema
3. Any custom logic or transformations not expressible in LinkML

Usage:
    python scripts/audit_rdf_linkml_coverage.py

Output:
    - Console report with coverage statistics
    - JSON report file for detailed analysis
"""

import json
import os
from pathlib import Path
from typing import Any

import yaml

# Try to import LinkML runtime
try:
    from linkml_runtime.utils.schemaview import SchemaView

    LINKML_AVAILABLE = True
except ImportError:
    LINKML_AVAILABLE = False
    print("WARNING: linkml_runtime not available. Install with: pip install linkml-runtime")


def load_rdf_map(config_path: str | None = None) -> dict[str, Any]:
    """Load the rdf_map.yml configuration file."""
    if config_path is None:
        base_path = Path(__file__).parent.parent
        config_path = str(base_path / "conf" / "rdf_map.yml")

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_linkml_schema(schema_path: str | None = None) -> SchemaView | None:
    """Load the LinkML schema using SchemaView."""
    if not LINKML_AVAILABLE:
        return None

    if schema_path is None:
        base_path = Path(__file__).parent.parent
        schema_path = str(base_path / "schemas" / "pyeuropepmc_schema.yaml")

    return SchemaView(schema_path)


def extract_rdf_map_fields(rdf_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract all field mappings from rdf_map.yml organized by entity."""
    entity_fields = {}

    for key, value in rdf_map.items():
        # Skip metadata keys
        if key.startswith("_"):
            continue

        if isinstance(value, dict):
            entity_name = key
            entity_fields[entity_name] = {
                "rdf_types": value.get("rdf:type", []),
                "fields": value.get("fields", {}),
                "multi_value_fields": value.get("multi_value_fields", {}),
                "relationships": value.get("relationships", {}),
            }

    return entity_fields


def extract_linkml_fields(schema_view: SchemaView) -> dict[str, dict[str, Any]]:
    """Extract all field definitions from the LinkML schema organized by class."""
    class_fields = {}

    for class_name in schema_view.all_classes():
        cls = schema_view.get_class(class_name)
        slots = schema_view.class_slots(class_name)

        # Get slot URIs for each slot
        slot_uris = {}
        multivalued_slots = {}
        relationship_slots = {}

        for slot_name in slots:
            slot = schema_view.get_slot(slot_name)
            if slot:
                slot_uri = slot.slot_uri
                is_multivalued = slot.multivalued
                slot_range = slot.range

                # Check if it's a relationship (range is another class)
                is_relationship = slot_range and slot_range in schema_view.all_classes()

                if is_relationship:
                    relationship_slots[slot_name] = {
                        "slot_uri": str(slot_uri) if slot_uri else None,
                        "range": slot_range,
                        "inverse": slot.inverse if hasattr(slot, "inverse") else None,
                        "multivalued": is_multivalued,
                    }
                elif is_multivalued:
                    multivalued_slots[slot_name] = {
                        "slot_uri": str(slot_uri) if slot_uri else None,
                        "range": str(slot_range) if slot_range else None,
                    }
                else:
                    slot_uris[slot_name] = {
                        "slot_uri": str(slot_uri) if slot_uri else None,
                        "range": str(slot_range) if slot_range else None,
                    }

        class_fields[class_name] = {
            "class_uri": str(cls.class_uri) if cls.class_uri else None,
            "is_a": cls.is_a,
            "fields": slot_uris,
            "multi_value_fields": multivalued_slots,
            "relationships": relationship_slots,
        }

    return class_fields


def compare_mappings(
    rdf_map_fields: dict[str, dict[str, Any]],
    linkml_fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare rdf_map.yml mappings with LinkML schema definitions."""
    report = {
        "summary": {
            "rdf_map_entities": len(rdf_map_fields),
            "linkml_classes": len(linkml_fields),
            "fully_covered": 0,
            "partially_covered": 0,
            "not_covered": 0,
        },
        "entities": {},
        "missing_from_linkml": [],
        "extra_in_linkml": [],
        "field_coverage": {},
    }

    # Check each rdf_map entity against LinkML
    for entity_name, entity_data in rdf_map_fields.items():
        if entity_name not in linkml_fields:
            report["missing_from_linkml"].append(entity_name)
            report["summary"]["not_covered"] += 1
            continue

        linkml_entity = linkml_fields[entity_name]
        entity_report = {
            "covered_fields": [],
            "missing_fields": [],
            "covered_multi_value": [],
            "missing_multi_value": [],
            "covered_relationships": [],
            "missing_relationships": [],
            "predicate_mismatches": [],
        }

        # Check single-value fields
        for field_name, field_config in entity_data.get("fields", {}).items():
            rdf_predicate = field_config.get("predicate", "")
            if field_name in linkml_entity["fields"]:
                linkml_slot = linkml_entity["fields"][field_name]
                entity_report["covered_fields"].append(field_name)

                # Check predicate match (allowing for prefix differences)
                if linkml_slot.get("slot_uri"):
                    linkml_pred_local = linkml_slot["slot_uri"].split("/")[-1].split("#")[-1]
                    rdf_pred_local = rdf_predicate.split(":")[-1] if ":" in rdf_predicate else rdf_predicate
                    if linkml_pred_local != rdf_pred_local:
                        entity_report["predicate_mismatches"].append({
                            "field": field_name,
                            "rdf_map": rdf_predicate,
                            "linkml": linkml_slot["slot_uri"],
                        })
            else:
                entity_report["missing_fields"].append(field_name)

        # Check multi-value fields
        for field_name, predicate in entity_data.get("multi_value_fields", {}).items():
            if field_name in linkml_entity["multi_value_fields"]:
                entity_report["covered_multi_value"].append(field_name)
            else:
                entity_report["missing_multi_value"].append(field_name)

        # Check relationships
        for rel_name, rel_config in entity_data.get("relationships", {}).items():
            if rel_name in linkml_entity["relationships"]:
                entity_report["covered_relationships"].append(rel_name)
            else:
                entity_report["missing_relationships"].append(rel_name)

        # Calculate coverage for this entity
        total_items = (
            len(entity_data.get("fields", {}))
            + len(entity_data.get("multi_value_fields", {}))
            + len(entity_data.get("relationships", {}))
        )
        covered_items = (
            len(entity_report["covered_fields"])
            + len(entity_report["covered_multi_value"])
            + len(entity_report["covered_relationships"])
        )

        coverage_pct = (covered_items / total_items * 100) if total_items > 0 else 100
        entity_report["coverage_percentage"] = coverage_pct

        if coverage_pct == 100:
            report["summary"]["fully_covered"] += 1
        elif coverage_pct > 0:
            report["summary"]["partially_covered"] += 1
        else:
            report["summary"]["not_covered"] += 1

        report["entities"][entity_name] = entity_report
        report["field_coverage"][entity_name] = coverage_pct

    # Check for extra classes in LinkML not in rdf_map
    for class_name in linkml_fields:
        if class_name not in rdf_map_fields and not class_name.startswith("Base"):
            report["extra_in_linkml"].append(class_name)

    # Calculate overall coverage
    total_coverage = sum(report["field_coverage"].values())
    num_entities = len(report["field_coverage"])
    report["summary"]["average_coverage"] = (
        total_coverage / num_entities if num_entities > 0 else 0
    )

    return report


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted audit report to console."""
    print("\n" + "=" * 80)
    print("RDF_MAP.YML vs LINKML SCHEMA COVERAGE AUDIT")
    print("=" * 80)

    summary = report["summary"]
    print(f"\nSUMMARY:")
    print(f"  - Entities in rdf_map.yml: {summary['rdf_map_entities']}")
    print(f"  - Classes in LinkML schema: {summary['linkml_classes']}")
    print(f"  - Fully covered: {summary['fully_covered']}")
    print(f"  - Partially covered: {summary['partially_covered']}")
    print(f"  - Not covered: {summary['not_covered']}")
    print(f"  - Average coverage: {summary['average_coverage']:.1f}%")

    if report["missing_from_linkml"]:
        print(f"\nENTITIES MISSING FROM LINKML:")
        for entity in report["missing_from_linkml"]:
            print(f"  - {entity}")

    print("\nDETAILED ENTITY COVERAGE:")
    for entity_name, entity_data in report["entities"].items():
        coverage = entity_data["coverage_percentage"]
        status = "✓" if coverage == 100 else "△" if coverage > 50 else "✗"
        print(f"\n  {status} {entity_name} ({coverage:.1f}% coverage)")

        if entity_data["missing_fields"]:
            print(f"      Missing fields: {', '.join(entity_data['missing_fields'])}")
        if entity_data["missing_multi_value"]:
            print(f"      Missing multi-value: {', '.join(entity_data['missing_multi_value'])}")
        if entity_data["missing_relationships"]:
            print(f"      Missing relationships: {', '.join(entity_data['missing_relationships'])}")
        if entity_data["predicate_mismatches"]:
            print("      Predicate mismatches:")
            for mismatch in entity_data["predicate_mismatches"]:
                print(f"        - {mismatch['field']}: {mismatch['rdf_map']} vs {mismatch['linkml']}")

    print("\n" + "=" * 80)
    print("RECOMMENDATION:")

    avg_coverage = summary["average_coverage"]
    if avg_coverage >= 95:
        print("  ✓ LinkML schema has excellent coverage of rdf_map.yml mappings.")
        print("  → Safe to deprecate rdf_map.yml and use LinkML as source of truth.")
    elif avg_coverage >= 80:
        print("  △ LinkML schema has good coverage but some gaps exist.")
        print("  → Consider migrating remaining fields before deprecating rdf_map.yml.")
    else:
        print("  ✗ Significant gaps exist between rdf_map.yml and LinkML schema.")
        print("  → Keep rdf_map.yml as legacy and continue migration.")

    print("=" * 80 + "\n")


def save_report(report: dict[str, Any], output_path: str | None = None) -> None:
    """Save the audit report as JSON."""
    if output_path is None:
        base_path = Path(__file__).parent.parent
        output_path = str(base_path / "audit_report.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Detailed report saved to: {output_path}")


def main() -> dict[str, Any]:
    """Run the audit and generate report."""
    print("Loading rdf_map.yml...")
    rdf_map = load_rdf_map()
    rdf_map_fields = extract_rdf_map_fields(rdf_map)

    print("Loading LinkML schema...")
    schema_view = load_linkml_schema()

    if schema_view is None:
        print("ERROR: Could not load LinkML schema. Ensure linkml-runtime is installed.")
        return {}

    linkml_fields = extract_linkml_fields(schema_view)

    print("Comparing mappings...")
    report = compare_mappings(rdf_map_fields, linkml_fields)

    print_report(report)
    save_report(report)

    return report


if __name__ == "__main__":
    main()
