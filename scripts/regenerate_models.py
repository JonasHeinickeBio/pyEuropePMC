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

    # Patch ReferenceEntity to allow journal to be Union[str, JournalEntity]
    with open(models_file) as f:
        content = f.read()

    import re

    # Patch ReferenceEntity: change journal field to Union[str, JournalEntity, None]
    # The journal field is inherited from ScholarlyWorkEntity, so we need to patch it
    # in the ReferenceEntity class definition
    pattern_ref_journal = r"(class ReferenceEntity.*?)(journal: Optional\[JournalEntity\])"

    def replace_ref_journal(match):
        return match.group(1) + "journal: Union[str, JournalEntity, None]"

    content = re.sub(pattern_ref_journal, replace_ref_journal, content, flags=re.DOTALL)

    # Patch PaperEntity: change journal field to Union[str, JournalEntity, None]
    pattern_paper_journal = r"(class PaperEntity.*?)(journal: Optional\[JournalEntity\])"

    def replace_paper_journal(match):
        return match.group(1) + "journal: Union[str, JournalEntity, None]"

    content = re.sub(pattern_paper_journal, replace_paper_journal, content, flags=re.DOTALL)

    # Add DOI normalization to pattern_doi validators
    # This normalizes DOI URLs by stripping prefixes and lowercasing
    doi_validator_patch = '''    @field_validator('doi')
    def pattern_doi(cls, v):
        import re

        def normalize_doi(doi_str):
            """Normalize DOI by stripping prefixes and lowercasing."""
            doi_str = doi_str.strip().lower()
            doi_str = re.sub(r"^https://doi\\.org/", "", doi_str)
            doi_str = re.sub(r"^http://doi\\.org/", "", doi_str)
            doi_str = re.sub(r"^http://dx\\.doi\\.org/", "", doi_str)
            return doi_str

        pattern = re.compile(r"^10\\.\\d{4,9}/[-._;()/:a-zA-Z0-9]+$")
        if isinstance(v, list):
            normalized = []
            for element in v:
                if isinstance(element, str):
                    element = normalize_doi(element)
                    if not pattern.match(element):
                        err_msg = f"Invalid doi format: {element}"
                        raise ValueError(err_msg)
                    normalized.append(element)
                else:
                    normalized.append(element)
            return normalized
        elif isinstance(v, str):
            v = normalize_doi(v)
            if not pattern.match(v):
                err_msg = f"Invalid doi format: {v}"
                raise ValueError(err_msg)
            return v
        return v

    @field_validator('pmcid')
    def pattern_pmcid(cls, v):
        pattern=re.compile(r"^PMC\\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmcid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmcid format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('pmid')
    def pattern_pmid(cls, v):
        pattern=re.compile(r"^\\d+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid pmid format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid pmid format: {v}"
            raise ValueError(err_msg)
        return v

'''

    # Find and replace the DOI validator section
    # We need to find all pattern_doi validators and replace them
    # The pattern_doi validator appears in multiple classes (ScholarlyWorkEntity and possibly others)
    # We'll use a simpler approach: replace the entire validator section

    # First, let's identify the DOI validator pattern in the file
    import re

    # Pattern to match a DOI validator
    doi_validator_pattern = (
        r"(@field_validator\("
        "'doi'"
        "\\)\\s+def pattern_doi\\(cls, v\\):.*?(?=\n    @field_validator|\n    class |\\Z))"
    )

    def replace_doi_validator(match):
        return doi_validator_patch.strip()

    content = re.sub(doi_validator_pattern, replace_doi_validator, content, flags=re.DOTALL)

    with open(models_file, "w") as f:
        f.write(content)

    print("Model regeneration complete!")


if __name__ == "__main__":
    regenerate_models()
