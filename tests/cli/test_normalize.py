"""Unit tests for the normalize CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyeuropepmc.cli.normalize import normalize_app

pytestmark = pytest.mark.unit

runner = CliRunner()

MINIMAL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article" xml:lang="en">
  <front>
    <article-meta>
      <title-group>
        <article-title>Test Article</article-title>
      </title-group>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>This is a test paragraph.</p>
    </sec>
  </body>
</article>"""


@pytest.fixture
def xml_file(tmp_path: Path) -> Path:
    """Create a minimal JATS XML file in a temp directory."""
    path = tmp_path / "test.xml"
    path.write_text(MINIMAL_XML, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# normalize text
# ---------------------------------------------------------------------------


class TestNormalizeText:
    """Tests for the ``normalize text`` command."""

    def test_basic(self, xml_file: Path) -> None:
        """Basic text normalization outputs body text."""
        result = runner.invoke(normalize_app, ["text", str(xml_file)])
        assert result.exit_code == 0
        assert "This is a test paragraph." in result.stdout

    def test_output_file(self, xml_file: Path) -> None:
        """Text can be written to an output file."""
        out = xml_file.with_suffix(".txt")
        result = runner.invoke(
            normalize_app, ["text", str(xml_file), "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        assert "This is a test paragraph." in out.read_text(encoding="utf-8")

    def test_with_options(self, xml_file: Path) -> None:
        """Options like --no-entities are accepted."""
        result = runner.invoke(
            normalize_app,
            ["text", str(xml_file), "--no-entities", "--no-markup", "--no-sections"],
        )
        assert result.exit_code == 0
        assert "test paragraph" in result.stdout

    def test_file_not_found(self) -> None:
        """Non-existent file raises a clear error."""
        result = runner.invoke(normalize_app, ["text", "/nonexistent/file.xml"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_directory_input(self, tmp_path: Path) -> None:
        """Directory input raises a clear error with batch hint."""
        result = runner.invoke(normalize_app, ["text", str(tmp_path)])
        assert result.exit_code == 1
        assert "batch" in result.stdout.lower()


# ---------------------------------------------------------------------------
# normalize sections
# ---------------------------------------------------------------------------


class TestNormalizeSections:
    """Tests for the ``normalize sections`` command."""

    def test_basic(self, xml_file: Path) -> None:
        """Sections command outputs a table."""
        result = runner.invoke(normalize_app, ["sections", str(xml_file)])
        assert result.exit_code == 0
        assert "Introduction" in result.stdout

    def test_output_file(self, xml_file: Path) -> None:
        """Sections can be written as JSON to an output file."""
        out = xml_file.with_suffix(".json")
        result = runner.invoke(
            normalize_app, ["sections", str(xml_file), "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 1


# ---------------------------------------------------------------------------
# normalize bioc
# ---------------------------------------------------------------------------


class TestNormalizeBioc:
    """Tests for the ``normalize bioc`` command."""

    def test_basic(self, xml_file: Path) -> None:
        """BioC command outputs JSON."""
        result = runner.invoke(normalize_app, ["bioc", str(xml_file)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "source" in data or "passages" in data

    def test_output_file(self, xml_file: Path) -> None:
        """BioC output is written to file."""
        out = xml_file.with_suffix(".bioc.json")
        result = runner.invoke(
            normalize_app, ["bioc", str(xml_file), "--output", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "source" in data or "passages" in data


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------


class TestClassify:
    """Tests for the ``normalize classify`` command."""

    def test_known_heading(self) -> None:
        """Known heading shows its mapped type."""
        result = runner.invoke(normalize_app, ["classify", "Introduction"])
        assert result.exit_code == 0
        assert "intro" in result.stdout.lower()

    def test_unknown_heading(self) -> None:
        """Unknown heading maps to 'other'."""
        result = runner.invoke(normalize_app, ["classify", "Random Heading"])
        assert result.exit_code == 0
        assert "other" in result.stdout.lower()


# ---------------------------------------------------------------------------
# batch
# ---------------------------------------------------------------------------


class TestNormalizeBatch:
    """Tests for the ``normalize batch`` command."""

    def test_basic(self, tmp_path: Path) -> None:
        """Batch normalizes all XML files in a directory."""
        # Create XML files
        for name in ("a.xml", "b.xml"):
            (tmp_path / name).write_text(MINIMAL_XML, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app, ["batch", str(tmp_path), str(out_dir)]
        )
        assert result.exit_code == 0
        assert "2 succeeded" in result.stdout
        assert (out_dir / "a.txt").exists()
        assert (out_dir / "b.txt").exists()

    def test_no_xml_files(self, tmp_path: Path) -> None:
        """Error when no XML files found."""
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app, ["batch", str(tmp_path), str(out_dir)]
        )
        assert result.exit_code == 1
        assert "no xml files" in result.stdout.lower()

    def test_sections_format(self, tmp_path: Path) -> None:
        """Sections output format works."""
        (tmp_path / "test.xml").write_text(MINIMAL_XML, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app,
            ["batch", str(tmp_path), str(out_dir), "--output-format", "sections"],
        )
        assert result.exit_code == 0
        assert (out_dir / "test.sections.json").exists()

    def test_bioc_format(self, tmp_path: Path) -> None:
        """BioC output format works."""
        (tmp_path / "test.xml").write_text(MINIMAL_XML, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app,
            ["batch", str(tmp_path), str(out_dir), "--output-format", "bioc"],
        )
        assert result.exit_code == 0
        assert (out_dir / "test.bioc.json").exists()

    def test_invalid_format(self, tmp_path: Path) -> None:
        """Invalid output format raises a clear error."""
        (tmp_path / "test.xml").write_text(MINIMAL_XML, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app,
            ["batch", str(tmp_path), str(out_dir), "--output-format", "invalid"],
        )
        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower()

    def test_recursive(self, tmp_path: Path) -> None:
        """Recursive mode finds XML in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "test.xml").write_text(MINIMAL_XML, encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(
            normalize_app,
            ["batch", str(tmp_path), str(out_dir), "--recursive"],
        )
        assert result.exit_code == 0
        assert "1 succeeded" in result.stdout
        # Output path should mirror subdirectory structure
        assert (out_dir / "sub" / "test.txt").exists()
