"""scripts/check_changelog.py: new entries stay under [Unreleased]."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_changelog.py"
spec = importlib.util.spec_from_file_location("check_changelog", SCRIPT)
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

BASE = """# Changelog

## [Unreleased]

### Bug Fixes

- a fix waiting for the next release

## [4.4.0] - 2026-10-26

### Features

- diagnostics

## [4.3.0] - 2026-10-25

### Features

- bearer auth
"""


def test_the_repository_changelog_passes():
    changelog = SCRIPT.parents[1] / "CHANGELOG.md"
    assert check.problems(changelog.read_text(encoding="utf-8")) == []


def test_a_clean_changelog_passes():
    assert check.problems(BASE, BASE) == []


def test_a_new_entry_under_unreleased_passes():
    head = BASE.replace("- a fix waiting", "- another fix\n- a fix waiting")
    assert check.problems(head, BASE) == []


def test_a_release_that_cuts_unreleased_passes():
    head = BASE.replace(
        "## [Unreleased]\n\n### Bug Fixes\n\n- a fix waiting for the next release\n",
        "## [Unreleased]\n\n## [4.5.0] - 2026-10-27\n\n### Bug Fixes\n\n- a fix waiting\n",
    )
    assert check.problems(head, BASE) == []


def test_an_entry_merged_under_a_version_already_cut_fails():
    """The incident: git put a branch's lines under the heading main had just cut."""
    head = BASE.replace("- diagnostics\n", "- diagnostics\n- rate limits (from the branch)\n")
    (message,) = check.problems(head, BASE)
    assert "'## [4.4.0]' changed" in message
    assert "Unreleased" in message


def test_a_removed_release_fails():
    head = BASE[: BASE.index("## [4.3.0]")]
    assert any("'## [4.3.0]' was removed" in m for m in check.problems(head, BASE))


def test_a_repeated_heading_in_a_section_fails():
    head = BASE.replace(
        "- a fix waiting for the next release\n",
        "- a fix waiting for the next release\n\n### Bug Fixes\n\n- from a second merge\n",
    )
    (message,) = check.problems(head)
    assert "'### Bug Fixes' 2 times" in message


@pytest.mark.parametrize(
    "head",
    ["# Changelog\n\n## [4.4.0] - x\n", BASE + "\n## [Unreleased]\n"],
    ids=["missing", "twice"],
)
def test_unreleased_must_exist_once(head):
    assert any("exactly one" in m for m in check.problems(head))


def test_unreleased_must_come_first():
    head = "# Changelog\n\n## [4.4.0] - x\n\n## [Unreleased]\n"
    assert any("must be the first section" in m for m in check.problems(head))


def test_the_command_line_exit_status(tmp_path, capsys):
    good, bad, base = tmp_path / "good.md", tmp_path / "bad.md", tmp_path / "base.md"
    base.write_text(BASE, encoding="utf-8")
    good.write_text(BASE, encoding="utf-8")
    bad.write_text(BASE.replace("- bearer auth", "- bearer auth\n- sneaked in"), encoding="utf-8")
    assert check.main([str(good), "--base", str(base)]) == 0
    assert check.main([str(bad), "--base", str(base)]) == 1
    assert "::error" in capsys.readouterr().out
