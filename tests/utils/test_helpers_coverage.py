"""
Additional unit tests for utils.helpers to improve test coverage.

This module focuses on testing edge cases, error paths, and less common scenarios
to achieve higher test coverage for the helpers module.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from pyeuropepmc.utils.helpers import save_to_json_with_merge, save_to_json, load_json
from pyeuropepmc.exceptions import ValidationError


pytestmark = pytest.mark.unit


class TestHelpersCoverage:
    """Additional test coverage for utils.helpers edge cases."""

    def test_save_to_json_with_merge_file_not_exists(self):
        """Test save_to_json_with_merge when file doesn't exist."""
        data = {"new_data": "test"}

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "new_file.json"
            save_to_json_with_merge(data, file_path)

            # Verify file was created with the data
            assert file_path.exists()
            with open(file_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            assert saved_data == data

    def test_save_to_json_with_merge_existing_file(self):
        """Test save_to_json_with_merge with existing file."""
        existing_data = {"old_key": "old_value"}
        new_data = {"new_key": "new_value"}

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "existing_file.json"

            # Create existing file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f)

            # Merge new data
            save_to_json_with_merge(new_data, file_path)

            # Verify data was merged
            with open(file_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            assert "old_key" in saved_data
            assert "new_key" in saved_data
            assert saved_data["old_key"] == "old_value"
            assert saved_data["new_key"] == "new_value"

    def test_save_to_json_with_io_error(self, tmp_path):
        """Test save_to_json with IO error."""
        data = {"test": "data"}
        test_file = tmp_path / "test.json"

        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with pytest.raises(ValidationError) as exc_info:
                save_to_json(data, test_file)

            error_message = str(exc_info.value)
            assert "Failed to save JSON file" in error_message

    def test_save_to_json_with_json_encoding_error(self, tmp_path):
        """Test save_to_json with JSON encoding error."""

        # Create data that can't be JSON serialized
        class NonSerializable:
            pass

        data = {"test": NonSerializable()}
        test_file = tmp_path / "test.json"

        with pytest.raises(ValidationError) as exc_info:
            save_to_json(data, test_file)

        error_message = str(exc_info.value)
        assert "Failed to serialize data to JSON" in error_message

    def test_save_to_json_with_unicode_encoding_error(self, tmp_path):
        """Test save_to_json with Unicode encoding error."""
        data = {"test": "data"}
        test_file = tmp_path / "test.json"

        with patch(
            "builtins.open", side_effect=UnicodeEncodeError("utf-8", "test", 0, 1, "error")
        ):
            with pytest.raises(ValidationError) as exc_info:
                save_to_json(data, test_file)

            error_message = str(exc_info.value)
            assert "Failed to save JSON file" in error_message

    def test_load_json_file_not_found(self):
        """Test load_json with file not found."""
        with pytest.raises(ValidationError) as exc_info:
            load_json("nonexistent_file.json")

        error_message = str(exc_info.value)
        assert "JSON file not found" in error_message

    def test_load_json_invalid_json(self):
        """Test load_json with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            temp_file.write("invalid json content {")
            temp_path = Path(temp_file.name)

        try:
            with pytest.raises(ValidationError) as exc_info:
                load_json(temp_path)

            error_message = str(exc_info.value)
            assert "Failed to parse JSON file" in error_message
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_json_permission_error(self, tmp_path):
        """Test load_json with permission error."""
        test_file = tmp_path / "test.json"

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(ValidationError) as exc_info:
                load_json(test_file)

            error_message = str(exc_info.value)
            assert "Failed to read JSON file" in error_message

    def test_load_json_unicode_decode_error(self, tmp_path):
        """Test load_json with Unicode decode error."""
        test_file = tmp_path / "test.json"

        with patch(
            "builtins.open", side_effect=UnicodeDecodeError("utf-8", b"test", 0, 1, "error")
        ):
            with pytest.raises(ValidationError) as exc_info:
                load_json(test_file)

            error_message = str(exc_info.value)
            assert "Failed to read JSON file" in error_message

    def test_load_json_valid_file(self):
        """Test load_json with valid JSON file."""
        test_data = {"test_key": "test_value", "number": 42}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            json.dump(test_data, temp_file)
            temp_path = Path(temp_file.name)

        try:
            loaded_data = load_json(temp_path)
            assert loaded_data == test_data
        finally:
            temp_path.unlink(missing_ok=True)

    def test_save_to_json_valid_data(self):
        """Test save_to_json with valid data."""
        test_data = {"test_key": "test_value", "list": [1, 2, 3]}

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_save.json"
            save_to_json(test_data, file_path)

            # Verify file was created correctly
            assert file_path.exists()
            with open(file_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            assert saved_data == test_data

    def test_save_to_json_with_merge_invalid_existing_json(self):
        """Test save_to_json_with_merge with invalid existing JSON."""
        new_data = {"new_key": "new_value"}

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid.json"

            # Create file with invalid JSON
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("invalid json {")

            # Should handle invalid JSON gracefully and overwrite
            save_to_json_with_merge(new_data, file_path)

            # Verify new data was saved
            with open(file_path, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            assert saved_data == new_data

    def test_save_to_json_with_merge_permission_error_on_read(self):
        """Test save_to_json_with_merge with permission error when reading existing file."""
        new_data = {"new_key": "new_value"}

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.json"

            # Create existing file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"old": "data"}, f)

            # Mock permission error on read but allow write
            def mock_open_func(*args, **kwargs):
                if "r" in args[1]:
                    raise PermissionError("Read access denied")
                else:
                    return mock_open()(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open_func):
                # Should handle read error gracefully and just save new data
                save_to_json_with_merge(new_data, file_path)

    def test_helpers_error_context(self, tmp_path):
        """Test that helper functions provide proper error context."""
        # Test save_to_json error context
        test_file = tmp_path / "test.json"

        with patch("builtins.open", side_effect=IOError("IO Error")):
            with pytest.raises(ValidationError) as exc_info:
                save_to_json({"test": "data"}, test_file)

            assert exc_info.value.field_name == "file_path"
            assert exc_info.value.expected_type == "writable file"
            assert "field_name" in exc_info.value.details

        # Test load_json error context
        nonexistent_file = tmp_path / "nonexistent.json"
        with pytest.raises(ValidationError) as exc_info:
            load_json(nonexistent_file)

        assert exc_info.value.field_name == "file_path"
        assert exc_info.value.expected_type == "readable JSON file"
        assert "field_name" in exc_info.value.details

    def test_warn_if_empty_hitcount_zero(self):
        """Test warning is issued when hitCount == 0."""
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        import warnings
        response = {"hitCount": 0}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_if_empty_hitcount(response)
            assert any("No results found" in str(warn.message) for warn in w)

    def test_warn_if_empty_hitcount_zero_with_context(self):
        """Test warning includes context when hitCount == 0 and context is provided."""
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        import warnings
        response = {"hitCount": 0}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_if_empty_hitcount(response, context="citations")
            assert any("for citations" in str(warn.message) for warn in w)

    def test_warn_if_empty_hitcount_missing_key(self):
        """Test warning is issued when 'hitCount' key is missing."""
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        import warnings
        response = {"other": 1}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_if_empty_hitcount(response)
            assert any("'hitCount' key not found" in str(warn.message) for warn in w)

    def test_warn_if_empty_hitcount_missing_key_with_context(self):
        """Test warning includes context when 'hitCount' key is missing and context is provided."""
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        import warnings
        response = {"other": 1}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_if_empty_hitcount(response, context="references")
            assert any("for references" in str(warn.message) for warn in w)

    def test_warn_if_empty_hitcount_type_error(self):
        """Test warning is issued when response is not a dict."""
        from pyeuropepmc.utils.helpers import warn_if_empty_hitcount
        import warnings
        response = None
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_if_empty_hitcount(response)
            assert any("Response is not a dictionary" in str(warn.message) for warn in w)
