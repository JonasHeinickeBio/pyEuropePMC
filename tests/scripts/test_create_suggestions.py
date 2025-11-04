"""Tests for the create_suggestions.py script."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Import the functions we want to test
# We need to add scripts to the path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from create_suggestions import is_duplicate, parse_suggestions


class TestIsDuplicate:
    """Tests for the is_duplicate function."""

    def test_exact_match(self):
        """Test exact title match is detected as duplicate."""
        existing = [
            {"title": "Fix memory leak", "number": 1, "labels": []},
            {"title": "Add new feature", "number": 2, "labels": []},
        ]
        assert is_duplicate("Fix memory leak", existing) is True

    def test_case_insensitive_match(self):
        """Test case-insensitive matching."""
        existing = [{"title": "Fix Memory Leak", "number": 1, "labels": []}]
        assert is_duplicate("fix memory leak", existing) is True

    def test_substring_match(self):
        """Test that substring is detected as duplicate."""
        existing = [
            {"title": "Fix memory leak in parser module", "number": 1, "labels": []}
        ]
        assert is_duplicate("Fix memory leak", existing) is True

    def test_no_match(self):
        """Test that different titles are not duplicates."""
        existing = [
            {"title": "Fix memory leak", "number": 1, "labels": []},
            {"title": "Add new feature", "number": 2, "labels": []},
        ]
        assert is_duplicate("Improve documentation", existing) is False

    def test_empty_list(self):
        """Test with no existing issues."""
        assert is_duplicate("Any title", []) is False


class TestParseSuggestions:
    """Tests for the parse_suggestions function."""

    def test_parse_list_format(self, tmp_path):
        """Test parsing suggestions in list format."""
        suggestions_file = tmp_path / "suggestions.json"
        data = [
            {"title": "Test 1", "body": "Body 1", "labels": ["bug"]},
            {"title": "Test 2", "body": "Body 2", "labels": ["enhancement"]},
        ]
        suggestions_file.write_text(json.dumps(data))

        result = parse_suggestions(suggestions_file)
        assert len(result) == 2
        assert result[0]["title"] == "Test 1"
        assert result[1]["title"] == "Test 2"

    def test_parse_dict_with_suggestions_key(self, tmp_path):
        """Test parsing when JSON has 'suggestions' key."""
        suggestions_file = tmp_path / "suggestions.json"
        data = {
            "suggestions": [
                {"title": "Test 1", "body": "Body 1", "labels": ["bug"]},
            ]
        }
        suggestions_file.write_text(json.dumps(data))

        result = parse_suggestions(suggestions_file)
        assert len(result) == 1
        assert result[0]["title"] == "Test 1"

    def test_parse_dict_with_issues_key(self, tmp_path):
        """Test parsing when JSON has 'issues' key."""
        suggestions_file = tmp_path / "suggestions.json"
        data = {
            "issues": [
                {"title": "Test 1", "body": "Body 1", "labels": ["bug"]},
            ]
        }
        suggestions_file.write_text(json.dumps(data))

        result = parse_suggestions(suggestions_file)
        assert len(result) == 1
        assert result[0]["title"] == "Test 1"

    def test_parse_single_dict(self, tmp_path):
        """Test parsing when JSON is a single suggestion dict."""
        suggestions_file = tmp_path / "suggestions.json"
        data = {"title": "Test 1", "body": "Body 1", "labels": ["bug"]}
        suggestions_file.write_text(json.dumps(data))

        result = parse_suggestions(suggestions_file)
        assert len(result) == 1
        assert result[0]["title"] == "Test 1"

    def test_invalid_json(self, tmp_path):
        """Test handling of invalid JSON."""
        suggestions_file = tmp_path / "suggestions.json"
        suggestions_file.write_text("not valid json {")

        result = parse_suggestions(suggestions_file)
        assert result == []

    def test_missing_file(self, tmp_path):
        """Test handling of missing file."""
        suggestions_file = tmp_path / "nonexistent.json"

        result = parse_suggestions(suggestions_file)
        assert result == []
