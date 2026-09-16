"""Regression tests for the search logging defects fixed alongside these tests.

Covered here:

- ``prisma_summary()`` adds up every query run against a database instead of
  keeping only the last count;
- ``generate_private_key(publish_public=True)`` writes a public key file that
  ``load_pem_public_key()`` accepts;
- ``sign_file()`` signs the file, so ``openssl dgst -sha256 -verify`` accepts
  the signature;
- ``record_platform()``, ``record_export()`` and a CSV export handle a log
  that has no entries yet.

The cryptographic tests use real keys rather than mocks, because what broke
was the byte layout the real primitives produce. Every test writes inside a
pytest ``tmp_path``.
"""

from __future__ import annotations

import csv
from pathlib import Path
import shutil
import subprocess

import pytest

from pyeuropepmc.utils.search_logging import (
    CRYPTOGRAPHY_AVAILABLE,
    SearchLog,
    SearchLogEntry,
    generate_private_key,
    prisma_summary,
    record_export,
    record_platform,
    record_query,
    sign_and_zip_results,
    sign_file,
    start_search,
)

requires_cryptography = pytest.mark.skipif(
    not CRYPTOGRAPHY_AVAILABLE, reason="cryptography not installed"
)


class TestPrismaSummaryCounts:
    def test_several_queries_against_one_database_add_up(self):
        log = start_search("multi-query search")
        record_query(log, "Europe PMC", "q1", results_returned=1234)
        record_query(log, "Europe PMC", "q2", results_returned=200)
        record_query(log, "PubMed", "q3", results_returned=50)

        summary = prisma_summary(log)

        assert summary["records_by_database"] == {"Europe PMC": 1434, "PubMed": 50}
        assert summary["total_records_identified"] == 1484

    def test_entries_without_a_count_contribute_zero(self):
        log = start_search("partial counts")
        record_query(log, "Europe PMC", "q1", results_returned=10)
        record_query(log, "Europe PMC", "q2")  # results_returned is None

        summary = prisma_summary(log)

        assert summary["records_by_database"] == {"Europe PMC": 10}
        assert summary["total_records_identified"] == 10

    def test_an_empty_log_summarizes_to_zero(self):
        summary = prisma_summary(start_search("nothing run yet"))

        assert summary["records_by_database"] == {}
        assert summary["total_records_identified"] == 0


@requires_cryptography
class TestKeyGeneration:
    def test_published_public_key_can_be_loaded(self, tmp_path):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        _, pub_path = generate_private_key(
            tmp_path / "key.pem",
            name="A Researcher",
            email="researcher@example.org",
            info="Systematic review 2026",
            key_size=2048,
            publish_public=True,
        )

        assert pub_path is not None
        pem = Path(pub_path).read_bytes()
        # The comment is a preamble, not part of the base64 body.
        lines = pem.decode().splitlines()
        assert lines[0].startswith("# ")
        assert lines[1] == "-----BEGIN PUBLIC KEY-----"
        assert "A Researcher" in lines[0]

        public_key = load_pem_public_key(pem)
        assert public_key.key_size == 2048

    def test_explicit_public_key_path_is_used(self, tmp_path):
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        target = tmp_path / "published" / "public.pem"
        target.parent.mkdir()

        _, pub_path = generate_private_key(tmp_path / "key.pem", public_key_path=target)

        assert Path(pub_path) == target
        assert load_pem_public_key(target.read_bytes()) is not None

    def test_private_key_can_be_loaded(self, tmp_path):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        priv_path, _ = generate_private_key(tmp_path / "key.pem", name="A Researcher")

        assert load_pem_private_key(Path(priv_path).read_bytes(), password=None) is not None

    def test_public_and_private_keys_are_a_pair(self, tmp_path):
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
            load_pem_private_key,
            load_pem_public_key,
        )

        priv_path, pub_path = generate_private_key(tmp_path / "key.pem", publish_public=True)

        private_key = load_pem_private_key(Path(priv_path).read_bytes(), password=None)
        published = load_pem_public_key(Path(pub_path).read_bytes())

        assert published.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ) == private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)


@requires_cryptography
class TestSignFile:
    def _verify_with_cryptography(self, data_path: Path, sig_path: Path, pub_path: Path) -> None:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        public_key = load_pem_public_key(pub_path.read_bytes())
        # Raises InvalidSignature if the signature is not over the file bytes.
        public_key.verify(
            sig_path.read_bytes(),
            data_path.read_bytes(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_signature_verifies_against_the_file_contents(self, tmp_path):
        priv_path, pub_path = generate_private_key(tmp_path / "key.pem", publish_public=True)
        data = tmp_path / "results.json"
        data.write_bytes(b'{"hitCount": 42}\n')

        sig_path = Path(sign_file(data, priv_path))

        assert sig_path == Path(str(data) + ".sig")
        self._verify_with_cryptography(data, sig_path, Path(pub_path))

    def test_signature_rejects_modified_content(self, tmp_path):
        from cryptography.exceptions import InvalidSignature

        priv_path, pub_path = generate_private_key(tmp_path / "key.pem", publish_public=True)
        data = tmp_path / "results.json"
        data.write_bytes(b"original\n")
        sig_path = Path(sign_file(data, priv_path))

        data.write_bytes(b"tampered\n")

        with pytest.raises(InvalidSignature):
            self._verify_with_cryptography(data, sig_path, Path(pub_path))

    @pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")
    def test_openssl_verifies_the_signature(self, tmp_path):
        priv_path, pub_path = generate_private_key(tmp_path / "key.pem", publish_public=True)
        data = tmp_path / "results.txt"
        data.write_bytes(b"provenance record\n")
        sig_path = sign_file(data, priv_path)

        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(pub_path),
                "-signature",
                sig_path,
                str(data),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Verified OK" in result.stdout

    def test_sign_and_zip_results_produces_a_verifiable_signature(self, tmp_path):
        priv_path, pub_path = generate_private_key(tmp_path / "key.pem", publish_public=True)
        member = tmp_path / "results.json"
        member.write_text('{"hitCount": 1}')

        zip_path, sig_path = sign_and_zip_results(
            [str(member)], tmp_path / "bundle.zip", private_key_path=priv_path
        )

        self._verify_with_cryptography(Path(zip_path), Path(sig_path), Path(pub_path))


class TestEmptyLogHandling:
    def test_record_platform_explains_the_empty_log(self):
        log = start_search("nothing run yet")

        with pytest.raises(ValueError, match="record_query"):
            record_platform(log, "Europe PMC REST API")

    def test_record_export_explains_the_empty_log(self, tmp_path):
        log = start_search("nothing run yet")

        with pytest.raises(ValueError, match="record_query"):
            record_export(log, str(tmp_path / "export.csv"), "csv")

    def test_record_platform_still_updates_the_last_entry(self):
        log = start_search("one query")
        record_query(log, "Europe PMC", "cancer")

        record_platform(log, "Europe PMC REST API")

        assert log.entries[-1].platform == "Europe PMC REST API"

    def test_csv_export_of_an_empty_log_writes_a_header_only(self, tmp_path):
        log = SearchLog(title="nothing run yet")
        path = log.export(tmp_path / "log.csv", format="csv")

        with path.open(encoding="utf8", newline="") as fh:
            rows = list(csv.reader(fh))

        assert rows == [list(SearchLogEntry.__dataclass_fields__.keys())]
        assert log.export_format == "csv"

    def test_csv_export_still_writes_entries(self, tmp_path):
        log = start_search("one query")
        record_query(log, "Europe PMC", "cancer", results_returned=3)

        path = log.export(tmp_path / "log.csv", format="csv")

        with path.open(encoding="utf8", newline="") as fh:
            rows = list(csv.DictReader(fh))

        assert len(rows) == 1
        assert rows[0]["database"] == "Europe PMC"
        assert rows[0]["results_returned"] == "3"
