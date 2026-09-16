"""Europe PMC file URLs for the assets a JATS document references.

A JATS ``<graphic>`` or ``<media>`` carries a bare file name - ``gkr715f1``,
``elife-99323-fig1.jpg`` - not a URL. Europe PMC serves those files from one
endpoint::

    https://europepmc.org/api/fulltextRepo
        ?pmcId=PMC3258128&type=FILE&fileName=gkr715f1.jpg
        &mimeType=image/jpeg&version=1

which is what the article pages themselves load. Two details are not optional,
and both were checked against the live service:

* ``mimeType`` must be present. Without it the endpoint answers 500.
* A graphic's file name must carry an extension. JATS from several publishers
  omits it (``gkr715f1``, ``41392_2025_2280_Fig1_HTML``); the stored file is a
  JPEG, and asking for the name as written answers 500.

``version`` is accepted but not required; it is sent as 1, as the article pages
do, so the URLs match the ones a reader's browser would request.
"""

from __future__ import annotations

import posixpath
import re
from urllib.parse import urlencode

__all__ = [
    "DEFAULT_IMAGE_EXTENSION",
    "EUROPE_PMC_FILE_ENDPOINT",
    "asset_file_name",
    "build_asset_url",
    "guess_mime_type",
    "has_known_extension",
    "normalise_pmcid",
]

EUROPE_PMC_FILE_ENDPOINT = "https://europepmc.org/api/fulltextRepo"

#: Extension -> MIME type. ``mimetypes`` from the standard library knows most of
#: these, but its answers depend on the system's mime.types file, and the query
#: string has to be reproducible on any machine.
_MIME_TYPES = {
    "bmp": "image/bmp",
    "csv": "text/csv",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "eps": "application/postscript",
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "m": "text/plain",
    "mov": "video/quicktime",
    "mp3": "audio/mpeg",
    "mp4": "video/mp4",
    "pdf": "application/pdf",
    "png": "image/png",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "svg": "image/svg+xml",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "txt": "text/plain",
    "wav": "audio/wav",
    "webp": "image/webp",
    "wmv": "video/x-ms-wmv",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xml": "application/xml",
    "yaml": "text/yaml",
    "yml": "text/yaml",
    "zip": "application/zip",
}

#: What an extension-less graphic reference is stored as. Every such file in the
#: corpus - Oxford University Press, Springer Nature - is a JPEG.
DEFAULT_IMAGE_EXTENSION = "jpg"

_FALLBACK_MIME = "application/octet-stream"

_EXTENSION_RE = re.compile(r"\.([A-Za-z0-9]+)$")

_PMCID_RE = re.compile(r"^PMC(\d+)$", re.IGNORECASE)


def normalise_pmcid(pmcid: str | None) -> str | None:
    """``pmcid`` as Europe PMC spells it, or ``None`` if it is not a PMC ID.

    Only ``PMC`` followed by digits, in any case, is accepted. A PMID, a DOI or
    a bare number returns ``None``: none of them can address a file in the PMC
    repository, and a URL built from one answers 500 rather than failing where
    the caller can see it. Callers that hold a PMID must resolve it first.
    """
    if not pmcid:
        return None
    match = _PMCID_RE.match(str(pmcid).strip())
    return f"PMC{match.group(1)}" if match else None


def asset_file_name(href: str, default_extension: str | None = None) -> str:
    """The stored file name for a JATS ``xlink:href``.

    Drops any directory part - a few documents write ``./fig1.jpg``. When
    ``default_extension`` is given and the name does not already end in a known
    file type, it is appended: that is how an extension-less ``<graphic>``
    reference names its file. Media and supplementary references are left as
    written, since their extensions (``.yaml``, ``.m``, ``.fasta``) are too
    varied to tell apart from a name such as ``pone.0357759.g001``.
    """
    name = posixpath.basename((href or "").strip())
    if not name or not default_extension or has_known_extension(name):
        return name
    return f"{name}.{default_extension}"


def has_known_extension(file_name: str) -> bool:
    """Whether ``file_name`` ends in a file type this module recognises.

    ``pone.0357759.g001`` and ``10.1371/journal.pone.0357759.s001`` end in a
    dotted suffix too, but not a file type.
    """
    match = _EXTENSION_RE.search(file_name or "")
    return match is not None and match.group(1).lower() in _MIME_TYPES


def guess_mime_type(file_name: str) -> str:
    """MIME type for a file name, falling back to ``application/octet-stream``."""
    match = _EXTENSION_RE.search(file_name or "")
    if not match:
        return _FALLBACK_MIME
    return _MIME_TYPES.get(match.group(1).lower(), _FALLBACK_MIME)


def build_asset_url(
    pmcid: str | None,
    href: str,
    mime_type: str = "",
    default_extension: str | None = None,
) -> str | None:
    """A Europe PMC download URL for ``href`` in article ``pmcid``.

    Returns ``None`` when there is no file name, or when ``pmcid`` is not a PMC
    ID - a URL that cannot resolve is worse than no URL.

    ``mime_type`` overrides the type guessed from the extension; JATS states it
    on ``<media>`` elements, where the extension is often a bare ``.m``.
    ``default_extension`` is passed through to :func:`asset_file_name`.
    """
    normalised = normalise_pmcid(pmcid)
    file_name = asset_file_name(href, default_extension)
    if not normalised or not file_name:
        return None
    query = urlencode(
        {
            "pmcId": normalised,
            "type": "FILE",
            "fileName": file_name,
            "mimeType": mime_type or guess_mime_type(file_name),
            "version": "1",
        }
    )
    return f"{EUROPE_PMC_FILE_ENDPOINT}?{query}"
