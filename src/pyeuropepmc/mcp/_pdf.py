"""Where downloaded PDFs go, and how a download is reported.

The only MCP tool that writes outside the caches is ``download_papers_pdf``, so the rules
that keep it safe live here and are tested without a network: the caller never chooses a
path (the file name comes from a validated PMCID or DOI, the directory from the server's
environment), and a file that is not a PDF or is too large is removed again. Each file
that is saved gets a line in ``manifest.jsonl`` next to it: where it came from and under
what licence.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any

#: Directory the server saves PDFs in; ``~`` is expanded. Set it in the server's environment.
ENV_DIR = "PYEUROPEPMC_MCP_DOWNLOAD_DIR"
#: Used when ``ENV_DIR`` is unset: a visible folder, because these are files the user wants.
DEFAULT_DIR = Path("~/Downloads/pyeuropepmc")
#: A scanned monograph is tens of MB; more than this is a wrong file or an abuse of the tool.
MAX_PDF_BYTES = 100 * 1024 * 1024

#: One JSON object per line, appended for every PDF saved, in the download directory.
MANIFEST_NAME = "manifest.jsonl"
_manifest_lock = threading.Lock()

_PMCID_RE = re.compile(r"^PMC\d{1,10}$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_PDF_MAGIC = b"%PDF"


def download_dir() -> Path:
    """The folder PDFs are saved in: ``PYEUROPEPMC_MCP_DOWNLOAD_DIR`` or the default."""
    configured = (os.environ.get(ENV_DIR) or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_DIR.expanduser()


def pdf_path(directory: Path, pmcid: str) -> Path:
    """``<directory>/<PMCID>.pdf``; refuses anything that is not a plain PMCID.

    The name is built from the identifier alone, so no request can write outside
    ``directory`` however its inputs are spelled.
    """
    if not _PMCID_RE.fullmatch(pmcid):
        raise ValueError(f"not a PMCID: {pmcid!r}")
    return directory / f"{pmcid}.pdf"


def doi_path(directory: Path, doi: str) -> Path:
    """``<directory>/<DOI with unsafe characters replaced>-<hash>.pdf`` for a paper without PMCID.

    Only letters, digits, ``.``, ``_`` and ``-`` survive in the name and a short hash of the
    DOI keeps two DOIs that differ only in replaced characters apart, so the DOI cannot
    steer the file out of ``directory``.
    """
    if not _DOI_RE.fullmatch(doi):
        raise ValueError(f"not a DOI: {doi!r}")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", doi.lower())[:80].strip("._-")
    digest = hashlib.sha256(doi.lower().encode()).hexdigest()[:8]
    return directory / f"{stem}-{digest}.pdf"


def check_pdf(path: Path) -> str | None:
    """Why the file at ``path`` cannot be kept, or ``None`` when it is a PDF of fair size."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            magic = handle.read(len(_PDF_MAGIC))
    except OSError as exc:
        return f"cannot read {path.name}: {exc}"
    if magic != _PDF_MAGIC:
        return "the file is not a PDF"
    if size > MAX_PDF_BYTES:
        return f"the PDF is {size} bytes, over the {MAX_PDF_BYTES} byte limit"
    return None


def describe(path: Path) -> dict[str, Any]:
    """Where the file is, how big, and its SHA-256 (to tell a re-download from a new file)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def manifest_record(
    target: Path,
    description: dict[str, Any],
    *,
    pmcid: str | None,
    doi: str | None,
    source: str,
    url: str | None,
    license: str | None,
    license_source: str | None,
    md5_verified: bool,
    from_cache: bool,
    version: str,
) -> dict[str, Any]:
    """The manifest line of one saved file.

    ``file`` is the name inside the download directory, not a path, so the manifest stays
    valid when the folder is moved. ``license`` is as the named source reported it
    (normalized); ``null`` means the source did not say, not that the paper is closed.
    """
    return {
        "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "file": target.name,
        "pmcid": pmcid or None,
        "doi": doi or None,
        "source": source,
        "url": url,
        "license": license,
        "license_source": license_source,
        "md5_verified": md5_verified,
        "from_cache": from_cache,
        "sha256": description["sha256"],
        "size_bytes": description["size_bytes"],
        "pyeuropepmc": version,
    }


def append_manifest(directory: Path, record: dict[str, Any]) -> str | None:
    """Append ``record`` as one line of ``manifest.jsonl``; the error text if that fails.

    A download that was saved is not undone because its note could not be written, so this
    reports instead of raising. Downloading a file again adds a second line for it: the last
    line of a file is the current one. The lines are appended whole under a lock.
    """
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
    try:
        with _manifest_lock, (directory / MANIFEST_NAME).open("ab") as handle:
            handle.write(line)
    except OSError as exc:
        return f"cannot write {MANIFEST_NAME}: {exc}"
    return None
