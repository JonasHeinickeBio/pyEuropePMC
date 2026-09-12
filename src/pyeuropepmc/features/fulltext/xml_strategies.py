"""
Pluggable full-text XML fetch strategies.

Europe PMC is always tried first (its own methods live on
:class:`~pyeuropepmc.features.fulltext.fulltext_client.FullTextClient`). The
strategies here *extend* coverage with other open services, keyed by PMCID or
DOI:

===================  ==============================================  ===========
strategy             endpoint                                        needs
===================  ==============================================  ===========
``pmc_oa_service``   NCBI PMC OA Web Service (``oa.fcgi``) → .nxml    PMCID
``ncbi_efetch``      E-utilities ``efetch.fcgi?db=pmc&rettype=xml``   PMCID
``bioc_pmc``         BioC-PMC RESTful API (BioC XML)                  PMCID
``doi_negotiation``  DOI content negotiation (``Accept: …+xml``)      DOI
``biorxiv``          bioRxiv / medRxiv API + JATS download            DOI
===================  ==============================================  ===========

Each strategy is a plain callable with the signature

    fetch(ctx: FetchContext) -> str | None

returning the XML text (JATS or BioC) or ``None``. They never raise — a
network / parse failure is logged and returns ``None`` so the chain moves on.
Register a third-party strategy with :func:`register_strategy`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import io
import logging
import re
import tarfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import requests

logger = logging.getLogger(__name__)

__all__ = [
    "FetchContext",
    "XmlFetchStrategy",
    "register_strategy",
    "default_strategies",
    "run_strategies",
]


@dataclass
class FetchContext:
    """Everything a strategy needs to attempt a fetch."""

    pmcid: str | None = None  # digits only, no "PMC" prefix
    doi: str | None = None
    session: requests.Session | None = None
    timeout: int = 30
    email: str | None = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def pmcid_full(self) -> str | None:
        return f"PMC{self.pmcid}" if self.pmcid else None

    def _get(self, url: str, **kw: object) -> requests.Response:
        import requests

        headers = kw.pop("headers", None)
        timeout = kw.pop("timeout", self.timeout)
        if self.session is not None:
            return self.session.get(url, headers=headers, timeout=timeout, **kw)  # type: ignore[arg-type]
        return requests.get(url, headers=headers, timeout=timeout, **kw)  # type: ignore[arg-type]


XmlFetchStrategy = Callable[[FetchContext], "str | None"]


def _looks_like_xml(text: str) -> bool:
    if not text:
        return False
    head = text.lstrip()[:2000].lower()
    if head.startswith(("{", "<!doctype html", "<html")):
        return False
    return head.startswith("<?xml") or head.startswith("<") and "<html" not in head


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------


def fetch_pmc_oa_service(ctx: FetchContext) -> str | None:
    """NCBI PMC OA Web Service — resolves the OA package and pulls the .nxml."""
    if not ctx.pmcid_full:
        return None
    try:
        meta = ctx._get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
            params={"id": ctx.pmcid_full},
        )
        meta.raise_for_status()
        # The response lists <link format="tgz" href="ftp://..."> entries.
        m = re.search(r'href="(ftp[^"]+\.tar\.gz)"', meta.text) or re.search(
            r'href="(https?[^"]+\.tar\.gz)"', meta.text
        )
        if not m:
            logger.debug("PMC OA service: no package link for %s", ctx.pmcid_full)
            return None
        url = m.group(1).replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")
        pkg = ctx._get(url, timeout=max(ctx.timeout, 60))
        pkg.raise_for_status()
        with tarfile.open(fileobj=io.BytesIO(pkg.content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".nxml"):
                    fh = tar.extractfile(member)
                    if fh is not None:
                        text = fh.read().decode("utf-8", errors="replace")
                        if _looks_like_xml(text):
                            return text
        logger.debug("PMC OA service: package for %s had no .nxml", ctx.pmcid_full)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("PMC OA service failed for %s: %s", ctx.pmcid_full, exc)
        return None


def fetch_ncbi_efetch(ctx: FetchContext) -> str | None:
    """NCBI E-utilities efetch — JATS XML straight from PubMed Central."""
    if not ctx.pmcid:
        return None
    try:
        params = {"db": "pmc", "id": ctx.pmcid, "rettype": "xml", "retmode": "xml"}
        if ctx.email:
            params["email"] = ctx.email
            params["tool"] = "pyeuropepmc"
        resp = ctx._get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=params)
        resp.raise_for_status()
        text = resp.text
        # efetch returns <pmc-articleset>…</pmc-articleset>; a body-less stub
        # (just the front matter) means the full text isn't available.
        if _looks_like_xml(text) and "<body" in text.lower():
            return text
        logger.debug("efetch for %s returned no <body>", ctx.pmcid)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("efetch failed for PMC%s: %s", ctx.pmcid, exc)
        return None


def fetch_bioc_pmc(ctx: FetchContext) -> str | None:
    """BioC-PMC RESTful API — full text as BioC XML."""
    if not ctx.pmcid_full:
        return None
    url = (
        "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/"
        f"BioC_xml/{ctx.pmcid_full}/unicode"
    )
    try:
        resp = ctx._get(url)
        resp.raise_for_status()
        text = resp.text
        if _looks_like_xml(text) and "<passage>" in text:
            return text
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("BioC-PMC failed for %s: %s", ctx.pmcid_full, exc)
        return None


def fetch_doi_negotiation(ctx: FetchContext) -> str | None:
    """DOI content negotiation — ask the publisher for JATS / generic XML."""
    if not ctx.doi:
        return None
    accept = (
        "application/vnd.jats+xml, application/vnd.crossref.unixsd+xml;q=0.9, "
        "application/xml;q=0.8, text/xml;q=0.7"
    )
    try:
        resp = ctx._get(
            f"https://doi.org/{ctx.doi}",
            headers={"Accept": accept},
            allow_redirects=True,
        )
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()
        if "xml" in ctype and _looks_like_xml(resp.text) and "crossref" not in resp.text[:400]:
            return resp.text
        return None
    except Exception as exc:  # noqa: BLE001
        logger.debug("DOI negotiation failed for %s: %s", ctx.doi, exc)
        return None


def fetch_biorxiv(ctx: FetchContext) -> str | None:
    """bioRxiv / medRxiv — JATS XML for the preprint behind a DOI."""
    if not ctx.doi or "10.1101/" not in ctx.doi:
        return None
    for server in ("biorxiv", "medrxiv"):
        try:
            meta = ctx._get(f"https://api.biorxiv.org/details/{server}/{ctx.doi}")
            meta.raise_for_status()
            payload = meta.json()
            collection = payload.get("collection") or []
            if not collection:
                continue
            # JATS lives in the S3 bucket keyed by the article's "jatsxml" URL.
            jats_url = collection[-1].get("jatsxml")
            if not jats_url:
                continue
            xml = ctx._get(jats_url, timeout=max(ctx.timeout, 60))
            xml.raise_for_status()
            if _looks_like_xml(xml.text):
                return xml.text
        except Exception as exc:  # noqa: BLE001
            logger.debug("%s API failed for %s: %s", server, ctx.doi, exc)
    return None


_BUILTIN: dict[str, XmlFetchStrategy] = {
    "pmc_oa_service": fetch_pmc_oa_service,
    "ncbi_efetch": fetch_ncbi_efetch,
    "bioc_pmc": fetch_bioc_pmc,
    "doi_negotiation": fetch_doi_negotiation,
    "biorxiv": fetch_biorxiv,
}

_REGISTRY: dict[str, XmlFetchStrategy] = dict(_BUILTIN)

# Order the chain runs in (after Europe PMC's own methods).
DEFAULT_ORDER = ["pmc_oa_service", "ncbi_efetch", "bioc_pmc", "doi_negotiation", "biorxiv"]


def register_strategy(name: str, strategy: XmlFetchStrategy, *, replace: bool = False) -> None:
    """Add a third-party XML fetch strategy."""
    if name in _REGISTRY and not replace:
        raise ValueError(f"strategy {name!r} already registered; pass replace=True")
    _REGISTRY[name] = strategy


def default_strategies(names: list[str] | None = None) -> list[tuple[str, XmlFetchStrategy]]:
    """Return ``(name, callable)`` pairs in run order."""
    order = names or DEFAULT_ORDER
    return [(n, _REGISTRY[n]) for n in order if n in _REGISTRY]


def run_strategies(
    ctx: FetchContext,
    names: list[str] | None = None,
) -> tuple[str | None, str | None]:
    """Run the chain, returning ``(xml_text, winning_strategy_name)``."""
    for name, strategy in default_strategies(names):
        logger.debug("Trying XML strategy %s for %s / %s", name, ctx.pmcid_full, ctx.doi)
        text = strategy(ctx)
        if text:
            logger.info("XML strategy %s succeeded for %s / %s", name, ctx.pmcid_full, ctx.doi)
            return text, name
    return None, None
