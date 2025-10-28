"""
Search logging utilities for reproducible, auditable literature searches
(PRISMA/Cochrane compliant).

This module provides a robust, file-system-friendly framework to record and persist all
search queries (search strings), filters, and results in a structured JSON format. It is
designed for full PRISMA and Cochrane compliance:

- All search strings (queries) for each database/source are stored, with exact syntax,
    date run, and filters applied.
- Optionally, raw search results can be persisted to disk for auditability and
    reproducibility.
- The log can be included in systematic review methods, PRISMA flow diagrams, and
    supplements.
- All file operations and cryptographic steps are wrapped in try/except and logged for
    traceability.
- Utility functions are provided to zip and cryptographically sign result files for
    provenance.

See function/class docstrings for usage details and error handling notes.

PRISMA 2020 Flowchart:
---------------------
To generate a PRISMA 2020 flow diagram from your exported search log data, you can use the
official interactive tool at:
    https://estech.shinyapps.io/prisma_flowdiagram/
This web app allows you to create publication-ready PRISMA diagrams by uploading or entering
your review data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import getpass
import json
import logging
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    serialization = None
    rsa = None

logger = logging.getLogger(__name__)


@dataclass
class SearchLogEntry:
    """A single search query log entry, including query string, filters, and optional
    raw results path.

    Attributes:
        database: Name of the database/source (e.g., PubMed, EuropePMC).
        query: The exact search string used (Boolean logic, field tags, etc.).
        filters: Dict of explicit filters (date range, types, language, open access, etc.).
        date_run: ISO timestamp when the query was executed.
        results_returned: Number of results returned by this query.
        notes: Optional notes (e.g., version, searcher, comments).
        raw_results_path: Optional path to a file containing the raw results for this query.
        platform: Optional. The search platform or interface used (e.g., web, API, tool version).
        export_path: Optional. Path to exported results file (.csv, .ris, .nbib).
    """

    database: str
    query: str
    filters: dict[str, Any]
    date_run: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    results_returned: int | None = None
    notes: str | None = None
    raw_results_path: str | None = None
    platform: str | None = None
    export_path: str | None = None


@dataclass
class SearchLog:
    """A structured log of all search queries, filters, and results for a systematic review.

    Attributes:
        title: Short descriptive title of the search (e.g., "cancer immunotherapy search").
        executed_by: Optional person or script name that ran the search.
        created_at: ISO timestamp when the log was created.
        entries: List of SearchLogEntry objects (one per query).
        deduplicated_total: Total records after deduplication across databases.
        final_included: Final number of included studies after screening.
        last_updated: ISO timestamp when the log was last updated.
        peer_reviewed: Optional. Peer review status or PRESS/JBI checklist path.
        export_format: Optional. Format used for machine-readable export (json, csv, ris).
    """

    title: str
    executed_by: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    entries: list[SearchLogEntry] = field(default_factory=list)
    deduplicated_total: int | None = None
    final_included: int | None = None
    peer_reviewed: str | None = None
    export_format: str | None = None

    def add_entry(self, entry: SearchLogEntry) -> None:
        """Add a SearchLogEntry to the log and update last_updated."""
        self.entries.append(entry)
        self.last_updated = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert the log to a serializable dictionary."""
        data = asdict(self)
        return data

    def export(self, path: str | Path, format: str = "json") -> Path:
        """Export the log in a machine-readable format (json, csv, ris)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if format == "json":
            with p.open("w", encoding="utf8") as fh:
                json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
        elif format == "csv":
            import csv

            with p.open("w", encoding="utf8", newline="") as fh:
                fieldnames = list(self.entries[0].__dataclass_fields__.keys())
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                for entry in self.entries:
                    writer.writerow(asdict(entry))
        elif format == "ris":
            # Minimal RIS export for demonstration
            with p.open("w", encoding="utf8") as fh:
                for entry in self.entries:
                    fh.write("TY  - SER\n")
                    fh.write(f"DB  - {entry.database}\n")
                    fh.write(f"TI  - {self.title}\n")
                    fh.write(f"DA  - {entry.date_run}\n")
                    fh.write(f"N1  - {entry.query}\n")
                    fh.write("ER  - \n\n")
        else:
            raise ValueError(f"Unsupported export format: {format}")
        self.export_format = format
        return p

    def save(self, path: str | Path, *, indent: int = 2) -> Path:
        """Save the log as a JSON file. Logs errors and raises on failure."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = self.to_dict()
            with p.open("w", encoding="utf8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=indent)
            logger.info(f"Search log saved to {p}")
            return p
        except Exception as e:
            logger.error(f"Failed to save search log: {e}")
            raise


def start_search(title: str, executed_by: str | None = None) -> SearchLog:
    """Create a new SearchLog instance for a systematic review search.

    Args:
        title: Short descriptive title of the search (e.g., "cancer immunotherapy search").
        executed_by: Optional person or script name that ran the search.

    Returns:
        SearchLog: A new SearchLog object ready to record queries.
    """
    return SearchLog(title=title, executed_by=executed_by)


def record_query(
    log: SearchLog,
    database: str,
    query: str,
    filters: dict[str, Any] | None = None,
    results_returned: int | None = None,
    notes: str | None = None,
    raw_results: Any = None,
    raw_results_dir: str | Path | None = None,
    raw_results_filename: str | None = None,
    platform: str | None = None,
    export_path: str | None = None,
) -> None:
    """Record a single query run against a database, including all filters and optional
    raw results.

    This function stores the exact search string (query) used for each database/source, as
    required by PRISMA and Cochrane reporting standards. All queries, filters, and results are
    persisted for full reproducibility and supplement inclusion. Optionally, the raw search
    results can be saved to a separate file, and the path is stored in the log entry.
    All file operations are logged and errors are reported via logger.

    Args:
        log: The SearchLog instance to update.
        database: Name of the database/source (e.g., PubMed, EuropePMC).
        query: The exact search string used (Boolean logic, field tags, etc.).
        filters: Dict of explicit filters (date range, types, language, open access,
            semantic thresholds, etc.).
        results_returned: Number of results returned by this query.
        notes: Optional notes (e.g., version, searcher, comments).
        raw_results: Optional. The raw results object to persist (will be saved as JSON).
        raw_results_dir: Optional. Directory to save raw results file. If not given, not saved.
        raw_results_filename: Optional. Filename for raw results file. If not given, auto-named.
    """
    raw_results_path = None
    if raw_results is not None and raw_results_dir is not None:
        try:
            raw_results_dir = Path(raw_results_dir)
            raw_results_dir.mkdir(parents=True, exist_ok=True)
            if raw_results_filename is None:
                safe_db = database.replace(" ", "_").replace("/", "_")
                safe_time = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
                raw_results_filename = f"{safe_db}_results_{safe_time}.json"
            raw_results_path = str(raw_results_dir / raw_results_filename)
            with open(raw_results_path, "w", encoding="utf8") as fh:
                json.dump(raw_results, fh, ensure_ascii=False, indent=2)
            logger.info(f"Raw results saved to {raw_results_path}")
        except Exception as e:
            logger.error(f"Failed to save raw results: {e}")
            raw_results_path = None
    entry = SearchLogEntry(
        database=database,
        query=query,
        filters=filters or {},
        results_returned=results_returned,
        notes=notes,
        raw_results_path=raw_results_path,
        platform=platform,
        export_path=export_path,
    )
    log.add_entry(entry)


def record_peer_review(log: SearchLog, peer_reviewed: str | None = None) -> None:
    """Record peer review status or checklist path (PRESS/JBI)."""
    log.peer_reviewed = peer_reviewed


def record_platform(log: SearchLog, platform: str) -> None:
    """Record the search platform/interface/tool version used."""
    log.entries[-1].platform = platform


def record_export(log: SearchLog, export_path: str, format: str) -> None:
    """Record the export file path and format for a query entry."""
    log.entries[-1].export_path = export_path
    log.export_format = format


def zip_results(files: list[str], zip_path: str | Path) -> str:
    """
    Zip result files for provenance and reproducibility.
    Each file is added to the archive with its basename. All file operations are logged.
    """
    import zipfile

    zip_path = Path(zip_path)
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                try:
                    zf.write(f, arcname=Path(f).name)
                    logger.info(f"Added {f} to zip archive {zip_path}")
                except Exception as e:
                    logger.error(f"Failed to add {f} to zip: {e}")
        logger.info(f"Created zip archive {zip_path}")
        return str(zip_path)
    except Exception as e:
        logger.error(f"Failed to create zip archive {zip_path}: {e}")
        raise


def sign_file(file_path: str | Path, private_key_path: str | Path) -> str:
    """
    Sign a file with an RSA private key (PKCS1v15, SHA256) and save the signature.

    All file and cryptographic operations are logged. Only RSA keys are supported.

    Args:
        file_path: Path to the file to sign.
        private_key_path: Path to private key for signing (PEM format).

    Returns:
        Path to the created signature file.

    Raises:
        Exception: If signing fails or the key is not RSA.
    """
    import hashlib

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    file_path = Path(file_path)
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        digest = hashlib.sha256(file_bytes).digest()
        with open(private_key_path, "rb") as key_file:
            private_key = load_pem_private_key(key_file.read(), password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            logger.error("Loaded private key does not support RSA signing.")
            raise TypeError("Loaded private key does not support RSA signing.")
        signature = private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
        sig_path = str(file_path) + ".sig"
        with open(sig_path, "wb") as sig_file:
            sig_file.write(signature)
        logger.info(
            f"Signed file {file_path} with key {private_key_path}, signature at {sig_path}"
        )
        return sig_path
    except Exception as e:
        logger.error(f"Failed to sign file {file_path}: {e}")
        raise


def sign_and_zip_results(
    files: list[str],
    zip_path: str | Path,
    cert_path: str | Path | None = None,
    private_key_path: str | Path | None = None,
) -> str | tuple[str, str]:
    """Optionally sign and zip result files for provenance (legacy wrapper).

    This function is a convenience wrapper for zip_results and sign_file.
    All operations are logged.

    Args:
        files: List of file paths to include in the zip.
        zip_path: Path to output zip file.
        cert_path: (Unused, for compatibility.)
        private_key_path: Optional path to private key for signing.

    Returns:
        Path to the created zip file (and signature if signing is used).

    Raises:
        Exception: If zipping or signing fails.
    """
    try:
        zip_file = zip_results(files, zip_path)
        if private_key_path:
            sig_file = sign_file(zip_file, private_key_path)
            logger.info(f"Created zip and signature: {zip_file}, {sig_file}")
            return zip_file, sig_file
        logger.info(f"Created zip: {zip_file}")
        return zip_file
    except Exception as e:
        logger.error(f"Failed to sign and zip results: {e}")
        raise


def record_results(
    log: SearchLog,
    deduplicated_total: int | None,
    final_included: int | None,
) -> None:
    """Record aggregate counts for PRISMA-style reporting.

    Args:
        log: The SearchLog instance to update.
        deduplicated_total: Total records after deduplication across databases.
        final_included: Final number of included studies after screening.
    """
    log.deduplicated_total = deduplicated_total
    log.final_included = final_included


def prisma_summary(log: SearchLog) -> dict[str, Any]:
    """Return a minimal PRISMA-like summary dict containing counts useful for methods sections.

    This is intentionally minimal (numbers only) and can be extended for more detailed reporting.

    Args:
        log: The SearchLog instance to summarize.

    Returns:
        dict: Summary with counts for PRISMA flow diagram and methods.
    """
    by_db = {e.database: (e.results_returned or 0) for e in log.entries}
    total_records = sum(by_db.values())
    summary = {
        "title": log.title,
        "executed_by": log.executed_by,
        "created_at": log.created_at,
        "records_by_database": by_db,
        "total_records_identified": total_records,
        "deduplicated_total": log.deduplicated_total,
        "final_included": log.final_included,
    }
    return summary


def generate_private_key(
    private_key_path: str | Path,
    public_key_path: str | Path | None = None,
    name: str | None = None,
    email: str | None = None,
    info: str | None = None,
    key_size: int = 2048,
    publish_public: bool = False,
) -> tuple[str, str | None]:
    """
    Generate a new RSA private key and save it to disk, with optional metadata and
    public key export.

    Args:
        private_key_path: Path to save the private key PEM file.
        public_key_path: Optional path to save the public key PEM file.
        name: Optional user name to embed as a PEM comment.
        email: Optional email to embed as a PEM comment.
        info: Optional additional info (e.g., affiliation, purpose).
        key_size: RSA key size in bits (default 2048).
        publish_public: If True, export the public key PEM for publishing.

    Returns:
        Tuple of (private_key_path, public_key_path or None)
    """
    if serialization is None or rsa is None:
        raise ImportError("cryptography library is required for key generation.")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    comments = []
    if name:
        comments.append(f"Name: {name}")
    if email:
        comments.append(f"Email: {email}")
    if info:
        comments.append(f"Info: {info}")
    comments.append(f"Created: {datetime.utcnow().isoformat()}")
    comments.append(f"User: {getpass.getuser()}")
    comment_str = ", ".join(comments)

    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_path = str(private_key_path)
    with open(private_key_path, "wb") as f:
        # Sanitize comment to remove newlines and special characters
        sanitized_comment = (
            comment_str.replace("\n", " ").replace("\r", " ").replace("#", "").strip()
        )
        f.write(f"# {sanitized_comment}\n".encode())
        f.write(private_key_bytes)
    logger.info(f"Generated new RSA private key at {private_key_path}")

    pub_path = None
    if publish_public or public_key_path:
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        pub_path = str(public_key_path) if public_key_path else private_key_path + ".pub.pem"
        with open(pub_path, "wb") as f:
            f.write(b"-----BEGIN PUBLIC KEY-----\n")
            f.write(f"# {comment_str}\n".encode())
            f.write(b"".join(public_key_bytes.splitlines(keepends=True)[1:]))
        logger.info(f"Exported public key at {pub_path}")

    return private_key_path, pub_path


__all__ = [
    "SearchLog",
    "SearchLogEntry",
    "start_search",
    "record_query",
    "record_results",
    "prisma_summary",
    "zip_results",
    "sign_file",
    "sign_and_zip_results",
    "record_peer_review",
    "record_platform",
    "record_export",
]
