
import json
from pathlib import Path

from pyeuropepmc.utils.search_logging import (
    start_search,
    record_query,
    record_results,
    prisma_summary,
)

def test_search_log_entry_fields():
    from pyeuropepmc.utils.search_logging import SearchLogEntry
    entry = SearchLogEntry(
        database="TestDB",
        query="foo",
        filters={"year": 2020},
        results_returned=10,
        notes="note",
        raw_results_path="/tmp/results.json",
    )
    assert entry.database == "TestDB"
    assert entry.query == "foo"
    assert entry.filters["year"] == 2020
    assert entry.results_returned == 10
    assert entry.notes == "note"
    assert entry.raw_results_path == "/tmp/results.json"


def test_search_log_add_and_to_dict():
    from pyeuropepmc.utils.search_logging import SearchLog, SearchLogEntry
    log = SearchLog(title="t", executed_by="x")
    entry = SearchLogEntry(database="db", query="q", filters={})
    log.add_entry(entry)
    d = log.to_dict()
    assert d["title"] == "t"
    assert d["executed_by"] == "x"
    assert len(d["entries"]) == 1


def test_search_log_save_and_load(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import SearchLog, SearchLogEntry
    import json
    log = SearchLog(title="save test")
    entry = SearchLogEntry(database="db", query="q", filters={})
    log.add_entry(entry)
    out = tmp_path / "log.json"
    log.save(out)
    data = json.loads(out.read_text(encoding="utf8"))
    assert data["title"] == "save test"
    assert data["entries"][0]["database"] == "db"


def test_record_query_sets_fields(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import start_search, record_query
    log = start_search("title")
    record_query(log, database="db", query="q", filters={"x": 1}, results_returned=2, notes="n")
    entry = log.entries[-1]
    assert entry.database == "db"
    assert entry.query == "q"
    assert entry.filters["x"] == 1
    assert entry.results_returned == 2
    assert entry.notes == "n"


def test_record_query_raw_results(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import start_search, record_query
    import os
    log = start_search("title")
    raw = [{"id": 1}]
    record_query(log, database="db", query="q", raw_results=raw, raw_results_dir=tmp_path)
    entry = log.entries[-1]
    assert entry.raw_results_path
    assert os.path.exists(entry.raw_results_path)


def test_zip_results_creates_zip(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import zip_results
    f1 = tmp_path / "a.txt"
    f1.write_text("abc")
    zip_path = tmp_path / "z.zip"
    out = zip_results([str(f1)], zip_path)
    assert out == str(zip_path)
    assert zip_path.exists()


def test_sign_file_creates_sig(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import sign_file
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return  # skip if cryptography not installed
    f1 = tmp_path / "a.txt"
    f1.write_text("abc")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "k.pem"
    with open(key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    sig_path = sign_file(f1, key_path)
    assert sig_path.endswith(".sig")
    assert tmp_path.joinpath(sig_path).exists() or Path(sig_path).exists()


def test_sign_and_zip_results(tmp_path: Path):
    from pyeuropepmc.utils.search_logging import sign_and_zip_results
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        return
    f1 = tmp_path / "a.txt"
    f1.write_text("abc")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_path = tmp_path / "k.pem"
    with open(key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    zip_path = tmp_path / "z.zip"
    result = sign_and_zip_results([str(f1)], zip_path, private_key_path=key_path)
    assert isinstance(result, tuple)
    assert Path(result[0]).exists()
    assert Path(result[1]).exists()




def test_search_logging(tmp_path: Path):
    """Test the SearchLog API, including raw_results persistence and zip/sign utilities."""
    from pyeuropepmc.utils.search_logging import zip_results, sign_file
    import os

    log = start_search("test search", executed_by="tester")

    # Test with raw_results persistence
    raw_results = [{"pmid": "1", "title": "Cancer Study"}]
    record_query(
        log,
        database="EuropePMC",
        query="cancer",
        filters={"min_year": 2010},
        results_returned=100,
        raw_results=raw_results,
        raw_results_dir=tmp_path,
    )
    record_query(
        log,
        database="PubMed",
        query="immunotherapy",
        filters={"open_access": "Y"},
        results_returned=50,
    )

    record_results(log, deduplicated_total=120, final_included=5)

    # Save and load to ensure JSON serializable
    out = tmp_path / "search_log.json"
    log.save(out)

    data = json.loads(out.read_text(encoding="utf8"))
    assert data["title"] == "test search"
    assert data["executed_by"] == "tester"
    assert len(data["entries"]) == 2

    # Check that raw_results_path is set and file exists
    entry0 = data["entries"][0]
    assert entry0["raw_results_path"]
    assert os.path.exists(entry0["raw_results_path"])
    with open(entry0["raw_results_path"], encoding="utf8") as fh:
        raw_data = json.load(fh)
    assert raw_data == raw_results

    summary = prisma_summary(log)
    assert summary["total_records_identified"] == 150
    assert summary["deduplicated_total"] == 120
    assert summary["final_included"] == 5

    # Test zip_results utility
    zip_path = tmp_path / "results.zip"
    zipped = zip_results([str(out), str(entry0["raw_results_path"])], zip_path)
    assert os.path.exists(zipped)

    # Test sign_file utility (skip if cryptography not available or no key)
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        # Generate a temporary RSA key for testing
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path = tmp_path / "test_key.pem"
        with open(key_path, "wb") as key_file:
            key_file.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        sig_path = sign_file(zipped, key_path)
        assert os.path.exists(sig_path)
    except ImportError:
        pass  # cryptography not installed, skip sign_file test
