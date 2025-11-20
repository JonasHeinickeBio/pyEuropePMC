"""
Institution entity model for representing organizational affiliations.
"""

from dataclasses import dataclass, field
from typing import Any

from pyeuropepmc.models.base import BaseEntity

__all__ = ["InstitutionEntity"]


@dataclass
class InstitutionEntity(BaseEntity):
    """
    Entity representing an institution with ROR alignment.

    Attributes
    ----------
    display_name : str
        Display name of the institution
    ror_id : Optional[str]
        ROR (Research Organization Registry) identifier
    openalex_id : Optional[str]
        OpenAlex institution ID
    country : Optional[str]
        Country name
    country_code : Optional[str]
        ISO country code
    city : Optional[str]
        City name
    latitude : Optional[float]
        Geographic latitude
    longitude : Optional[float]
        Geographic longitude
    institution_type : Optional[str]
        Type of institution (e.g., education, healthcare)
    grid_id : Optional[str]
        GRID identifier
    isni : Optional[str]
        ISNI identifier
    wikidata_id : Optional[str]
        Wikidata identifier
    fundref_id : Optional[str]
        FundRef identifier
    website : Optional[str]
        Institution website URL
    established : Optional[int]
        Year established
    relationships : Optional[list[dict]]
        Related institutions
    domains : Optional[list[str]]
        Associated domain names

    Examples
    --------
    >>> institution = InstitutionEntity(
    ...     display_name="University of Example",
    ...     ror_id="https://ror.org/abc123",
    ...     country="United States"
    ... )
    >>> institution.validate()
    """

    display_name: str = ""
    ror_id: str | None = None
    openalex_id: str | None = None
    country: str | None = None
    country_code: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    institution_type: str | None = None
    grid_id: str | None = None
    isni: str | None = None
    wikidata_id: str | None = None
    fundref_id: str | None = None
    website: str | None = None
    established: int | None = None
    relationships: list[dict[str, Any]] | None = None
    domains: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["org:Organization"]
        if not self.label:
            self.label = self.display_name or ""

    def validate(self) -> None:
        """
        Validate institution data.

        Raises
        ------
        ValueError
            If display_name is not provided or empty
        """
        if not self.display_name or not self.display_name.strip():
            raise ValueError("InstitutionEntity must have a display_name")

    def normalize(self) -> None:
        """Normalize institution data (trim whitespace)."""
        if self.display_name:
            self.display_name = self.display_name.strip()
        if self.ror_id:
            self.ror_id = self.ror_id.strip()
        if self.openalex_id:
            self.openalex_id = self.openalex_id.strip()
        if self.country:
            self.country = self.country.strip()
        if self.country_code:
            self.country_code = self.country_code.strip()
        if self.city:
            self.city = self.city.strip()
        if self.website:
            self.website = self.website.strip()

    @classmethod
    def from_enrichment_dict(cls, inst_dict: dict[str, Any]) -> "InstitutionEntity":
        """
        Create an InstitutionEntity from enrichment institution dictionary.

        Parameters
        ----------
        inst_dict : dict
            Institution dictionary from enrichment result (OpenAlex format)

        Returns
        -------
        InstitutionEntity
            Institution entity with enrichment data
        """
        # Extract external IDs
        external_ids = inst_dict.get("external_ids", [])
        grid_id = None
        isni = None
        wikidata_id = None
        fundref_id = None

        if isinstance(external_ids, list):
            for ext_id in external_ids:
                if isinstance(ext_id, dict):
                    ext_type = ext_id.get("type")
                    preferred = ext_id.get("preferred")
                    all_ids = ext_id.get("all", [])
                    if ext_type == "grid" and preferred:
                        grid_id = preferred
                    elif ext_type == "isni" and all_ids:
                        isni = all_ids[0] if all_ids else None
                    elif ext_type == "wikidata" and all_ids:
                        wikidata_id = all_ids[0] if all_ids else None
                    elif ext_type == "fundref" and all_ids:
                        fundref_id = all_ids[0] if all_ids else None

        # Get institution type (first from types list if available)
        types = inst_dict.get("types", [])
        institution_type = types[0] if types else inst_dict.get("type")

        return cls(
            display_name=inst_dict.get("display_name", ""),
            ror_id=inst_dict.get("ror_id"),
            openalex_id=inst_dict.get("id"),
            country=inst_dict.get("country"),
            country_code=inst_dict.get("country_code"),
            city=inst_dict.get("city"),
            latitude=inst_dict.get("latitude"),
            longitude=inst_dict.get("longitude"),
            institution_type=institution_type,
            grid_id=grid_id,
            isni=isni,
            wikidata_id=wikidata_id,
            fundref_id=fundref_id,
            website=inst_dict.get("website"),
            established=inst_dict.get("established"),
            relationships=inst_dict.get("relationships"),
            domains=inst_dict.get("domains", []),
        )
