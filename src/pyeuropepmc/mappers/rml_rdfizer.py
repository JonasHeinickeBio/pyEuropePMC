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

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from typing import TYPE_CHECKING, Any

from pyeuropepmc.conf import config_file

if TYPE_CHECKING:
    from rdflib import Graph

try:
    from rdfizer import semantify

    RDFIZER_AVAILABLE = True
except ImportError:
    RDFIZER_AVAILABLE = False

__all__ = ["RMLRDFizer", "RDFIZER_AVAILABLE"]

#: JSON file each ``entity_type`` is written to. The names are the
#: ``rml:source`` values that examples/scripts/sync_rdf_mappings.py generates.
_SOURCE_FILES = {
    "paper": "paper.json",
    "author": "authors.json",
    "section": "sections.json",
    "table": "tables.json",
    "tablerow": "table_rows.json",
    "figure": "figures.json",
    "reference": "references.json",
    "journal": "journal.json",
    "grant": "grant.json",
    "institution": "institutions.json",
    "scholarlywork": "scholarlywork.json",
    "annotation": "annotation.json",
}

#: A relative JSON source in an RML mapping: ``rml:source "authors.json"``.
_RML_JSON_SOURCE = re.compile(r'(rml:source\s+)"([^"/\\]+\.json)"')

#: Record fields that are identifiers in their own right, in order of preference.
_NATURAL_ID_FIELDS = ("doi", "pmcid", "pmid", "orcid", "ror_id")

#: Fields left out of the content digest: they change from run to run.
_VOLATILE_FIELDS = frozenset({"id", "last_updated"})


def _content_digest(record: Any) -> str:
    """Stable digest of a record's content, ignoring volatile fields."""

    def strip(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in obj.items() if k not in _VOLATILE_FIELDS}
        if isinstance(obj, list):
            return [strip(item) for item in obj]
        return obj

    canonical = json.dumps(strip(record), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _assign_missing_ids(records: list[dict[str, Any]], entity_type: str) -> None:
    """Give each record without an ``id`` one, for the ``.../{id}`` subject templates.

    Without an ``id`` the RML subject template cannot be filled and the record
    produces no triples. An identifier of the entity itself is used where there
    is one (DOI, PMCID, ``pmid:<PMID>``, ORCID, ROR ID), so records for the same
    work or person share a subject. Otherwise the id is a digest of the record's
    content, ``<entity_type>-<16 hex digits>``: the same in every run (Python's
    ``hash()`` of a string is salted per process), and a second record with
    identical content gets a ``-2`` suffix instead of silently sharing a subject.
    """
    seen: dict[str, int] = {}
    for record in records:
        if record.get("id") is not None:
            continue
        natural = next((f for f in _NATURAL_ID_FIELDS if record.get(f)), None)
        if natural is not None:
            value = record[natural]
            record["id"] = f"pmid:{value}" if natural == "pmid" else str(value)
            continue
        ident = f"{entity_type}-{_content_digest(record)}"
        seen[ident] = seen.get(ident, 0) + 1
        record["id"] = ident if seen[ident] == 1 else f"{ident}-{seen[ident]}"


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

        # Default to the rdfizer_config.ini and rml_mappings.ttl that ship with
        # the package.
        if config_path is None:
            config_path = str(config_file("rdfizer_config.ini"))

        if mapping_path is None:
            mapping_path = str(config_file("rml_mappings.ttl"))

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
        from rdflib import Graph

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

            # Bind namespaces to ensure proper prefixes in serialization
            self._bind_namespaces(g)

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
        filename = _SOURCE_FILES.get(entity_type, f"{entity_type}.json")
        json_path = os.path.join(output_dir, filename)

        # Always use array format for consistency
        data = [e.to_dict() for e in entities]

        # Every subject template uses {id}: a record without one yields no triples.
        _assign_missing_ids(data, entity_type)

        # Filter out None values and convert to strings to avoid invalid RDF
        def filter_none(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: filter_none(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [filter_none(item) for item in obj]
            else:
                # Convert all values to strings for RML processing
                return str(obj)

        data = filter_none(data)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return json_path

    def _mapping_sources(self) -> list[str]:
        """The relative JSON source files the RML mapping reads."""
        with open(self.mapping_path, encoding="utf-8") as f:
            return sorted({m.group(2) for m in _RML_JSON_SOURCE.finditer(f.read())})

    def _create_empty_json_files(self, temp_dir: str) -> None:
        """
        Create empty JSON files for all entity types to avoid RDFizer errors.

        Covers every source the mapping names, so a triples map added to the
        mapping (for example by regenerating it from rdf_map.yml) has an input.

        Parameters
        ----------
        temp_dir : str
            Temporary directory path
        """
        filenames = set(_SOURCE_FILES.values()) | set(self._mapping_sources())

        for filename in sorted(filenames):
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

        # Point every relative JSON source of the mapping at the temp directory
        mapping_content = _RML_JSON_SOURCE.sub(
            lambda m: f'{m.group(1)}"{os.path.join(temp_dir, m.group(2))}"', mapping_content
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

    def _bind_namespaces(self, g: Graph) -> None:
        """
        Bind namespaces to the RDF graph for proper prefixing.

        Parameters
        ----------
        g : Graph
            RDF graph to bind namespaces to
        """
        # Define the same namespaces as in the RML mappings
        namespaces = {
            "ex": "http://example.org/",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "bibo": "http://purl.org/ontology/bibo/",
            "prov": "http://www.w3.org/ns/prov#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "nif": "http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "mesh": "http://id.nlm.nih.gov/mesh/",
            "obo": "http://purl.obolibrary.org/obo/",
            "org": "http://www.w3.org/ns/org#",
            "cito": "http://purl.org/spar/cito/",
            "datacite": "http://purl.org/spar/datacite/",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            "ror": "https://ror.org/vocab#",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "data": "http://example.org/data/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        }

        for prefix, uri in namespaces.items():
            g.bind(prefix, uri)

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

        # No output produced
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
            filename = _SOURCE_FILES.get(entity_type, f"{entity_type}.json")
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

            # Load output into RDF graph *before* the temporary directory
            # (and the output file inside it) is removed on exiting this
            # `with` block.
            from rdflib import Graph

            g = Graph()
            if output_file and os.path.exists(output_file):
                g.parse(output_file, format="nt")

        # Bind namespaces to ensure proper prefixes in serialization
        self._bind_namespaces(g)

        return g
