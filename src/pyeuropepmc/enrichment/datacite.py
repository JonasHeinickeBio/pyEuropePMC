"""
DataCite API client for enriching paper and dataset metadata.

DataCite provides metadata for datasets, software, and other research outputs,
including DOIs, alternate identifiers, and versioning information.
"""

import logging
from typing import Any, cast

from pyeuropepmc.cache.cache import CacheConfig
from pyeuropepmc.enrichment.base import BaseEnrichmentClient

logger = logging.getLogger(__name__)

__all__ = ["DataCiteClient"]


class DataCiteClient(BaseEnrichmentClient):
    """
    Client for DataCite API enrichment.

    DataCite provides comprehensive metadata for:
    - Datasets and data publications
    - Software and code repositories
    - Research papers and publications
    - Alternate identifiers and versioning
    - Publisher and repository information
    - Usage statistics (views, downloads, citations)
    - Relationships to other works (citations, references, versions)
    - Geographic and funding information

    The client extracts both basic metadata and advanced usage statistics,
    relationships, and temporal information from the DataCite REST API.

    Examples
    --------
    >>> client = DataCiteClient()
    >>> metadata = client.enrich(doi="10.5061/dryad.8515")
    >>> if metadata:
    ...     print(metadata.get("title"))
    ...     print(f"Citations: {metadata.get('citation_count', 0)}")
    ...     print(f"Downloads: {metadata.get('download_count', 0)}")
    """

    BASE_URL = "https://api.datacite.org/dois"

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 15,
        cache_config: CacheConfig | None = None,
        email: str | None = None,
    ) -> None:
        """
        Initialize DataCite client.

        Parameters
        ----------
        rate_limit_delay : float, optional
            Delay between requests in seconds (default: 1.0)
        timeout : int, optional
            Request timeout in seconds (default: 15)
        cache_config : CacheConfig, optional
            Cache configuration
        email : str, optional
            Email for contact (optional)
        """
        super().__init__(
            base_url=self.BASE_URL,
            rate_limit_delay=rate_limit_delay,
            timeout=timeout,
            cache_config=cache_config,
        )
        self.email = email

        # Add email to user agent if provided
        if email:
            user_agent = (
                f"pyeuropepmc/1.12.0 "
                f"(https://github.com/JonasHeinickeBio/pyEuropePMC; "
                f"mailto:{email})"
            )
            self.session.headers.update({"User-Agent": user_agent})
            logger.info(f"DataCite client initialized with email: {email}")

    def enrich(
        self, identifier: str | None = None, use_cache: bool = True, **kwargs: Any
    ) -> dict[str, Any] | None:
        """
        Enrich paper/dataset metadata using DataCite API.

        Parameters
        ----------
        identifier : str
            DOI to enrich (required)
        use_cache : bool, optional
            Whether to use cached results (default: True)
        **kwargs
            Additional parameters (unused)

        Returns
        -------
        dict or None
            Enriched metadata with comprehensive DataCite information including:
            - doi: DOI identifier
            - title: Publication title
            - creators: List of creators/authors with ORCID and affiliations
            - contributors: List of contributors with roles and affiliations
            - publisher: Publisher name
            - publication_year: Year published
            - resource_type: Specific type of resource
            - resource_type_general: General resource category
            - descriptions: Abstracts and descriptions
            - subjects: Subject categories and classifications
            - dates: Publication and other relevant dates
            - related_identifiers: Related DOIs and resources
            - sizes: File sizes
            - formats: File formats
            - version: Version information
            - rights_list: Usage rights and licenses
            - language: Publication language
            - url: Landing page URL
            - state: DOI state (findable, registered, draft)
            - citation_count: Number of citations
            - view_count: Number of views
            - download_count: Number of downloads
            - relationships: Related works (citations, references, versions)
            - xml: Base64-encoded DataCite XML metadata
            - And many more fields...

        Raises
        ------
        ValueError
            If identifier is not provided
        """
        if not identifier:
            raise ValueError("Identifier is required for DataCite enrichment")

        logger.debug(f"Enriching metadata for identifier: {identifier}")

        # Make request to DataCite API
        response = self._make_request(endpoint=identifier, use_cache=use_cache)
        if response is None:
            logger.warning(f"No data found for identifier: {identifier}")
            return None

        # Extract metadata from response
        try:
            data = response.get("data", {})
            if not data:
                logger.warning(f"Empty response from DataCite for identifier: {identifier}")
                return None

            # Parse and normalize metadata
            enriched = self._parse_datacite_response(data)
            logger.info(f"Successfully enriched metadata for identifier: {identifier}")
            return enriched

        except Exception as e:
            logger.error(f"Error parsing DataCite response for {identifier}: {e}")
            return None

    def _parse_datacite_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse DataCite API response into normalized metadata.

        Parameters
        ----------
        data : dict
            DataCite API data object

        Returns
        -------
        dict
            Normalized metadata
        """
        attributes = data.get("attributes", {})
        relationships = data.get("relationships", {})

        return {
            "source": "datacite",
            "doi": data.get("id"),
            "prefix": attributes.get("prefix"),
            "suffix": attributes.get("suffix"),
            "identifiers": attributes.get("identifiers", []),
            "alternate_identifiers": attributes.get("alternateIdentifiers", []),
            "title": self._extract_title(attributes),
            "creators": self._extract_creators(attributes),
            "contributors": self._extract_contributors(attributes),
            "publisher": attributes.get("publisher"),
            "container": attributes.get("container", {}),
            "publication_year": attributes.get("publicationYear"),
            "subjects": self._extract_subjects(attributes),
            "dates": self._extract_dates(attributes),
            "language": attributes.get("language"),
            "types": attributes.get("types", {}),
            "resource_type": attributes.get("types", {}).get("resourceType"),
            "resource_type_general": attributes.get("types", {}).get("resourceTypeGeneral"),
            "sizes": attributes.get("sizes", []),
            "formats": attributes.get("formats", []),
            "version": attributes.get("version"),
            "rights_list": attributes.get("rightsList", []),
            "descriptions": self._extract_descriptions(attributes),
            "geo_locations": attributes.get("geoLocations", []),
            "funding_references": attributes.get("fundingReferences", []),
            "related_identifiers": self._extract_related_identifiers(attributes),
            "related_items": attributes.get("relatedItems", []),
            # Usage statistics
            "view_count": attributes.get("viewCount", 0),
            "download_count": attributes.get("downloadCount", 0),
            "reference_count": attributes.get("referenceCount", 0),
            "citation_count": attributes.get("citationCount", 0),
            "part_count": attributes.get("partCount", 0),
            "part_of_count": attributes.get("partOfCount", 0),
            "version_count": attributes.get("versionCount", 0),
            "version_of_count": attributes.get("versionOfCount", 0),
            # Temporal information
            "created": attributes.get("created"),
            "registered": attributes.get("registered"),
            "published": attributes.get("published"),
            "updated": attributes.get("updated"),
            # Status information
            "state": attributes.get("state"),
            "is_active": attributes.get("isActive"),
            "reason": attributes.get("reason"),
            # URLs
            "url": attributes.get("url"),
            "content_url": attributes.get("contentUrl"),
            # Metadata information
            "metadata_version": attributes.get("metadataVersion"),
            "schema_version": attributes.get("schemaVersion"),
            "source_system": attributes.get("source"),
            # XML metadata (base64 encoded)
            "xml": attributes.get("xml"),
            # Relationships
            "relationships": self._extract_relationships(relationships),
            # Usage over time
            "views_over_time": attributes.get("viewsOverTime", []),
            "downloads_over_time": attributes.get("downloadsOverTime", []),
            "citations_over_time": attributes.get("citationsOverTime", []),
        }

    def _extract_title(self, attributes: dict[str, Any]) -> str | None:
        """Extract title from attributes."""
        titles = attributes.get("titles", [])
        if titles and isinstance(titles, list):
            for t in titles:
                if isinstance(t, dict) and t.get("title"):
                    title = t["title"]
                    return str(title) if title is not None else None
        return None

    def _extract_creators(self, attributes: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract creators/authors from attributes."""
        creators = []
        for creator in attributes.get("creators", []):
            if isinstance(creator, dict):
                name = creator.get("name", "")
                given_name = creator.get("givenName", "")
                family_name = creator.get("familyName", "")
                if given_name and family_name:
                    name = f"{given_name} {family_name}"
                if name:
                    creators.append(
                        {
                            "name": name,
                            "given_name": given_name,
                            "family_name": family_name,
                            "orcid": (
                                creator.get("nameIdentifiers", [{}])[0].get("nameIdentifier")
                                if creator.get("nameIdentifiers")
                                else None
                            ),
                            "affiliation": creator.get("affiliation", []),
                        }
                    )
        return creators if creators else None

    def _extract_descriptions(self, attributes: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract descriptions from attributes."""
        descriptions = []
        for desc in attributes.get("descriptions", []):
            if isinstance(desc, dict) and desc.get("description"):
                descriptions.append(
                    {
                        "description": desc["description"],
                        "type": desc.get("descriptionType", "Abstract"),
                    }
                )
        return descriptions if descriptions else None

    def _extract_subjects(self, attributes: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract subjects from attributes."""
        subjects = []
        for subject in attributes.get("subjects", []):
            if isinstance(subject, dict) and subject.get("subject"):
                subjects.append(
                    {
                        "subject": subject["subject"],
                        "scheme": subject.get("subjectScheme"),
                        "scheme_uri": subject.get("schemeUri"),
                    }
                )
        return subjects if subjects else None

    def _extract_dates(self, attributes: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract dates from attributes."""
        dates = []
        for date_info in attributes.get("dates", []):
            if isinstance(date_info, dict):
                dates.append(
                    {"date": date_info.get("date"), "date_type": date_info.get("dateType")}
                )
        return dates if dates else None

    def _extract_contributors(self, attributes: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract contributors from attributes."""
        contributors = []
        for contributor in attributes.get("contributors", []):
            if isinstance(contributor, dict):
                name = contributor.get("name", "")
                given_name = contributor.get("givenName", "")
                family_name = contributor.get("familyName", "")
                if given_name and family_name:
                    name = f"{given_name} {family_name}"
                if name:
                    contributors.append(
                        {
                            "name": name,
                            "given_name": given_name,
                            "family_name": family_name,
                            "contributor_type": contributor.get("contributorType"),
                            "orcid": (
                                contributor.get("nameIdentifiers", [{}])[0].get("nameIdentifier")
                                if contributor.get("nameIdentifiers")
                                else None
                            ),
                            "affiliation": contributor.get("affiliation", []),
                        }
                    )
        return contributors if contributors else None

    def _extract_related_identifiers(
        self, attributes: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Extract related identifiers from attributes."""
        related_identifiers = []
        for rel_id in attributes.get("relatedIdentifiers", []):
            if isinstance(rel_id, dict):
                related_identifiers.append(
                    {
                        "identifier": rel_id.get("relatedIdentifier"),
                        "identifier_type": rel_id.get("relatedIdentifierType"),
                        "relation_type": rel_id.get("relationType"),
                        "resource_type_general": rel_id.get("resourceTypeGeneral"),
                    }
                )
        return related_identifiers if related_identifiers else None

    def _extract_relationships(self, relationships: dict[str, Any]) -> dict[str, Any]:
        """Extract relationships from the relationships object."""
        extracted = {}

        # Extract client and provider information
        if "client" in relationships:
            client_data = relationships["client"].get("data", {})
            if client_data:
                extracted["client"] = {
                    "id": client_data.get("id"),
                    "type": client_data.get("type"),
                }

        if "provider" in relationships:
            provider_data = relationships["provider"].get("data", {})
            if provider_data:
                extracted["provider"] = {
                    "id": provider_data.get("id"),
                    "type": provider_data.get("type"),
                }

        # Extract various relationship lists
        relationship_types = [
            "media",
            "references",
            "citations",
            "parts",
            "partOf",
            "versions",
            "versionOf",
        ]

        for rel_type in relationship_types:
            if rel_type in relationships:
                data_list = relationships[rel_type].get("data", [])
                if data_list:
                    extracted[rel_type.lower()] = [  # type: ignore[assignment]
                        cast(dict[str, Any], {"id": item.get("id"), "type": item.get("type")})
                        for item in data_list
                        if isinstance(item, dict)
                    ]

        return extracted
