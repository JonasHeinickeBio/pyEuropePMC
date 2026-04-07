#!/usr/bin/env python3
"""
Script to regenerate PyEuropePMC models from LinkML schema.

This script:
1. Regenerates Pydantic models from the LinkML schema
2. Adds custom methods that are not part of the schema
3. Ensures the models are ready for use

Usage:
    python scripts/regenerate_models.py
"""

from pathlib import Path
import subprocess
import sys


def regenerate_models():
    """Regenerate models from LinkML schema and add custom methods."""

    project_root = Path(__file__).parent.parent
    schema_file = project_root / "schemas" / "pyeuropepmc_schema.yaml"
    models_file = project_root / "src" / "pyeuropepmc" / "models" / "__init__.py"

    print("Regenerating Pydantic models from LinkML schema...")

    # Run gen-pydantic to generate the base models
    cmd = ["gen-pydantic", str(schema_file), ">", str(models_file)]

    result = subprocess.run(" ".join(cmd), shell=True, cwd=project_root)

    if result.returncode != 0:
        print(f"Error regenerating models: {result.returncode}")
        sys.exit(1)

    print("Models regenerated successfully.")

    # Add the import for custom methods at the end of models.py
    with open(models_file) as f:
        content = f.read()

    # Check if the custom import is already there
    if "from . import models_custom" not in content:
        # Add the import after the model rebuilds
        rebuild_section = "# Model rebuild\n# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model"
        custom_import = "\n# Import custom methods to extend generated models\nfrom . import models_custom  # noqa: E402,F401"

        if rebuild_section in content:
            content = content.replace(rebuild_section, rebuild_section + custom_import)

            with open(models_file, "w") as f:
                f.write(content)

            print("Added custom methods import to models.py")
        else:
            print("Warning: Could not find model rebuild section to add custom import")

    print("Model regeneration complete!")


if __name__ == "__main__":
    regenerate_models()
