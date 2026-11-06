"""Where downloaded PDFs go, and how a download is reported.

The only MCP tool that writes outside the caches is ``download_papers_pdf``, so the rules
that keep it safe live here and are tested without a network: the caller never chooses a
path (the file name comes from a validated PMCID, the directory from the server's
environment), and a file that is not a PDF or is too large is removed again.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
from typing import Any

#: Directory the server saves PDFs in; ``~`` is expanded. Set it in the server's environment.
ENV_DIR = "PYEUROPEPMC_MCP_DOWNLOAD_DIR"
#: Used when ``ENV_DIR`` is unset: a visible folder, because these are files the user wants.
DEFAULT_DIR = Path("~/Downloads/pyeuropepmc")
#: A scanned monograph is tens of MB; more than this is a wrong file or an abuse of the tool.
MAX_PDF_BYTES = 100 * 1024 * 1024

_PMCID_RE = re.compile(r"^PMC\d{1,10}$")
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
