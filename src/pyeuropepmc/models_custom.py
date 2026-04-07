"""
Custom model methods for PyEuropePMC entities.

This file contains custom methods that extend the generated LinkML models.
These methods are not part of the LinkML schema and need to be added after
model generation.
"""

from typing import Any

from .models import Organization


def _add_custom_methods():
    """Add custom methods to generated model classes."""

    @classmethod
    def from_enrichment_dict(cls, inst_dict: dict[str, Any]) -> Organization:
        """
        Create an Organization from enrichment institution dictionary.

        Parameters
        ----------
        inst_dict : dict
            Institution dictionary from enrichment result

        Returns
        -------
        Organization
            Organization entity with enrichment data
        """
        # Handle relationships - extract labels from dicts
        relationships_data = inst_dict.get("relationships", [])
        if relationships_data and isinstance(relationships_data[0], dict):
            relationships_list = [r.get("label", "") for r in relationships_data]
        else:
            relationships_list = relationships_data

        # Extract individual identifiers from external_ids
        grid_id = None
        isni = None
        wikidata_id = None
        fundref_id = None

        external_ids = inst_dict.get("external_ids", [])
        if external_ids:
            for ext_id in external_ids:
                if isinstance(ext_id, dict):
                    id_type = ext_id.get("type")
                    id_value = ext_id.get("preferred") or (
                        ext_id.get("all", [None])[0] if ext_id.get("all") else None
                    )

                    if id_type == "grid" and id_value:
                        grid_id = id_value
                    elif id_type == "isni" and id_value:
                        isni = id_value
                    elif id_type == "wikidata" and id_value:
                        wikidata_id = id_value
                    elif id_type == "fundref" and id_value:
                        fundref_id = id_value

        return cls(
            display_name=inst_dict.get("display_name", ""),
            ror_id=inst_dict.get("ror_id"),
            openalex_id=inst_dict.get("openalex_id") or inst_dict.get("id"),
            country=inst_dict.get("country"),
            country_code=inst_dict.get("country_code"),
            city=inst_dict.get("city"),
            latitude=inst_dict.get("latitude"),
            longitude=inst_dict.get("longitude"),
            institution_type=inst_dict.get("type"),
            grid_id=grid_id,
            isni=isni,
            wikidata_id=wikidata_id,
            fundref_id=fundref_id,
            website=inst_dict.get("website"),
            established=inst_dict.get("established"),
            domains=inst_dict.get("domains", []),
            relationships=relationships_list,
            # Additional ROR fields
            status=inst_dict.get("status"),
            types=inst_dict.get("types", []),
            names=inst_dict.get("names", []),
            locations=inst_dict.get("locations", []),
            links=inst_dict.get("links", []),
        )

    # Add the method to the Organization class
    Organization.from_enrichment_dict = from_enrichment_dict


# Apply the custom methods when this module is imported
_add_custom_methods()
