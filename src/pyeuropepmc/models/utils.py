"""Utility functions for data model operations."""


def normalize_doi(doi: str | None) -> str | None:
    """
    Normalize a DOI by lowercasing and removing URL prefixes.

    Parameters
    ----------
    doi : str or None
        The DOI to normalize

    Returns
    -------
    str or None
        Normalized DOI, or None if input was None

    Examples
    --------
    >>> normalize_doi("10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("https://doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi("http://dx.doi.org/10.1234/TEST")
    '10.1234/test'
    >>> normalize_doi(None)
    """
    if not doi:
        return None

    return (
        doi.lower()
        .replace("https://doi.org/", "")
        .replace("http://dx.doi.org/", "")
        .replace("http://doi.org/", "")
        .strip()
    )
