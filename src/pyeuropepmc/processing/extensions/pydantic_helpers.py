"""
Pydantic Model Integration for pyEuropePMC.

Provides utilities for generating Pydantic v2 models from existing dataclasses,
enabling runtime type validation, JSON Schema generation, and better IDE support.

Based on patterns from pubmed-types (xsdata-pydantic approach).

Usage::

    # Convert existing results to validated Pydantic models
    generator = PydanticModelGenerator()
    ArticleModel = generator.generate_model("Article", {"title": str, "doi": str})

    # Or convert a dict from parser output
    article = ArticleModel(**parser.extract_metadata())

Note
----
This module requires ``pydantic>=2.0``. If pydantic is not installed, the
import will fail gracefully and the module won't be available.
"""

from __future__ import annotations

from dataclasses import MISSING
import logging
from typing import Any, get_type_hints

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, create_model

    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    BaseModel = None
    Field = None
    create_model = None
    _HAS_PYDANTIC = False


def has_pydantic() -> bool:
    """Check whether pydantic v2 is installed."""
    return _HAS_PYDANTIC


def dataclass_to_pydantic(
    dc: type,
    model_name: str | None = None,
    include_fields: list[str] | None = None,
    exclude_fields: list[str] | None = None,
) -> type[BaseModel]:
    """
    Convert a Python dataclass to a Pydantic v2 model.

    Parameters
    ----------
    dc : type
        The dataclass to convert.
    model_name : str, optional
        Name for the generated model. Defaults to the dataclass name.
    include_fields : list[str], optional
        Only include these fields (all if None).
    exclude_fields : list[str], optional
        Exclude these fields (none if None).

    Returns
    -------
    type[BaseModel]
        A new Pydantic model class.

    Raises
    ------
    ImportError
        If pydantic is not installed.

    Examples
    --------
    >>> @dataclass
    ... class Author:
    ...     name: str
    ...     orcid: str = ""
    ...
    >>> AuthorModel = dataclass_to_pydantic(Author)
    >>> author = AuthorModel(name="John Doe", orcid="0000-0002-1825-0097")
    >>> author.model_dump()
    {'name': 'John Doe', 'orcid': '0000-0002-1825-0097'}
    """
    if not _HAS_PYDANTIC:
        raise ImportError("pydantic>=2.0 is required. Install with: pip install pydantic")

    if model_name is None:
        model_name = dc.__name__

    # Get type hints and field definitions
    type_hints = get_type_hints(dc)
    fields: dict[str, tuple[type, Any]] = {}

    for field_name, field_type in type_hints.items():
        if include_fields and field_name not in include_fields:
            continue
        if exclude_fields and field_name in exclude_fields:
            continue

        # Get default from dataclass field
        dc_field: Any = None
        if hasattr(dc, "__dataclass_fields__"):
            dc_field = dc.__dataclass_fields__.get(field_name)

        if dc_field and dc_field.default_factory is not MISSING:
            # Field has a default_factory; invoke it
            try:
                default = dc_field.default_factory()
            except Exception:
                default = None
        else:
            default = dc_field.default if dc_field else ...

        # Wrap in Pydantic Field for metadata
        if dc_field and dc_field.metadata:
            fields[field_name] = (
                field_type,
                Field(default=default, **dc_field.metadata),
            )
        else:
            # Standard annotation: (type, default)
            fields[field_name] = (field_type, default)

    return create_model(model_name, **fields)  # type: ignore


class PydanticModelGenerator:
    """
    Generates Pydantic models from parser output data.

    Useful for creating validated schemas from the dict output of parsers.

    Examples
    --------
    >>> generator = PydanticModelGenerator()
    >>> # Create a model from data
    >>> metadata = parser.extract_metadata()
    >>> MetadataModel = generator.generate_model(
    ...     "Metadata", metadata, optional_defaults=True
    ... )
    >>> validated = MetadataModel(**metadata)
    """

    def __init__(self) -> None:
        if not _HAS_PYDANTIC:
            raise ImportError("pydantic>=2.0 is required. Install with: pip install pydantic")

    @staticmethod
    def generate_model(
        model_name: str,
        sample_data: dict[str, Any] | None = None,
        field_types: dict[str, type] | None = None,
        optional_defaults: bool = True,
    ) -> type[BaseModel]:
        """
        Generate a Pydantic model from sample data or explicit field types.

        Parameters
        ----------
        model_name : str
            Name for the generated model.
        sample_data : dict, optional
            Sample data to infer field types from.
        field_types : dict, optional
            Explicit field type definitions (overrides inference).
        optional_defaults : bool, optional
            If True, all fields default to None (making them optional).

        Returns
        -------
        type[BaseModel]
            Generated Pydantic model class.

        Examples
        --------
        >>> # From sample data
        >>> model = generator.generate_model("Article", {"id": "123", "title": "..."})

        >>> # With explicit types
        >>> model = generator.generate_model(
        ...     "Article",
        ...     field_types={"id": str, "title": str, "year": int},
        ... )
        """
        fields: dict[str, tuple[type, Any]] = {}

        # Use explicit field types if provided
        if field_types:
            for field_name, field_type in field_types.items():
                default = None if optional_defaults else ...
                fields[field_name] = (field_type, default)

        # Infer from sample data (as fallback or supplement)
        if sample_data:
            for key, value in sample_data.items():
                if key in fields:
                    continue  # Explicit type takes precedence
                inferred_type: Any = type(value) if value is not None else str
                # Handle optional/list types
                if isinstance(value, list):
                    inferred_type = list[type(value[0])] if value else list[str]
                elif isinstance(value, dict):
                    inferred_type = dict[str, Any]

                default = None if optional_defaults else value
                fields[key] = (inferred_type, default)

        return create_model(model_name, **fields)  # type: ignore

    @classmethod
    def from_dataclass(
        cls,
        dc: type,
        model_name: str | None = None,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> type[BaseModel]:
        """
        Generate a Pydantic model from a dataclass.

        Convenience wrapper around ``dataclass_to_pydantic``.

        Parameters
        ----------
        dc : type
            The dataclass to convert.
        model_name : str, optional
            Name for the generated model.
        include_fields : list[str], optional
            Fields to include.
        exclude_fields : list[str], optional
            Fields to exclude.

        Returns
        -------
        type[BaseModel]
            Pydantic model class.
        """
        return dataclass_to_pydantic(
            dc,
            model_name=model_name,
            include_fields=include_fields,
            exclude_fields=exclude_fields,
        )
