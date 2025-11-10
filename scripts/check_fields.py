#!/usr/bin/env python3
"""
Script to validate Europe PMC field coverage.

This script checks if all fields from the Europe PMC API are
included in the QueryBuilder FieldType definition.

Usage:
    python scripts/check_fields.py
"""

from __future__ import annotations

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyeuropepmc.query_builder import validate_field_coverage


def main() -> int:
    """Run field coverage validation."""
    try:
        result = validate_field_coverage(verbose=True)

        # Exit with error code if not up to date
        return 0 if result["up_to_date"] else 1

    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install requests: pip install requests")
        return 2
    except Exception as e:
        print(f"Error: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
