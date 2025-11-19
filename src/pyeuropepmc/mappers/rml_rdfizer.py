"""
RML-based RDF mapping using SDM-RDFizer.

This module provides a wrapper around the SDM-RDFizer tool to convert
PyEuropePMC entities to RDF using RML (RDF Mapping Language) mappings.

SDM-RDFizer is a tool for converting structured data to RDF using RML mappings.
Repository: https://github.com/SDM-TIB/SDM-RDFizer

Installation:
    pip install rdfizer
    # or
    poetry add rdfizer

Usage:
    python3 -m rdfizer -c /path/to/config/file

"""

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from rdflib import Graph

try:
    from rdfizer import semantify

    RDFIZER_AVAILABLE = True
except ImportError:
    RDFIZER_AVAILABLE = False

__all__ = ["RMLRDFizer", "RDFIZER_AVAILABLE"]


class RMLRDFizer:
    """
    Wrapper for SDM-RDFizer to convert entities to RDF using RML mappings.

    This class provides a high-level interface to the SDM-RDFizer, which
    executes RML (RDF Mapping Language) mappings to transform JSON data
    into RDF triples.

    Attributes
    ----------
    config_path : str
        Path to the RDFizer configuration file
    mapping_path : str
        Path to the RML mappings file (Turtle format)

    Examples
    --------
    >>> from pyeuropepmc.mappers import RMLRDFizer
    >>> from pyeuropepmc.models import PaperEntity
    >>>
    >>> rdfizer = RMLRDFizer()
    >>> paper = PaperEntity(pmcid="PMC123", title="Test")
    >>>
    >>> # Convert to RDF using RML
    >>> g = rdfizer.entities_to_rdf([paper], entity_type="paper")
    >>> print(g.serialize(format="turtle"))
    """

    def __init__(
        self,
        config_path: str | None = None,
        mapping_path: str | None = None,
    ):
        """
        Initialize the RML RDFizer wrapper.

        Parameters
        ----------
        config_path : Optional[str]
            Path to RDFizer config file. If None, uses default.
        mapping_path : Optional[str]
            Path to RML mappings file. If None, uses default.

        Raises
        ------
        ImportError
            If rdfizer package is not installed
        """
        if not RDFIZER_AVAILABLE:
            raise ImportError("rdfizer package not found. Install it with: pip install rdfizer")

        # Default to conf/rdfizer_config.ini and conf/rml_mappings.ttl
        if config_path is None:
            base_path = Path(__file__).parent.parent.parent.parent
            config_path = str(base_path / "conf" / "rdfizer_config.ini")

        if mapping_path is None:
            base_path = Path(__file__).parent.parent.parent.parent
            mapping_path = str(base_path / "conf" / "rml_mappings.ttl")

        self.config_path = config_path
        self.mapping_path = mapping_path

        # Verify files exist
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        if not os.path.exists(self.mapping_path):
            raise FileNotFoundError(f"Mapping file not found: {self.mapping_path}")

    def entities_to_rdf(
        self,
        entities: list[Any],
        entity_type: str,
        output_format: str = "turtle",
    ) -> Graph:
        """
        Convert entities to RDF using RML mappings.

        Parameters
        ----------
        entities : list[Any]
            List of entity objects to convert
        entity_type : str
            Type of entities (e.g., "paper", "author", "section")
        output_format : str
            Output format for RDF (default: "turtle")

        Returns
        -------
        Graph
            RDF graph containing the converted triples

        Examples
        --------
        >>> rdfizer = RMLRDFizer()
        >>> papers = [PaperEntity(pmcid="PMC123", title="Test")]
        >>> g = rdfizer.entities_to_rdf(papers, entity_type="paper")
        """
        # Create temporary directory for JSON data
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert entities to JSON
            self._entities_to_json(entities, entity_type, temp_dir)

            # Create empty JSON files for other entity types to avoid RDFizer errors
            self._create_empty_json_files(temp_dir)

            # Update config to point to temp directory
            temp_config = self._create_temp_config(temp_dir, entity_type)

            # Run RDFizer
            output_file = self._run_rdfizer(temp_config, temp_dir)

            # Load output into RDF graph
            g = Graph()
            if os.path.exists(output_file):
                g.parse(output_file, format="nt")  # RDFizer outputs N-Triples

            return g

    def _entities_to_json(self, entities: list[Any], entity_type: str, output_dir: str) -> str:
        """
        Convert entities to JSON files for RML processing.

        Parameters
        ----------
        entities : list[Any]
            List of entity objects
        entity_type : str
            Type of entities
        output_dir : str
            Directory to write JSON files

        Returns
        -------
        str
            Path to the created JSON file
        """
        # Determine filename based on entity type
        filename_map = {
            "paper": "paper.json",
            "author": "authors.json",
            "section": "sections.json",
            "table": "tables.json",
            "reference": "references.json",
        }

        filename = filename_map.get(entity_type, f"{entity_type}.json")
        json_path = os.path.join(output_dir, filename)

        # Convert entities to dict and write JSON
        if entity_type == "paper":
            # Always use array format for consistency
            data = [e.to_dict() for e in entities]
        else:
            # Multiple entities (list)
            data = [e.to_dict() for e in entities]

        # Filter out None values to avoid invalid RDF
        def filter_none(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: filter_none(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [filter_none(item) for item in obj]
            else:
                return obj

        data = filter_none(data)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return json_path

    def _create_empty_json_files(self, temp_dir: str) -> None:
        """
        Create empty JSON files for all entity types to avoid RDFizer errors.

        Parameters
        ----------
        temp_dir : str
            Temporary directory path
        """
        filenames = [
            "paper.json",
            "authors.json",
            "sections.json",
            "tables.json",
            "references.json",
        ]

        for filename in filenames:
            json_path = os.path.join(temp_dir, filename)
            if not os.path.exists(json_path):
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump([], f)  # Empty array

    def _create_temp_config(self, temp_dir: str, entity_type: str | None = None) -> str:
        """
        Create a temporary config file pointing to temp directory.

        Parameters
        ----------
        temp_dir : str
            Temporary directory path
        entity_type : str, optional
            Type of entity being processed (for filtering mappings)

        Returns
        -------
        str
            Path to temporary config file
        """
        temp_config_path = os.path.join(temp_dir, "rdfizer_config.ini")
        temp_mapping_path = os.path.join(temp_dir, "rml_mappings.ttl")

        # Read original config
        with open(self.config_path, encoding="utf-8") as f:
            config_content = f.read()

        # Read original mapping
        with open(self.mapping_path, encoding="utf-8") as f:
            mapping_content = f.read()

        # Update mapping sources to use temp directory
        mapping_content = mapping_content.replace(
            '"paper.json"', f'"{os.path.join(temp_dir, "paper.json")}"'
        )
        mapping_content = mapping_content.replace(
            '"authors.json"', f'"{os.path.join(temp_dir, "authors.json")}"'
        )
        mapping_content = mapping_content.replace(
            '"sections.json"', f'"{os.path.join(temp_dir, "sections.json")}"'
        )
        mapping_content = mapping_content.replace(
            '"tables.json"', f'"{os.path.join(temp_dir, "tables.json")}"'
        )
        mapping_content = mapping_content.replace(
            '"references.json"', f'"{os.path.join(temp_dir, "references.json")}"'
        )

        # Write temp mapping
        with open(temp_mapping_path, "w", encoding="utf-8") as f:
            f.write(mapping_content)

        # Update paths to use temp directory
        config_content = config_content.replace("main_directory: .", f"main_directory: {temp_dir}")
        config_content = config_content.replace(
            "output_folder: output", f"output_folder: {temp_dir}/output"
        )
        # Update mapping path to temp mapping
        config_content = config_content.replace(
            "mapping: conf/rml_mappings.ttl", f"mapping: {temp_mapping_path}"
        )

        # Write temp config
        with open(temp_config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

        return temp_config_path

    def _run_rdfizer(self, config_path: str, temp_dir: str) -> str:
        """
        Run the SDM-RDFizer with the given config.

        Parameters
        ----------
        config_path : str
            Path to config file
        temp_dir : str
            Temporary directory

        Returns
        -------
        str
            Path to output RDF file
        """
        # Run RDFizer
        semantify(config_path)

        # Find output file
        output_dir = os.path.join(temp_dir, "output")
        output_files = []

        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.endswith(".nt"):
                    output_files.append(os.path.join(output_dir, f))

        if output_files:
            return output_files[0]

        # Return empty path if no output
        return ""

    def convert_json_to_rdf(
        self,
        json_data: dict[str, Any] | list[dict[str, Any]],
        entity_type: str,
        output_format: str = "turtle",
    ) -> Graph:
        """
        Convert JSON data directly to RDF using RML mappings.

        Parameters
        ----------
        json_data : dict or list
            JSON data to convert
        entity_type : str
            Type of entities in the JSON data
        output_format : str
            Output format for RDF

        Returns
        -------
        Graph
            RDF graph containing the converted triples

        Examples
        --------
        >>> rdfizer = RMLRDFizer()
        >>> json_data = {"pmcid": "PMC123", "title": "Test"}
        >>> g = rdfizer.convert_json_to_rdf(json_data, entity_type="paper")
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write JSON data
            filename_map = {
                "paper": "paper.json",
                "author": "authors.json",
                "section": "sections.json",
                "table": "tables.json",
                "reference": "references.json",
            }

            filename = filename_map.get(entity_type, f"{entity_type}.json")
            json_path = os.path.join(temp_dir, filename)

            # Ensure correct JSON structure
            if isinstance(json_data, dict):
                # Wrap single dict in array
                json_to_write: list[dict[str, Any]] = [json_data]
            else:
                # Already a list
                json_to_write = json_data

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_to_write, f, indent=2, ensure_ascii=False)

            # Create empty JSON files for other entity types
            self._create_empty_json_files(temp_dir)

            # Create temp config
            temp_config = self._create_temp_config(temp_dir, entity_type)

            # Run RDFizer
            output_file = self._run_rdfizer(temp_config, temp_dir)

            # Load output
            g = Graph()
            if os.path.exists(output_file):
                g.parse(output_file, format="nt")

            return g
