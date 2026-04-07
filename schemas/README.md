# PyEuropePMC Modular LinkML Schema

## Overview

The PyEuropePMC LinkML schema has been restructured into a modular, maintainable format. This organization improves clarity, makes updates easier, and enables better collaboration.

## Schema Structure

```
schemas/
├── pyeuropepmc_schema.yaml     # Main entry point (imports all modules)
├── base.yaml                    # Core metadata and namespace prefixes
├── enums.yaml                   # Controlled vocabularies
├── slots.yaml                   # Reusable attribute definitions
└── entities/                    # Entity class definitions
    ├── base.yaml               # BaseEntity and ScholarlyWorkEntity
    ├── affiliation.yaml        # AffiliationEntity
    ├── author.yaml             # AuthorEntity
    ├── figure.yaml             # FigureEntity
    ├── grant.yaml              # GrantEntity
    ├── institution.yaml        # InstitutionEntity
    ├── journal.yaml            # JournalEntity
    ├── paper.yaml              # PaperEntity
    ├── reference.yaml          # ReferenceEntity
    ├── section.yaml            # SectionEntity and CitationContextEntity
    └── table.yaml              # TableEntity and TableRowEntity
```

## Module Descriptions

### Core Modules

- **pyeuropepmc_schema.yaml**: Main schema file that imports all modules. Use this as the entry point for code generation.
- **base.yaml**: Contains schema metadata, namespace prefixes, and imports for LinkML types.
- **enums.yaml**: All controlled vocabularies (OpenAccessStatus, PublicationType, InstitutionType, etc.).
- **slots.yaml**: Reusable slot definitions (attributes) used across multiple entity classes.

### Entity Modules

Each entity file contains:
- Class definition with description and ontology alignment
- Slot assignments
- Slot usage constraints
- Validation rules (where applicable)

## Usage

### Generating Python Models

```bash
# Option 1: Manual generation (basic models only)
gen-pydantic schemas/pyeuropepmc_schema.yaml > src/pyeuropepmc/models.py

# Option 2: Use the regeneration script (recommended - includes custom methods)
python scripts/regenerate_models.py
```

**Note**: The LinkML schema generates basic Pydantic model classes and fields. Custom methods (like `from_enrichment_dict()`) are maintained in `src/pyeuropepmc/models_custom.py` and automatically added when importing models. Use the regeneration script to ensure custom methods are properly included.

### Custom Methods

Some model methods are not part of the LinkML schema and are maintained separately:

- `InstitutionEntity.from_enrichment_dict()`: Creates institution entities from enrichment API data, flattening external identifiers
- Located in: `src/pyeuropepmc/models_custom.py`
- Automatically applied when models are imported

When regenerating models, these custom methods are preserved through the regeneration script.

### Generating JSON Schema

```bash
gen-json-schema schemas/pyeuropepmc_schema.yaml > schemas/pyeuropepmc.schema.json
```

### Generating OWL Ontology

```bash
gen-owl schemas/pyeuropepmc_schema.yaml > schemas/pyeuropepmc.owl.ttl
```

### Generating SHACL Shapes

```bash
gen-shacl schemas/pyeuropepmc_schema.yaml > shacl/pyeuropepmc.shacl.ttl
```

## Development Workflow

### Adding a New Entity Class

1. Create a new file in `schemas/entities/` (e.g., `my_entity.yaml`)
2. Define the class with appropriate slots and constraints
3. Add the import to `schemas/pyeuropepmc_schema.yaml`
4. Regenerate Python models and validation artifacts

### Adding a New Slot

1. Add the slot definition to `schemas/slots.yaml`
2. Reference the slot in entity class definitions
3. Regenerate artifacts

### Adding a New Enum

1. Add the enum definition to `schemas/enums.yaml`
2. Reference the enum as a slot range in entity classes
3. Regenerate artifacts

### Modifying an Entity

1. Edit the appropriate file in `schemas/entities/`
2. Regenerate Python models to reflect changes
3. Run tests to ensure compatibility

## Migration from Manual Models

As of December 2024, PyEuropePMC has migrated from manual dataclasses to LinkML-generated Pydantic models:

- **Old manual models**: Archived in `src/pyeuropepmc/models/archive/`
- **New generated models**: Located in `src/pyeuropepmc/models/generated.py`
- **Import path**: All models imported from `pyeuropepmc.models`

### Benefits of LinkML-Generated Models

1. **Single Source of Truth**: Schema definition drives all artifacts
2. **Automatic Validation**: Pydantic provides runtime validation
3. **Multiple Formats**: Generate Python, JSON Schema, OWL, SHACL from one source
4. **Type Safety**: Full type annotations for IDE support
5. **Ontology Alignment**: Built-in RDF/OWL mappings for semantic web integration

## Backups

The following backups are available:

- `schemas/pyeuropepmc_schema_backup.yaml`: Backup of monolithic schema before modularization
- `schemas/pyeuropepmc_schema_old.yaml`: Previous version of monolithic schema
- `src/pyeuropepmc/models/archive/`: All manual dataclass files
- `src/pyeuropepmc/models/generated_backup_modular.py`: Backup before modular schema generation

## Validation

All generated models include:

- Pattern-based validation (DOI, ORCID, PMCID, etc.)
- Range constraints (years, confidence scores, coordinates)
- Required field enforcement
- Type checking
- Cardinality constraints

## Testing

Test that all models can be imported and instantiated:

```python
from pyeuropepmc.models import (
    PaperEntity, AuthorEntity, InstitutionEntity, JournalEntity
)

author = AuthorEntity(full_name='Jane Doe', orcid='0000-0001-2345-6789')
paper = PaperEntity(title='My Research', pmcid='PMC1234567')
```

## References

- [LinkML Documentation](https://linkml.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [PyEuropePMC Project Instructions](.github/instructions/copilot-instructions.md)
