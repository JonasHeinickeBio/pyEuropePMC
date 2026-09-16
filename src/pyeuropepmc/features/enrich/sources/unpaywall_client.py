"""
Unpaywall client for Open Access lookup.

This module provides functionality to query the Unpaywall API to check
if a DOI has an Open Access version and where to download it.
"""

import logging
from typing import Any
from urllib.parse import quote

from pyeuropepmc.core.base import BaseAPIClient
from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import APIClientError, UnpaywallError

__all__ = ["UnpaywallClient"]

logger = logging.getLogger(__name__)


class UnpaywallClient(BaseAPIClient):
    """
    Client for Unpaywall API (v2).

    Provides methods to check Open Access availability and find OA locations
    for scholarly works using their DOI.

    Parameters
    ----------
    email : str
        Email address required by Unpaywall for rate limiting and contact
    rate_limit_delay : float, optional
        Delay between requests in seconds (default: 0.6 to stay under ~100k/day)
    """

    BASE_URL: str = "https://api.unpaywall.org/v2/"

    def __init__(self, email: str, rate_limit_delay: float = 0.6) -> None:
        if not email or "@" not in email:
            raise UnpaywallError(
                ErrorCodes.VALID002,
                {"message": "Valid email address is required for Unpaywall API"},
            )
        self.email = email
        super().__init__(rate_limit_delay=rate_limit_delay)

    def lookup_by_doi(self, doi: str) -> dict[str, Any] | None:
        """
        Look up a DOI in Unpaywall database.

        Parameters
        ----------
        doi : str
            DOI of the work to look up

        Returns
        -------
        dict or None
            Unpaywall record, or None if Unpaywall does not know the DOI

        Raises
        ------
        UnpaywallError
            If the DOI is empty (``VALID003``), or the request fails for any other
            reason than a 404 (``NET001``)
        """
        if not doi:
            raise UnpaywallError(ErrorCodes.VALID003, {"message": "DOI cannot be empty"})

        # _get prepends BASE_URL, so pass the DOI relative to it. Quote what a URL
        # path cannot carry (such as "#", "?" or spaces) but keep "/" and the
        # other characters a path allows, which DOIs routinely contain.
        endpoint = quote(doi.strip(), safe="/:@!$&'()*+,;=")
        params = {"email": self.email}

        try:
            response = self._get(endpoint, params=params)
        except APIClientError as e:
            # _get has already turned HTTP and network failures into APIClientError.
            # A closed client is a usage error, not a failed lookup.
            if e.error_code == ErrorCodes.FULL007:
                raise
            status_code = e.context.get("status_code")
            if status_code == 404:
                logger.debug(f"DOI not found in Unpaywall: {doi}")
                return None
            if isinstance(status_code, int):
                message = f"HTTP error {status_code} while looking up DOI {doi}"
            else:
                message = f"Network error while looking up DOI {doi}: {e.context.get('error', e)}"
            raise UnpaywallError(ErrorCodes.NET001, {"message": message, "doi": doi}) from e

        if response is None:
            return None
        if response.status_code != 200:
            logger.warning(f"Unpaywall returned status {response.status_code} for DOI {doi}")
            return None

        data: dict[str, Any] | None = response.json()
        return data

    def get_oa_status(self, doi: str) -> str | None:
        """
        Get Open Access status for a DOI.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        str or None
            OA status: 'gold', 'green', 'hybrid', 'bronze', 'closed', or None
        """
        record = self.lookup_by_doi(doi)
        if record is None:
            return None
        return record.get("oa_status")

    def has_oa_version(self, doi: str) -> bool:
        """
        Check if a DOI has any Open Access version.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        bool
            True if OA version exists, False otherwise
        """
        record = self.lookup_by_doi(doi)
        if record is None:
            return False
        return record.get("is_oa", False) is True

    def get_best_oa_location(self, doi: str) -> dict[str, Any] | None:
        """
        Get the best Open Access location for a DOI.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        dict or None
            Best OA location info with 'url', 'url_for_pdf', 'license', etc.,
            or None if no OA location found
        """
        record = self.lookup_by_doi(doi)
        if record is None:
            return None
        return record.get("best_oa_location")

    def get_oa_locations(self, doi: str) -> list[dict[str, Any]]:
        """
        Get all Open Access locations for a DOI.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        list of dict
            List of OA locations, each with 'url', 'url_for_pdf', 'type', etc.
        """
        record = self.lookup_by_doi(doi)
        if record is None:
            return []
        oa_locations: list[dict[str, Any]] = record.get("oa_locations", [])
        if oa_locations is None:
            return []
        return oa_locations

    def get_pdf_url(self, doi: str) -> str | None:
        """
        Get PDF URL for a DOI if available.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        str or None
            PDF URL if available, None otherwise
        """
        best_location = self.get_best_oa_location(doi)
        if best_location is None:
            return None

        url_for_pdf = best_location.get("url_for_pdf")
        if isinstance(url_for_pdf, str) and url_for_pdf:
            return url_for_pdf

        url = best_location.get("url")
        if isinstance(url, str) and url and ("pdf" in url.lower() or "full" in url.lower()):
            return url

        return None

    def get_license(self, doi: str) -> str | None:
        """
        Get license information for a DOI.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        str or None
            License string (e.g., 'cc-by-4.0') or None
        """
        best_location = self.get_best_oa_location(doi)
        if best_location is None:
            return None
        return best_location.get("license")

    def get_repository(self, doi: str) -> str | None:
        """
        Get repository name if OA version is in a repository.

        Parameters
        ----------
        doi : str
            DOI of the work

        Returns
        -------
        str or None
            Repository name or None
        """
        best_location = self.get_best_oa_location(doi)
        if best_location is None:
            return None
        return best_location.get("repository_institution")
