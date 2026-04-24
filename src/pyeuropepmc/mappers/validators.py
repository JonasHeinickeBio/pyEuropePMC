"""
Data validation utilities for PyEuropePMC RDF conversion.

This module provides functions for validating different data sources
before RDF conversion.
"""

from typing import Any

from pyeuropepmc.mappers.converters import RDFConversionError


def validate_search_results(search_results: Any) -> None:
    """
    Validate search results data structure.

    Parameters
    ----------
    search_results : Any
        Search results to validate

    Raises
    ------
    RDFConversionError
        If search results are invalid
    """
    if search_results is None:
        raise RDFConversionError("Search results cannot be None")

    if not search_results:
        raise RDFConversionError("Search results cannot be empty")

    # Check type
    if not isinstance(search_results, list | dict):
        raise RDFConversionError("Search results must be a list or dict")

    # If it's a list, check that it contains dicts
    if isinstance(search_results, list) and not all(
        isinstance(item, dict) for item in search_results
    ):
        raise RDFConversionError("All search results must be dictionaries")


def validate_xml_data(xml_data: Any) -> None:
    """
    Validate XML parsing results data structure.

    Parameters
    ----------
    xml_data : Any
        XML data to validate

    Raises
    ------
    RDFConversionError
        If XML data is invalid
    """
    if xml_data is None:
        raise RDFConversionError("XML data cannot be None")

    if not xml_data:
        raise RDFConversionError("XML data cannot be empty")

    # Check type
    if not isinstance(xml_data, dict):
        raise RDFConversionError("XML data must be a dictionary")


def validate_enrichment_data(enrichment_data: Any) -> None:
    """
    Validate enrichment data structure.

    Parameters
    ----------
    enrichment_data : Any
        Enrichment data to validate

    Raises
    ------
    RDFConversionError
        If enrichment data is invalid
    """
    if enrichment_data is None:
        raise RDFConversionError("Enrichment data cannot be None")

    if not enrichment_data:
        raise RDFConversionError("Enrichment data cannot be empty")

    # Check type
    if not isinstance(enrichment_data, dict):
        raise RDFConversionError("Enrichment data must be a dictionary")
