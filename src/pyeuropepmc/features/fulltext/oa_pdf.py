"""PDFs of papers that are not in PubMed Central, from the open copies others know of.

Given a DOI, arXiv's own PDF, Unpaywall, OpenAlex and Semantic Scholar are asked, in that
order, for a link to an open copy; the first link that serves a real PDF wins.

The links come from third-party records, so nothing is fetched blindly: a link must be
http(s) to a public address (no ``localhost``, private ranges or cloud metadata
addresses), every redirect is checked the same way before it is followed, and the body must
be a PDF under the caller's size limit. Pages that answer with a browser check or a login
are not worked around; they count as "no copy here".
"""

from __future__ import annotations

from collections.abc import Callable
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import Any, NamedTuple
from urllib.parse import quote, urljoin, urlparse

import requests

from pyeuropepmc._useragent import get_user_agent
from pyeuropepmc.features.fulltext.pdf_result import PdfResult, normalize_license
from pyeuropepmc.utils.helpers import DownloadTooLarge, atomic_write, copy_capped

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
# (connect, read) seconds. Connecting is short because a host with an address that does not
# answer (an unreachable IPv6 one, say) is retried on each address before the next is tried.
API_TIMEOUT = (5, 20)
FETCH_TIMEOUT = (8, 60)
MIN_PDF_BYTES = 1024
_REDIRECT_STATUS = (301, 302, 303, 307, 308)
_ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)", re.IGNORECASE)
#: Source names, in the order they are asked.
SOURCES = ("arxiv", "unpaywall", "openalex", "semantic_scholar")


class Link(NamedTuple):
    """A candidate PDF URL and the licence the service that named it reported (if any)."""

    url: str
    license: str | None = None


def is_public_url(url: str) -> bool:
    """Whether ``url`` is http(s) with no credentials and only public addresses behind it.

    The host is resolved and every address must be globally routable, which rules out
    loopback, private and link-local ranges (cloud metadata services live there). A name
    that does not resolve is refused. The address can still change between this check and
    the connection, so this narrows the risk rather than removing it.
    """
    try:
        parts = urlparse(url)
        host = parts.hostname
        if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
            return False
        port = parts.port or (443 if parts.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        return False
    if not infos:
        return False
    for info in infos:
        address = ipaddress.ip_address(str(info[4][0]).split("%")[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            return False
    return True


def fetch_pdf(url: str, output_path: Path, max_bytes: int | None = None) -> bool:
    """Save the PDF behind ``url`` at ``output_path``; ``False`` and no file if it is not one.

    Redirects are followed by hand, at most ``MAX_REDIRECTS``, each target checked with
    :func:`is_public_url`. A page of type HTML, a status other than 200, a body over
    ``max_bytes`` (declared or counted while reading) or one that does not start with
    ``%PDF`` all mean "no".
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_url(current):
            logger.debug(f"Refusing a non-public or malformed link: {current}")
            return False
        response = requests.get(
            current,
            stream=True,
            timeout=FETCH_TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": get_user_agent(), "Accept": "application/pdf,*/*;q=0.5"},
        )
        try:
            if response.status_code in _REDIRECT_STATUS:
                target = response.headers.get("location")
                if not target:
                    return False
                current = urljoin(current, target)
                continue
            return _save_if_pdf(response, output_path, max_bytes)
        finally:
            response.close()
    logger.debug(f"Too many redirects from {url}")
    return False


def _save_if_pdf(response: Any, output_path: Path, max_bytes: int | None) -> bool:
    if response.status_code != 200:
        return False
    if "html" in str(response.headers.get("content-type", "")).lower():
        return False  # a landing page, paywall or browser check, not the file
    declared = str(response.headers.get("content-length", ""))
    if max_bytes is not None and declared.isdigit() and int(declared) > max_bytes:
        return False
    try:
        with atomic_write(output_path, "wb") as sink:
            copy_capped(response.iter_content(chunk_size=65536), sink, max_bytes)
    except DownloadTooLarge:
        return False
    try:
        with output_path.open("rb") as handle:
            looks_like_pdf = handle.read(4) == b"%PDF"
        if looks_like_pdf and output_path.stat().st_size >= MIN_PDF_BYTES:
            return True
    except OSError:
        pass
    output_path.unlink(missing_ok=True)
    return False


def _json(url: str, **params: Any) -> Any:
    response = requests.get(
        url, params=params, timeout=API_TIMEOUT, headers={"User-Agent": get_user_agent()}
    )
    return response.json() if response.status_code == 200 else None


def _arxiv_links(doi: str, email: str | None) -> list[Link]:
    match = _ARXIV_DOI.fullmatch(doi)
    return [Link(f"https://arxiv.org/pdf/{match.group(1)}")] if match else []


def _unpaywall_links(doi: str, email: str | None) -> list[Link]:
    if not email:
        return []
    from pyeuropepmc.features.enrich.sources.unpaywall_client import UnpaywallClient

    record = UnpaywallClient(email=email, rate_limit_delay=0.6).lookup_by_doi(doi) or {}
    best = record.get("best_oa_location") or {}
    locations = [best, *(record.get("oa_locations") or [])]
    return [
        Link(str(loc["url_for_pdf"]), loc.get("license"))
        for loc in locations
        if loc and loc.get("url_for_pdf")
    ]


def _openalex_links(doi: str, email: str | None) -> list[Link]:
    params = {"select": "best_oa_location,locations"}
    if email:
        params["mailto"] = email
    data = _json(f"https://api.openalex.org/works/doi:{quote(doi, safe='/')}", **params) or {}
    locations = [data.get("best_oa_location") or {}, *(data.get("locations") or [])]
    return [
        Link(str(loc["pdf_url"]), loc.get("license"))
        for loc in locations
        if loc and loc.get("pdf_url")
    ]


def _semantic_scholar_links(doi: str, email: str | None) -> list[Link]:
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='/')}"
    data = _json(url, fields="openAccessPdf") or {}
    pdf = data.get("openAccessPdf") or {}
    return [Link(str(pdf["url"]), pdf.get("license"))] if pdf.get("url") else []


_LINK_SOURCES: dict[str, Callable[[str, str | None], list[Link]]] = {
    "arxiv": _arxiv_links,
    "unpaywall": _unpaywall_links,
    "openalex": _openalex_links,
    "semantic_scholar": _semantic_scholar_links,
}


def download_pdf_by_doi(
    doi: str,
    output_path: str | Path,
    email: str | None = None,
    max_bytes: int | None = None,
    skip: tuple[str, ...] = (),
) -> PdfResult | None:
    """Save an open PDF of the paper with this DOI; say which source and link gave it.

    ``email`` is the contact address Unpaywall requires (without it that source is
    skipped) and OpenAlex uses for its polite pool. A source that fails, times out or
    knows nothing is skipped, as is any named in ``skip``; ``None`` means no source had a
    PDF that passed. The result carries the source's name, the link and the licence that
    source reported for it (normalized, ``None`` when it did not say).
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tried: set[str] = set()
    for source in SOURCES:
        if source in skip:
            continue
        try:
            links = _LINK_SOURCES[source](doi, email)
        except Exception as exc:  # noqa: BLE001 - one failing source must not stop the others
            logger.debug(f"{source} gave no links for {doi}: {exc}")
            continue
        for link in links:
            if link.url in tried:
                continue
            tried.add(link.url)
            try:
                if fetch_pdf(link.url, target, max_bytes):
                    logger.info(f"Downloaded the PDF of {doi} from {source}: {link.url}")
                    return PdfResult(
                        target, source, url=link.url, license=normalize_license(link.license)
                    )
            except (requests.RequestException, OSError, ValueError) as exc:
                logger.debug(f"{link.url} did not give a PDF: {exc}")
    return None
