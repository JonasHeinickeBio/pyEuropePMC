"""
Grant entity model for representing funding information.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyeuropepmc.models.base import BaseEntity

if TYPE_CHECKING:
    from pyeuropepmc.models.author import AuthorEntity

__all__ = ["GrantEntity"]


@dataclass
class GrantEntity(BaseEntity):
    """
    Entity representing a research grant or funding award.

    Attributes
    ----------
    fundref_doi : Optional[str]
        FundRef DOI for the funding organization
    funding_source : Optional[str]
        Name of the funding organization/source
    award_id : Optional[str]
        Grant or award identifier
    recipients : Optional[list[AuthorEntity]]
        List of principal investigators/recipients who receive this grant.
        These are the researchers receiving the funding, not giving it out.
    recipient : Optional[str]
        DEPRECATED: Use recipients instead. Kept for backward compatibility.
    """

    fundref_doi: str | None = None
    funding_source: str | None = None
    award_id: str | None = None
    recipients: list["AuthorEntity"] | None = None
    recipient: str | None = None  # Deprecated, kept for backward compatibility

    def __post_init__(self) -> None:
        """Initialize types and label after dataclass initialization."""
        if not self.types:
            self.types = ["frapo:Grant"]
        if not self.label:
            self.label = self.award_id or self.funding_source or "Grant"

    def normalize(self) -> None:
        """Normalize grant data."""
        # Normalize DOI if present
        if self.fundref_doi:
            self.fundref_doi = self.fundref_doi.strip()

        # Normalize funding source
        if self.funding_source:
            self.funding_source = self.funding_source.strip()

        # Normalize award ID
        if self.award_id:
            self.award_id = self.award_id.strip()

        # Normalize recipient (deprecated field)
        if self.recipient:
            self.recipient = self.recipient.strip()

        # Normalize recipient entities
        if self.recipients:
            for recipient in self.recipients:
                recipient.normalize()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fundref_doi": self.fundref_doi,
            "funding_source": self.funding_source,
            "award_id": self.award_id,
            "recipients": [r.to_dict() for r in self.recipients] if self.recipients else None,
            "recipient": self.recipient,  # Deprecated but included for compatibility
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrantEntity":
        """Create from dictionary."""
        from pyeuropepmc.models.author import AuthorEntity

        # Handle recipients
        recipients = None
        if data.get("recipients"):
            recipients = [
                AuthorEntity(**r) if isinstance(r, dict) else r for r in data["recipients"]
            ]

        return cls(
            fundref_doi=data.get("fundref_doi"),
            funding_source=data.get("funding_source"),
            award_id=data.get("award_id"),
            recipients=recipients,
            recipient=data.get("recipient"),
        )
