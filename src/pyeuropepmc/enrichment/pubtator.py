"""
PubTator Central API client for biomedical entity recognition.

PubTator Central provides automated annotations of biomedical entities
such as genes, diseases, chemicals, species, and mutations in PubMed abstracts.
"""

import logging
from typing import Any
from xml.etree.ElementTree import Element  # nosec B405

from defusedxml.ElementTree import fromstring as fromstring_defused

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["PubTatorClient"]


class PubTatorClient(BaseEnrichmentClient):
    """
    Client for PubTator Central API biomedical entity recognition.

    PubTator Central provides annotations for:
    - Genes/Proteins (NCBI Gene IDs)
    - Diseases (MeSH, OMIM IDs)
    - Chemicals (MeSH IDs)
    - Species (NCBI Taxonomy IDs)
    - Mutations (variant mentions)
    - Cell lines

    The API returns data in BioC XML format with entity mentions,
    identifiers, and relations between entities.

    Examples
    --------
    >>> client = PubTatorClient()
    >>> annotations = client.enrich(pmid="12345678")
    >>> if annotations:
    ...     print(f"Found {len(annotations.get('entities', []))} entities")
    ...     for entity in annotations.get('entities', []):
    ...         print(f"{entity['type']}: {entity['text']} ({entity['id']})")
    """

    BASE_URL = "https://www.ncbi.nlm.nih.gov/research/pubtator-api/publications/export"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
    ) -> None:
        """
        Initialize PubTator Central client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper with biomedical entity annotations from PubTator Central.

        Parameters
        ----------
        identifier : str
            PubMed ID (PMID) or PMC ID (required)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Biomedical annotations with keys:
            - entities: List of annotated entities with type, text, id, offsets
            - relations: List of relations between entities
            - source: Source identifier ("pubtator")
            - pmid: PubMed ID if available
            - pmcid: PMC ID if available

        Raises
        ------
        ValueError
            If identifier is not provided
        """
        if not identifier:
            raise ValueError("Identifier (PMID or PMCID) is required for PubTator enrichment")

        logger.debug(f"Enriching biomedical entities for identifier: {identifier}")

        # PubTator API expects PMIDs, convert PMCIDs if needed
        pmid = self._normalize_identifier(identifier)

        # Make request to PubTator API
        params = {"pmids": [pmid], "format": "biocxml"}
        response = self._make_request(
            endpoint="", params=params, headers={"Accept": "application/xml"}, use_cache=use_cache
        )

        if response is None:
            logger.warning(f"No data found for identifier: {identifier}")
            return None

        # Parse BioC XML response
        try:
            annotations = self._parse_bioc_xml(response)
            if annotations:
                logger.info(
                    f"Successfully enriched biomedical entities for identifier: {identifier}"
                )
                return annotations
            else:
                logger.warning(f"No annotations found for identifier: {identifier}")
                return None

        except Exception as e:
            logger.error(f"Error parsing PubTator response for {identifier}: {e}")
            return None

    def _normalize_identifier(self, identifier: str) -> str:
        """
        Normalize identifier to PMID format expected by PubTator.

        PubTator primarily works with PMIDs. For PMCIDs, we return as-is
        since PubTator can handle both, but the API parameter expects PMIDs.

        Parameters
        ----------
        identifier : str
            PMID or PMCID

        Returns
        -------
        str
            Normalized identifier
        """
        # Remove PMC prefix if present
        if identifier.upper().startswith("PMC"):
            return identifier[3:]
        return identifier

    def _parse_bioc_xml(self, xml_content: str) -> dict[str, Any] | None:
        """
        Parse BioC XML response from PubTator Central.

        Parameters
        ----------
        xml_content : str
            Raw XML response from PubTator API

        Returns
        -------
        dict or None
            Parsed annotations or None if parsing fails
        """
        try:
            root = fromstring_defused(xml_content)

            # BioC XML structure: collection > document > passage > annotation/relation
            documents = root.findall(".//document")
            if not documents:
                return None

            all_entities = []
            all_relations = []

            for doc in documents:
                # Extract document identifiers
                doc_id = doc.find(".//id")
                pmid = doc_id.text if doc_id is not None else None

                # Extract passages (abstract, title, etc.)
                passages = doc.findall(".//passage")

                for passage in passages:
                    # Extract annotations (entities)
                    annotations = passage.findall(".//annotation")

                    for annotation in annotations:
                        entity = self._parse_annotation(annotation)
                        if entity:
                            all_entities.append(entity)

                    # Extract relations
                    relations = passage.findall(".//relation")

                    for relation in relations:
                        rel = self._parse_relation(relation)
                        if rel:
                            all_relations.append(rel)

            return {
                "source": "pubtator",
                "pmid": pmid,
                "entities": all_entities,
                "relations": all_relations,
                "entity_count": len(all_entities),
                "relation_count": len(all_relations),
            }

        except Exception as e:
            logger.error(f"XML parsing error: {e}")
            return None

    def _parse_annotation(self, annotation: Element) -> dict[str, Any] | None:
        """
        Parse a single annotation element from BioC XML.

        Parameters
        ----------
        annotation : ET.Element
            Annotation XML element

        Returns
        -------
        dict or None
            Parsed entity annotation
        """
        try:
            # Extract text and location
            text_elem = annotation.find(".//text")
            location_elem = annotation.find(".//location")

            if text_elem is None or location_elem is None:
                return None

            text = text_elem.text
            offset = int(location_elem.get("offset", 0))
            length = int(location_elem.get("length", 0))

            # Extract infon elements (metadata)
            infons = {}
            for infon in annotation.findall(".//infon"):
                key = infon.get("key")
                value = infon.text
                if key and value:
                    infons[key] = value

            # Extract entity type and identifier
            entity_type = infons.get("type", "unknown")
            identifier = infons.get("identifier", "")

            # Parse identifiers into structured format
            identifiers = self._parse_identifiers(identifier)

            return {
                "type": entity_type,
                "text": text,
                "id": identifier,  # Keep original string for backward compatibility
                "identifiers": identifiers,  # Structured identifiers
                "offset": offset,
                "length": length,
                "confidence": infons.get("confidence", ""),
                "database": infons.get("database", ""),
                "section": infons.get("section", ""),
                "normalized_text": infons.get("normalized_text", ""),
            }

        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing annotation: {e}")
            return None

    def _parse_relation(self, relation: Element) -> dict[str, Any] | None:
        """
        Parse a single relation element from BioC XML.

        Parameters
        ----------
        relation : ET.Element
            Relation XML element

        Returns
        -------
        dict or None
            Parsed relation
        """
        try:
            # Extract relation type
            infons = {}
            for infon in relation.findall(".//infon"):
                key = infon.get("key")
                value = infon.text
                if key and value:
                    infons[key] = value

            relation_type = infons.get("type", "unknown")

            # Extract node arguments (entities involved in relation)
            nodes = []
            for node in relation.findall(".//node"):
                node_id = node.get("refid")
                role = node.get("role")
                if node_id and role:
                    nodes.append({"refid": node_id, "role": role})

            return {
                "type": relation_type,
                "nodes": nodes,
            }

        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing relation: {e}")
            return None

    def _parse_identifiers(self, identifier_string: str) -> dict:
        """
        Parse identifier string into structured format.

        Parameters
        ----------
        identifier_string : str
            Raw identifier string from PubTator

        Returns
        -------
        dict
            Structured identifiers by database
        """
        identifiers = {}

        if not identifier_string:
            return identifiers

        # Split multiple identifiers (semicolon separated)
        id_parts = [part.strip() for part in identifier_string.split(";") if part.strip()]

        for part in id_parts:
            # Handle different identifier formats
            if ":" in part:
                # Format: DATABASE:ID
                db, id_value = part.split(":", 1)
                db = db.strip()
                id_value = id_value.strip()

                # Parse specific database formats
                if db.upper() in ["MESH", "MSH"]:
                    # MeSH: D012345
                    identifiers["mesh"] = id_value
                elif db.upper() in ["GENE", "NCBIGENE"]:
                    # GENE:12345 or NCBIGENE:12345
                    identifiers["ncbi_gene"] = id_value
                elif db.upper() in ["HGNC"]:
                    # HGNC:12345
                    identifiers["hgnc"] = id_value
                elif db.upper() in ["CHEBI"]:
                    # CHEBI:12345
                    identifiers["chebi"] = id_value
                elif db.upper() in ["UNIPROT"]:
                    # UNIPROT:P12345
                    identifiers["uniprot"] = id_value
                elif db.upper() in ["TAXONOMY", "NCBITAXON"]:
                    # TAXONOMY:9606 or NCBITAXON:9606
                    identifiers["ncbi_taxonomy"] = id_value
                elif db.upper() in ["OMIM"]:
                    # OMIM:123456
                    identifiers["omim"] = id_value
                elif db.upper() in ["GO"]:
                    # GO:0001234
                    identifiers["go"] = id_value
                elif db.upper() in ["PUBCHEM"]:
                    # PUBCHEM:12345
                    identifiers["pubchem"] = id_value
                elif db.upper() in ["CHEMBL"]:
                    # CHEMBL:CHEMBL123
                    identifiers["chembl"] = id_value
                else:
                    # Generic database entry
                    identifiers[db.lower()] = id_value
            else:
                # No database prefix, treat as generic ID
                identifiers["unknown"] = part

        return identifiers
