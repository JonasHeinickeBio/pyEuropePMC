"""Benchmark CLI output, dataset detection, skip_errors and the reproduce command.

- ``pyeuropepmc benchmark report FILE`` raised TypeError on reports written by ``run``.
- ``profile`` showed 0.000000 per call and ``profile-memory`` "unknown" locations.
- ``is_downloaded`` looked for ``*.xml`` in datasets whose articles are ``*.nxml``.
- ``BenchmarkRunner(skip_errors=False)`` still skipped failing articles.
- The generated "How to reproduce" command selected no tests.
"""

from __future__ import annotations

from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest

from pyeuropepmc.benchmark.dataset import BenchmarkDataset
from pyeuropepmc.benchmark.runner import BenchmarkRunner
from pyeuropepmc.utils.dependencies import is_dependency_available

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_XML = ROOT / "tests" / "fixtures" / "fulltext_downloads" / "PMC3258128.xml"

ARTICLE = """<?xml version="1.0"?>
<article>
<front><article-meta>
<article-id pub-id-type="pmcid">PMC9999999</article-id>
<title-group><article-title>Benchmark Test Article</article-title></title-group>
</article-meta></front>
<body><sec><title>Introduction</title><p>Some text.</p></sec></body>
</article>
"""

needs_typer = pytest.mark.skipif(not is_dependency_available("typer"), reason="needs typer")


@pytest.fixture
def local_dir(tmp_path):
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "article_one.xml").write_text(ARTICLE, encoding="utf-8")
    (xml_dir / "article_two.xml").write_text(
        ARTICLE.replace("9999999", "8888888"), encoding="utf-8"
    )
    return xml_dir


def _cli():
    from typer.testing import CliRunner

    from pyeuropepmc.cli import app

    return CliRunner(), app


@needs_typer
class TestReportCommand:
    @pytest.fixture
    def report_file(self, local_dir, tmp_path):
        report = BenchmarkRunner(BenchmarkDataset("local", local_path=local_dir)).run_all()
        return report.save_json(tmp_path / "results.json")

    def test_report_written_by_run_is_printed(self, report_file):
        runner, app = _cli()
        result = runner.invoke(app, ["benchmark", "report", str(report_file)])

        assert result.exit_code == 0, result.output
        assert re.search(r"Composite score: \d\.\d{4}", result.output)
        assert "Articles        : 2" in result.output
        assert "[local]" in result.output
        assert "Parse time     :" in result.output

    def test_verbose_lists_articles_by_name(self, report_file):
        runner, app = _cli()
        result = runner.invoke(app, ["benchmark", "report", str(report_file), "--verbose"])

        assert result.exit_code == 0, result.output
        assert "article_one" in result.output
        assert "[local]" in result.output
        assert re.search(r"article_two\s+\[local\]\s+score=\d\.\d{4}", result.output)

    def test_report_with_a_failed_article_metric(self, tmp_path):
        from pyeuropepmc.benchmark.report import BenchmarkReport

        report = BenchmarkReport()
        report.add_article_result("local", "broken", {"error": "boom", "per_metric": {}})
        path = report.save_json(tmp_path / "r.json")

        runner, app = _cli()
        result = runner.invoke(app, ["benchmark", "report", str(path), "-v"])

        assert result.exit_code == 0, result.output
        assert "score=N/A" in result.output


@needs_typer
class TestProfileCommands:
    def test_per_call_column_is_filled(self):
        runner, app = _cli()
        result = runner.invoke(app, ["benchmark", "profile", str(FIXTURE_XML), "--top", "5"])

        assert result.exit_code == 0, result.output
        per_call = [float(v) for v in re.findall(r"\s(\d+\.\d{6})\s*$", result.output, re.M)]
        assert per_call, result.output
        assert any(v > 0 for v in per_call), result.output

    def test_memory_location_column_shows_the_site(self):
        runner, app = _cli()
        result = runner.invoke(
            app, ["benchmark", "profile-memory", str(FIXTURE_XML), "--top", "3"]
        )

        assert result.exit_code == 0, result.output
        table = result.output.split("Top allocations:")[1].split("Allocations by module")[0]
        rows = [line for line in table.splitlines() if re.match(r"\s+-?\d+\.\d\s", line)]
        assert rows, result.output
        assert all(re.search(r"\S+:\d+", row) for row in rows), rows
        assert "unknown" not in table

    def test_allocation_site_formatting(self):
        from pyeuropepmc.cli.benchmark import _allocation_site

        assert _allocation_site({"filename": "a.py", "lineno": 3, "function": ""}) == "a.py:3"
        assert (
            _allocation_site({"filename": "a.py", "lineno": 3, "function": "f"}) == "a.py:3 in f"
        )
        assert _allocation_site({"size_kib": 1.0}) == "unknown"


class TestIsDownloaded:
    @pytest.mark.parametrize("name", ["PMC_sample_1943", "eLife_984", "biorxiv-10k-test-2000"])
    def test_nxml_datasets(self, tmp_path, name):
        dataset = BenchmarkDataset(name, data_dir=tmp_path)
        assert dataset.info.filename_glob == "*.nxml"
        assert dataset.is_downloaded is False

        target = tmp_path / name
        target.mkdir()
        (target / "article.nxml").write_text(ARTICLE, encoding="utf-8")
        assert dataset.is_downloaded is True
        assert dataset.article_count == 1

    def test_xml_files_do_not_count_for_an_nxml_dataset(self, tmp_path):
        target = tmp_path / "PMC_sample_1943"
        target.mkdir()
        (target / "stray.xml").write_text(ARTICLE, encoding="utf-8")
        assert BenchmarkDataset("PMC_sample_1943", data_dir=tmp_path).is_downloaded is False

    def test_local_xml_dataset(self, local_dir):
        assert BenchmarkDataset("local", local_path=local_dir).is_downloaded is True

    @needs_typer
    def test_run_does_not_offer_to_download_an_nxml_dataset(self, tmp_path, monkeypatch):
        target = tmp_path / "eLife_984"
        target.mkdir()
        (target / "article.nxml").write_text(ARTICLE, encoding="utf-8")

        def no_download(*args, **kwargs):
            raise AssertionError("download() must not be called")

        monkeypatch.setattr(BenchmarkDataset, "download", no_download)
        runner, app = _cli()
        result = runner.invoke(
            app, ["benchmark", "run", "eLife_984", "--data-dir", str(tmp_path)], input="n\n"
        )

        assert result.exit_code == 0, result.output
        assert "not downloaded" not in result.output
        assert "Articles 1/1 successful" in result.output


class TestSkipErrors:
    @pytest.fixture
    def broken_dir(self, local_dir):
        (local_dir / "article_three.xml").write_text("<article><unclosed>", encoding="utf-8")
        return local_dir

    def test_skip_errors_true_records_and_continues(self, broken_dir):
        runner = BenchmarkRunner(
            BenchmarkDataset("local", local_path=broken_dir), skip_errors=True
        )
        report = runner.run_all()

        assert runner.stats["failed"] == 1
        assert runner.stats["successful"] == 2
        assert len(report.article_results) == 2

    @pytest.mark.parametrize("profile", [False, True])
    def test_skip_errors_false_raises(self, broken_dir, profile):
        runner = BenchmarkRunner(
            BenchmarkDataset("local", local_path=broken_dir), skip_errors=False, profile=profile
        )
        with pytest.raises(Exception, match=r"(?i)pars|syntax|xml|unclosed|mismatch|token"):
            runner.run_all()
        assert runner.stats["failed"] == 1

    @needs_typer
    def test_cli_no_skip_errors_stops_the_run(self, broken_dir):
        runner, app = _cli()
        result = runner.invoke(
            app, ["benchmark", "run", "local", "--local-path", str(broken_dir), "--no-skip-errors"]
        )
        # the parse error itself, not a usage error (exit code 2) for an unknown option
        assert result.exit_code == 1, result.output
        assert "PARSE002" in str(result.exception)

    @needs_typer
    def test_cli_skips_errors_by_default(self, broken_dir):
        runner, app = _cli()
        result = runner.invoke(app, ["benchmark", "run", "local", "--local-path", str(broken_dir)])
        assert result.exit_code == 0, result.output
        assert "Articles 2/3 successful (1 errors)" in result.output

    def test_skip_errors_false_raises_on_unreadable_file(self, local_dir):
        (local_dir / "not_utf8.xml").write_bytes(b"\xff\xfe<article/>")
        runner = BenchmarkRunner(
            BenchmarkDataset("local", local_path=local_dir), skip_errors=False
        )
        with pytest.raises(UnicodeDecodeError):
            runner.run_all()


class TestReproduceCommand:
    def test_report_contains_the_command(self):
        sys.path.insert(0, str(ROOT))
        try:
            from tests.benchmark_article_client import (
                REPRODUCE_COMMAND,
                BenchmarkManager,
                BenchmarkSuiteResult,
            )
        finally:
            sys.path.remove(str(ROOT))

        report = BenchmarkManager().generate_comprehensive_report(
            BenchmarkSuiteResult(suite_name="s", timestamp="t")
        )
        assert f"```bash\n{REPRODUCE_COMMAND}\n```" in report

    def test_command_selects_the_benchmark_test(self):
        """It used to collect nothing: the default options deselect benchmark tests."""
        sys.path.insert(0, str(ROOT))
        try:
            from tests.benchmark_article_client import REPRODUCE_COMMAND
        finally:
            sys.path.remove(str(ROOT))

        args = shlex.split(REPRODUCE_COMMAND)
        assert args[0] == "pytest"
        proc = subprocess.run(
            # -q on top of the configured -q prints "<file>: <count>" per file
            [sys.executable, "-m", "pytest", *args[1:], "--collect-only", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # exit code 5 is "no tests collected"
        assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
        assert "benchmark_article_client.py: 1" in proc.stdout, proc.stdout

    def test_readme_shows_the_same_command(self):
        sys.path.insert(0, str(ROOT))
        try:
            from tests.benchmark_article_client import REPRODUCE_COMMAND
        finally:
            sys.path.remove(str(ROOT))

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert REPRODUCE_COMMAND in readme
