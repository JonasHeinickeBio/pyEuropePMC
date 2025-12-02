"""
MeSH (Medical Subject Headings) data models for structured term representation.

This module provides dataclass models for representing MeSH terms with their
qualifiers, major topic indicators, and other metadata from Europe PMC.
"""

from dataclasses import dataclass, field

__all__ = ["MeSHQualifierEntity", "MeSHHeadingEntity"]


@dataclass
class MeSHQualifierEntity:
    """
    Represents a MeSH qualifier (subheading) that refines a descriptor.

    MeSH qualifiers provide specificity to main descriptors, indicating
    specific aspects like diagnosis, therapy, psychology, etc.

    Attributes
    ----------
    qualifier_name : str
        Full name of the qualifier (e.g., "diagnosis", "therapy")
    abbreviation : str | None
        Standard MeSH abbreviation (e.g., "DI", "TH")
    major_topic : bool
        Whether this qualifier is a major focus of the article

    Examples
    --------
    >>> qualifier = MeSHQualifierEntity(
    ...     qualifier_name="therapy",
    ...     abbreviation="TH",
    ...     major_topic=False
    ... )
    """

    qualifier_name: str
    abbreviation: str | None = None
    major_topic: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "MeSHQualifierEntity":
        """
        Create MeSHQualifierEntity from Europe PMC API response dict.

        Parameters
        ----------
        data : dict
            Raw qualifier data with keys: qualifierName, abbreviation, majorTopic_YN

        Returns
        -------
        MeSHQualifierEntity
            Parsed qualifier entity

        Examples
        --------
        >>> data = {
        ...     "qualifierName": "therapy",
        ...     "abbreviation": "TH",
        ...     "majorTopic_YN": "N"
        ... }
        >>> qualifier = MeSHQualifierEntity.from_dict(data)
        """
        return cls(
            qualifier_name=data.get("qualifierName", ""),
            abbreviation=data.get("abbreviation"),
            major_topic=data.get("majorTopic_YN") == "Y",
        )


@dataclass
class MeSHHeadingEntity:
    """
    Represents a complete MeSH heading including descriptor and qualifiers.

    A MeSH heading consists of a main descriptor (subject) and optional
    qualifiers that refine its meaning. Major topics indicate the primary
    focus of the article.

    Attributes
    ----------
    descriptor_name : str
        Main MeSH descriptor term (e.g., "Neoplasms", "Humans")
    major_topic : bool
        Whether this is a major topic of the article
    qualifiers : list[MeSHQualifierEntity]
        List of qualifiers refining this descriptor
    descriptor_ui : str | None
        Unique MeSH identifier (UI) if available

    Examples
    --------
    >>> heading = MeSHHeadingEntity(
    ...     descriptor_name="Neoplasms",
    ...     major_topic=True,
    ...     qualifiers=[
    ...         MeSHQualifierEntity("diagnosis", "DI", False),
    ...         MeSHQualifierEntity("therapy", "TH", False)
    ...     ]
    ... )
    """

    descriptor_name: str
    major_topic: bool = False
    qualifiers: list[MeSHQualifierEntity] = field(default_factory=list)
    descriptor_ui: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "MeSHHeadingEntity":
        """
        Create MeSHHeadingEntity from Europe PMC API response dict.

        Parameters
        ----------
        data : dict
            Raw MeSH heading data with keys: descriptorName, majorTopic_YN,
            meshQualifierList, etc.

        Returns
        -------
        MeSHHeadingEntity
            Parsed heading entity with qualifiers

        Examples
        --------
        >>> data = {
        ...     "descriptorName": "Neoplasms",
        ...     "majorTopic_YN": "Y",
        ...     "meshQualifierList": {
        ...         "meshQualifier": [
        ...             {"qualifierName": "therapy", "abbreviation": "TH", "majorTopic_YN": "N"}
        ...         ]
        ...     }
        ... }
        >>> heading = MeSHHeadingEntity.from_dict(data)
        """
        # Parse qualifiers if present
        qualifiers = []
        qualifier_list_data = data.get("meshQualifierList", {})
        qualifier_array = qualifier_list_data.get("meshQualifier", [])

        for qualifier_data in qualifier_array:
            qualifiers.append(MeSHQualifierEntity.from_dict(qualifier_data))

        return cls(
            descriptor_name=data.get("descriptorName", ""),
            major_topic=data.get("majorTopic_YN") == "Y",
            qualifiers=qualifiers,
            descriptor_ui=data.get("descriptorUI"),
        )

    def get_full_term(self) -> str:
        """
        Get the full MeSH term including qualifiers.

        Returns
        -------
        str
            Descriptor with qualifiers (e.g., "Neoplasms/therapy/diagnosis")

        Examples
        --------
        >>> heading = MeSHHeadingEntity(
        ...     descriptor_name="Neoplasms",
        ...     qualifiers=[MeSHQualifierEntity("therapy", "TH", False)]
        ... )
        >>> heading.get_full_term()
        'Neoplasms/therapy'
        """
        if not self.qualifiers:
            return self.descriptor_name

        qualifier_names = [q.qualifier_name for q in self.qualifiers]
        return f"{self.descriptor_name}/{'/'.join(qualifier_names)}"

    def to_dict(self) -> dict:
        """
        Convert to dictionary representation.

        Returns
        -------
        dict
            Dictionary with descriptor, major_topic, and qualifiers
        """
        return {
            "descriptor_name": self.descriptor_name,
            "major_topic": self.major_topic,
            "qualifiers": [
                {
                    "qualifier_name": q.qualifier_name,
                    "abbreviation": q.abbreviation,
                    "major_topic": q.major_topic,
                }
                for q in self.qualifiers
            ],
            "descriptor_ui": self.descriptor_ui,
        }
