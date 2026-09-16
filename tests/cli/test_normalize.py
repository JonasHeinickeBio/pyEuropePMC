"""Unit tests for the normalize CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pyeuropepmc.cli.normalize import normalize_app
from pyeuropepmc.utils.dependencies import is_dependency_available

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not is_dependency_available("typer"), reason="skipped due to missing typer"
    ),
]


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
        result = runner.invoke(normalize_app, ["text", str(xml_file), "--output", str(out)])
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
        result = runner.invoke(normalize_app, ["sections", str(xml_file), "--output", str(out)])
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
        result = runner.invoke(normalize_app, ["bioc", str(xml_file), "--output", str(out)])
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
        result = runner.invoke(normalize_app, ["batch", str(tmp_path), str(out_dir)])
        assert result.exit_code == 0
        assert "2 succeeded" in result.stdout
        assert (out_dir / "a.txt").exists()
        assert (out_dir / "b.txt").exists()

    def test_no_xml_files(self, tmp_path: Path) -> None:
        """Error when no XML files found."""
        out_dir = tmp_path / "out"
        result = runner.invoke(normalize_app, ["batch", str(tmp_path), str(out_dir)])
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


# ---------------------------------------------------------------------------
# Document text is data: Rich markup, encodings, flags and exit codes
# ---------------------------------------------------------------------------

BRACKETS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<article><body>
  <sec><title>Results [part 1/i]</title>
    <p>Gene [a] was fixed at rate r [/i] with P &#x0003c; 0.05 &#x00026; more.</p>
  </sec>
</body></article>"""


class TestDocumentTextIsNotMarkup:
    """Rich reads "[...]" as markup: "[/i]" raised MarkupError, "[a]" vanished."""

    @pytest.fixture
    def brackets_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "brackets.xml"
        path.write_text(BRACKETS_XML, encoding="utf-8")
        return path

    def test_text_prints_brackets_verbatim(self, brackets_file: Path) -> None:
        result = runner.invoke(normalize_app, ["text", str(brackets_file)])
        assert result.exit_code == 0, result.output
        assert "Gene [a] was fixed at rate r [/i] with P < 0.05 & more." in result.stdout

    def test_bioc_prints_valid_json(self, brackets_file: Path) -> None:
        result = runner.invoke(normalize_app, ["bioc", str(brackets_file)])
        assert result.exit_code == 0, result.output
        passages = json.loads(result.stdout)["documents"][0]["passages"]
        assert "[/i]" in passages[0]["text"]

    def test_sections_table_shows_a_bracketed_title(self, brackets_file: Path) -> None:
        result = runner.invoke(normalize_app, ["sections", str(brackets_file)])
        assert result.exit_code == 0, result.output
        assert "[part 1/i]" in result.stdout

    def test_classify_echoes_a_bracketed_heading(self) -> None:
        result = runner.invoke(normalize_app, ["classify", "Methods [/i]"])
        assert result.exit_code == 0, result.output
        assert "Methods [/i]" in result.stdout


class TestInputEncoding:
    def test_the_declared_encoding_is_honoured(self, tmp_path: Path) -> None:
        """Files were read as UTF-8 whatever their XML declaration said."""
        path = tmp_path / "latin1.xml"
        path.write_bytes(
            '<?xml version="1.0" encoding="ISO-8859-1"?>'
            "<article><body><sec><title>T</title><p>Café</p></sec></body></article>".encode(
                "iso-8859-1"
            )
        )
        result = runner.invoke(normalize_app, ["text", str(path)])
        assert result.exit_code == 0, result.output
        assert "Café" in result.stdout


class TestNoMarkup:
    def test_no_markup_keeps_inline_elements(self, tmp_path: Path) -> None:
        """--no-markup changed nothing while flatten_xrefs stayed on."""
        path = tmp_path / "bold.xml"
        path.write_text(
            "<article><body><sec><title>T</title>"
            "<p>Some <bold>bold</bold> text.</p></sec></body></article>",
            encoding="utf-8",
        )
        stripped = runner.invoke(normalize_app, ["text", str(path)])
        kept = runner.invoke(normalize_app, ["text", str(path), "--no-markup"])
        assert "Some bold text." in stripped.stdout
        assert "Some\nbold\ntext." in kept.stdout


class TestBatchExitCode:
    def test_exit_code_is_1_when_every_file_fails(self, tmp_path: Path) -> None:
        (tmp_path / "broken.xml").write_text("<article><body>", encoding="utf-8")
        result = runner.invoke(normalize_app, ["batch", str(tmp_path), str(tmp_path / "out")])
        assert result.exit_code == 1
        assert "0 succeeded, 1 failed" in result.stdout

    def test_exit_code_is_1_when_some_files_fail(self, tmp_path: Path) -> None:
        (tmp_path / "good.xml").write_text(MINIMAL_XML, encoding="utf-8")
        (tmp_path / "broken.xml").write_text("<article><body>", encoding="utf-8")
        out_dir = tmp_path / "out"
        result = runner.invoke(normalize_app, ["batch", str(tmp_path), str(out_dir)])
        assert result.exit_code == 1
        assert "1 succeeded, 1 failed" in result.stdout
        assert (out_dir / "good.txt").exists()

    def test_a_bracket_in_an_error_message_is_printed(self, tmp_path: Path) -> None:
        (tmp_path / "[draft].xml").write_text("<article><body>", encoding="utf-8")
        result = runner.invoke(normalize_app, ["batch", str(tmp_path), str(tmp_path / "out")])
        assert result.exit_code == 1
        assert "[draft].xml" in result.stdout
