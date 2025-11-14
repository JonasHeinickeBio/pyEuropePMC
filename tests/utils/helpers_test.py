"""
Test module for utility helper functions.

This module contains comprehensive tests for all helper functions in
src/pyeuropepmc/utils/helpers.py, covering normal operation, edge cases,
and error conditions.
"""

import json
from pathlib import Path
import platform
import stat
import subprocess

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import ValidationError
from pyeuropepmc.utils.helpers import (
    deep_merge_dicts,
    load_json,
    safe_int,
    save_to_json,
    save_to_json_with_merge,
)


def is_writable(path):
    """Test if a directory is writable by attempting to create a test file."""
    try:
        testfile = path / ".write_test"
        with open(testfile, "w") as f:
            f.write("test")
        testfile.unlink()
        return True
    except (OSError, PermissionError):
        return False


def make_readonly(path):
    """Make a directory read-only in a cross-platform way."""
    if platform.system() == "Windows":
        # On Windows, use attrib command or file attributes
        try:
            # Method 1: Use attrib command
            subprocess.run(["attrib", "+R", str(path)], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Method 2: Use stat flags (may not work on all Windows versions)
            try:
                current_mode = path.stat().st_mode
                path.chmod(current_mode & ~stat.S_IWRITE)
                return True
            except Exception:
                return False
    else:
        # Unix-like systems
        try:
            path.chmod(0o444)
            return True
        except Exception:
            return False


def restore_permissions(path):
    """Restore write permissions in a cross-platform way."""
    if platform.system() == "Windows":
        try:
            # Method 1: Use attrib command
            subprocess.run(["attrib", "-R", str(path)], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Method 2: Use stat flags
            try:
                current_mode = path.stat().st_mode
                path.chmod(current_mode | stat.S_IWRITE)
            except Exception:
                pass
    else:
        # Unix-like systems
        try:
            path.chmod(0o755)
        except Exception:
            pass


class TestDeepMergeDicts:
    """Test cases for deep_merge_dicts function."""

    def test_basic_merge(self):
        """Test basic dictionary merging."""
        original = {"a": 1, "b": 2}
        new = {"c": 3, "d": 4}
        result = deep_merge_dicts(original, new)
        expected = {"a": 1, "b": 2, "c": 3, "d": 4}
        assert result == expected

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        original = {"a": 1, "b": {"c": 2, "d": 3}}
        new = {"b": {"e": 4, "f": 5}, "g": 6}
        result = deep_merge_dicts(original, new)
        expected = {"a": 1, "b": {"c": 2, "d": 3, "e": 4, "f": 5}, "g": 6}
        assert result == expected

    def test_overwrite_values(self):
        """Test that non-dict values are overwritten."""
        original = {"a": 1, "b": {"c": 2}}
        new = {"a": 100, "b": {"c": 200}}
        result = deep_merge_dicts(original, new)
        expected = {"a": 100, "b": {"c": 200}}
        assert result == expected

    def test_deep_nested_merge(self):
        """Test deeply nested dictionary merging."""
        original = {"level1": {"level2": {"level3": {"a": 1}}}}
        new = {"level1": {"level2": {"level3": {"b": 2}, "other": 3}}}
        result = deep_merge_dicts(original, new)
        expected = {"level1": {"level2": {"level3": {"a": 1, "b": 2}, "other": 3}}}
        assert result == expected

    def test_original_not_modified(self):
        """Test that the original dictionary is not modified."""
        original = {"a": 1, "b": {"c": 2}}
        original_copy = {"a": 1, "b": {"c": 2}}
        new = {"b": {"d": 3}, "e": 4}

        result = deep_merge_dicts(original, new)

        # Original should remain unchanged
        assert original == original_copy
        # Result should contain merged data
        assert result == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    def test_empty_dictionaries(self):
        """Test merging with empty dictionaries."""
        assert deep_merge_dicts({}, {}) == {}
        assert deep_merge_dicts({"a": 1}, {}) == {"a": 1}
        assert deep_merge_dicts({}, {"a": 1}) == {"a": 1}

    def test_non_dict_values_overwrite(self):
        """Test that non-dict values replace dict values and vice versa."""
        original = {"a": {"b": 1}}
        new = {"a": "string"}
        result = deep_merge_dicts(original, new)
        assert result == {"a": "string"}

        original = {"a": "string"}
        new = {"a": {"b": 1}}
        result = deep_merge_dicts(original, new)
        assert result == {"a": {"b": 1}}

    def test_type_error_non_dict_original(self):
        """Test ValidationError when original is not a dict."""
        with pytest.raises(ValidationError) as exc_info:
            deep_merge_dicts("not a dict", {"a": 1})  # type: ignore

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID001

        # Check that the error message indicates dictionary validation failure
        error_str = str(exc_info.value)
        assert "[VALID001]" in error_str
        assert "Both arguments must be dictionaries" in error_str

    def test_type_error_non_dict_new(self):
        """Test ValidationError when new is not a dict."""
        with pytest.raises(ValidationError) as exc_info:
            deep_merge_dicts({"a": 1}, "not a dict")  # type: ignore

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID001

        # Check that the error message indicates dictionary validation failure
        error_str = str(exc_info.value)
        assert "[VALID001]" in error_str
        assert "Both arguments must be dictionaries" in error_str

    def test_type_error_both_non_dict(self):
        """Test ValidationError when both arguments are not dicts."""
        with pytest.raises(ValidationError) as exc_info:
            deep_merge_dicts("not a dict", 42)  # type: ignore

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID001

        # Check that the error message indicates dictionary validation failure
        error_str = str(exc_info.value)
        assert "[VALID001]" in error_str
        assert "Both arguments must be dictionaries" in error_str

    def test_complex_types(self):
        """Test merging with complex data types."""
        original = {"list": [1, 2], "tuple": (1, 2), "set": {1, 2}}
        new = {"list": [3, 4], "dict": {"nested": True}, "none": None}
        result = deep_merge_dicts(original, new)
        expected = {
            "list": [3, 4],  # Overwritten
            "tuple": (1, 2),  # Preserved
            "set": {1, 2},  # Preserved
            "dict": {"nested": True},  # Added
            "none": None,  # Added
        }
        assert result == expected


class TestSafeInt:
    """Test cases for safe_int function."""

    def test_valid_integers(self):
        """Test conversion of valid integers."""
        assert safe_int(5, 0) == 5
        assert safe_int("10", 0) == 10
        assert safe_int(15.7, 0) == 15

    def test_clamping_to_min(self):
        """Test clamping values to minimum."""
        assert safe_int(0, 10, minv=5, maxv=20) == 5
        assert safe_int(-10, 10, minv=1, maxv=100) == 1

    def test_clamping_to_max(self):
        """Test clamping values to maximum."""
        assert safe_int(1500, 10, minv=1, maxv=1000) == 1000
        assert safe_int(50, 10, minv=1, maxv=20) == 20

    def test_within_range(self):
        """Test values within the allowed range."""
        assert safe_int(50, 10, minv=1, maxv=100) == 50
        assert safe_int("25", 10, minv=10, maxv=30) == 25

    def test_invalid_values_return_default(self):
        """Test that invalid values return the default."""
        assert safe_int("not a number", 42) == 42
        assert safe_int([], 42) == 42
        assert safe_int({}, 42) == 42
        assert safe_int(object(), 42) == 42

    def test_none_returns_default(self):
        """Test that None returns the default value."""
        assert safe_int(None, 42) == 42

    def test_boolean_conversion(self):
        """Test boolean to int conversion."""
        assert safe_int(True, 0) == 1
        assert safe_int(False, 10) == 1  # Clamped to minv=1

    def test_string_numbers(self):
        """Test string representations of numbers."""
        assert safe_int("123", 0) == 123
        assert safe_int("0", 10, minv=5, maxv=20) == 5
        assert safe_int("2000", 10, minv=1, maxv=1000) == 1000

    def test_edge_cases(self):
        """Test edge cases for safe_int."""
        # Empty string
        assert safe_int("", 42) == 42
        # Whitespace
        assert safe_int("  ", 42) == 42
        # Float strings - int() doesn't parse float strings, so they should return default
        assert safe_int("123.45", 0) == 0
        # Scientific notation - int() can parse this
        assert safe_int("100", 0) == 100

    def test_default_parameters(self):
        """Test default minv and maxv parameters."""
        assert safe_int(0, 10) == 1  # minv=1 by default
        assert safe_int(2000, 10) == 1000  # maxv=1000 by default
        assert safe_int(500, 10) == 500  # Within default range


class TestSaveToJson:
    """Test cases for save_to_json function."""

    def test_save_simple_data(self, tmp_path):
        """Test saving simple data to JSON file."""
        data = {"key": "value", "number": 42}
        file_path = tmp_path / "test.json"

        result = save_to_json(data, file_path)
        assert result is True
        assert file_path.exists()

        with file_path.open("r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_save_with_string_path(self, tmp_path):
        """Test saving with string path."""
        data = {"test": True}
        file_path = str(tmp_path / "test_string.json")

        result = save_to_json(data, file_path)
        assert result is True
        assert Path(file_path).exists()

    def test_save_creates_directories(self, tmp_path):
        """Test that save_to_json creates parent directories."""
        data = {"nested": "directory"}
        file_path = tmp_path / "deep" / "nested" / "path" / "test.json"

        result = save_to_json(data, file_path)
        assert result is True
        assert file_path.exists()
        assert file_path.parent.exists()

    def test_save_complex_data(self, tmp_path):
        """Test saving complex nested data."""
        data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"deep": {"value": "found"}},
        }
        file_path = tmp_path / "complex.json"

        result = save_to_json(data, file_path)
        assert result is True

        with file_path.open("r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_save_unicode_data(self, tmp_path):
        """Test saving Unicode data."""
        data = {"unicode": "测试", "emoji": "🎉", "special": "ñáéíóú"}
        file_path = tmp_path / "unicode.json"

        result = save_to_json(data, file_path)
        assert result is True

        with file_path.open("r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_save_overwrites_existing(self, tmp_path):
        """Test that save_to_json overwrites existing files."""
        file_path = tmp_path / "overwrite.json"

        # Save initial data
        initial_data = {"version": 1}
        result1 = save_to_json(initial_data, file_path)
        assert result1 is True

        # Save new data
        new_data = {"version": 2}
        result2 = save_to_json(new_data, file_path)
        assert result2 is True

        # Verify new data is saved
        with file_path.open("r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data == new_data

    def test_save_non_serializable_data(self, tmp_path):
        """Test saving non-serializable data raises ValidationError."""
        data = {"function": lambda x: x}  # Functions are not JSON serializable
        file_path = tmp_path / "non_serializable.json"

        with pytest.raises(ValidationError) as exc_info:
            save_to_json(data, file_path)

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID007

        # Check that the error message indicates JSON serialization failure
        error_str = str(exc_info.value)
        assert "[VALID007]" in error_str
        assert "Failed to serialize data to JSON" in error_str

    def test_save_to_readonly_location(self, tmp_path):
        """Test saving to a read-only location with cross-platform compatibility."""
        # Create a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        # Try to make directory read-only using cross-platform method
        readonly_success = make_readonly(readonly_dir)

        # If we couldn't make it read-only, skip the test
        if not readonly_success or is_writable(readonly_dir):
            pytest.skip(
                f"Cannot make directory read-only on {platform.system()}. "
                f"This test requires filesystem permission control."
            )

        data = {"test": "data"}
        file_path = readonly_dir / "test.json"

        try:
            with pytest.raises(ValidationError) as exc_info:
                save_to_json(data, file_path)

            # Check that the exception has the correct error code for file save failure
            assert exc_info.value.error_code == ErrorCodes.VALID006

            # Check that the error message indicates save failure
            error_str = str(exc_info.value)
            assert "[VALID006]" in error_str
            assert "Failed to save JSON file" in error_str
        finally:
            # Always restore permissions for cleanup
            restore_permissions(readonly_dir)

    def test_save_to_readonly_location_mock(self, tmp_path, monkeypatch):
        """Alternative test using mocking to simulate permission errors consistently."""
        import builtins
        from pathlib import Path

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        original_open = builtins.open
        original_mkdir = Path.mkdir

        def mock_open(*args, **kwargs):
            # Check if we're trying to open a file in our test directory
            if len(args) > 0 and str(readonly_dir) in str(args[0]):
                raise PermissionError("Permission denied")
            return original_open(*args, **kwargs)

        def mock_mkdir(self, mode=0o777, parents=False, exist_ok=False):
            # Check if we're trying to create a directory in our test path
            if str(readonly_dir) in str(self):
                raise PermissionError("Permission denied")
            return original_mkdir(self, mode, parents, exist_ok)

        # Mock both open and mkdir to simulate permission errors
        monkeypatch.setattr(builtins, "open", mock_open)
        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        data = {"test": "data"}
        file_path = readonly_dir / "test.json"

        with pytest.raises(ValidationError) as exc_info:
            save_to_json(data, file_path)

        # Check that the exception has the correct error code for file save failure
        assert exc_info.value.error_code == ErrorCodes.VALID006

        # Check that the error message indicates save failure
        error_str = str(exc_info.value)
        assert "[VALID006]" in error_str
        assert "Failed to save JSON file" in error_str


class TestLoadJson:
    """Test cases for load_json function."""

    def test_load_existing_file(self, tmp_path):
        """Test loading data from an existing JSON file."""
        data = {"key": "value", "number": 42}
        file_path = tmp_path / "test.json"

        # Create test file
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded_data = load_json(file_path)
        assert loaded_data == data

    def test_load_with_string_path(self, tmp_path):
        """Test loading with string path."""
        data = {"test": True}
        file_path = tmp_path / "test_string.json"

        # Create test file
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded_data = load_json(str(file_path))
        assert loaded_data == data

    def test_load_nonexistent_file(self, tmp_path):
        """Test loading from a non-existent file raises ValidationError."""
        file_path = tmp_path / "nonexistent.json"
        with pytest.raises(ValidationError) as exc_info:
            load_json(file_path)

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID004

        # Check that the error message indicates file not found
        error_str = str(exc_info.value)
        assert "[VALID004]" in error_str
        assert "JSON file not found" in error_str

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises ValidationError."""
        file_path = tmp_path / "invalid.json"

        # Create file with invalid JSON
        with file_path.open("w", encoding="utf-8") as f:
            f.write("{ invalid json content")

        with pytest.raises(ValidationError) as exc_info:
            load_json(file_path)

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID005

        # Check that the error message indicates JSON parse failure
        error_str = str(exc_info.value)
        assert "[VALID005]" in error_str
        assert "Failed to parse JSON file" in error_str

    def test_load_empty_file(self, tmp_path):
        """Test loading empty file raises ValidationError."""
        file_path = tmp_path / "empty.json"
        file_path.touch()  # Create empty file

        with pytest.raises(ValidationError) as exc_info:
            load_json(file_path)

        # Check that the exception has the correct error code
        assert exc_info.value.error_code == ErrorCodes.VALID005

        # Check that the error message indicates JSON parse failure
        error_str = str(exc_info.value)
        assert "[VALID005]" in error_str
        assert "Failed to parse JSON file" in error_str

    def test_load_complex_data(self, tmp_path):
        """Test loading complex nested data."""
        data = {
            "string": "test",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"deep": {"value": "found"}},
        }
        file_path = tmp_path / "complex.json"

        # Create test file
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded_data = load_json(file_path)
        assert loaded_data == data

    def test_load_unicode_data(self, tmp_path):
        """Test loading Unicode data."""
        data = {"unicode": "测试", "emoji": "🎉", "special": "ñáéíóú"}
        file_path = tmp_path / "unicode.json"

        # Create test file
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        loaded_data = load_json(file_path)
        assert loaded_data == data


class TestSaveToJsonWithMerge:
    """Test cases for save_to_json_with_merge function."""

    def test_merge_with_nonexistent_file(self, tmp_path):
        """Test saving to a non-existent file (should create new file)."""
        data = {"key": "value"}
        file_path = tmp_path / "new.json"

        result = save_to_json_with_merge(data, file_path)
        assert result is True
        assert file_path.exists()

        loaded_data = load_json(file_path)
        assert loaded_data == data

    def test_merge_dicts(self, tmp_path):
        """Test merging dictionary data."""
        file_path = tmp_path / "merge_dicts.json"

        # Save initial data
        initial_data = {"a": 1, "b": {"c": 2}}
        save_to_json(initial_data, file_path)

        # Merge with new data
        new_data = {"b": {"d": 3}, "e": 4}
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify merged result
        loaded_data = load_json(file_path)
        expected = {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
        assert loaded_data == expected

    def test_merge_lists(self, tmp_path):
        """Test merging list data."""
        file_path = tmp_path / "merge_lists.json"

        # Save initial data
        initial_data = [1, 2, 3]
        save_to_json(initial_data, file_path)

        # Merge with new data
        new_data = [4, 5, 6]
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify merged result
        loaded_data = load_json(file_path)
        expected = [1, 2, 3, 4, 5, 6]
        assert loaded_data == expected

    def test_incompatible_types_overwrite(self, tmp_path):
        """Test that incompatible types cause overwrite with warning."""
        file_path = tmp_path / "incompatible.json"

        # Save initial data (dict)
        initial_data = {"key": "value"}
        save_to_json(initial_data, file_path)

        # Try to merge with incompatible type (string)
        new_data = "string data"
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify new data overwrote old data
        loaded_data = load_json(file_path)
        assert loaded_data == new_data

    def test_merge_with_corrupted_file(self, tmp_path):
        """Test merging when existing file is corrupted."""
        file_path = tmp_path / "corrupted.json"

        # Create corrupted JSON file
        with file_path.open("w", encoding="utf-8") as f:
            f.write("{ corrupted json")

        # Try to merge with new data
        new_data = {"key": "value"}
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify new data is saved (old corrupted data ignored)
        loaded_data = load_json(file_path)
        assert loaded_data == new_data

    def test_deep_merge_complex(self, tmp_path):
        """Test deep merging of complex nested structures."""
        file_path = tmp_path / "deep_merge.json"

        # Save initial complex data
        initial_data = {
            "users": {"alice": {"age": 30, "city": "New York"}, "bob": {"age": 25}},
            "settings": {"theme": "dark"},
        }
        save_to_json(initial_data, file_path)

        # Merge with new complex data
        new_data = {
            "users": {"alice": {"country": "USA"}, "charlie": {"age": 35, "city": "London"}},
            "settings": {"language": "en"},
            "version": "1.0",
        }
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify complex merge result
        loaded_data = load_json(file_path)
        expected = {
            "users": {
                "alice": {"age": 30, "city": "New York", "country": "USA"},
                "bob": {"age": 25},
                "charlie": {"age": 35, "city": "London"},
            },
            "settings": {"theme": "dark", "language": "en"},
            "version": "1.0",
        }
        assert loaded_data == expected

    def test_merge_with_string_path(self, tmp_path):
        """Test merging with string file path."""
        file_path = str(tmp_path / "string_path.json")

        # Save initial data
        initial_data = {"a": 1}
        save_to_json(initial_data, file_path)

        # Merge with new data
        new_data = {"b": 2}
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify merge
        loaded_data = load_json(file_path)
        assert loaded_data == {"a": 1, "b": 2}

    def test_merge_empty_structures(self, tmp_path):
        """Test merging with empty structures."""
        file_path = tmp_path / "empty_merge.json"

        # Test empty dict merge
        save_to_json({}, file_path)
        result = save_to_json_with_merge({"key": "value"}, file_path)
        assert result is True
        assert load_json(file_path) == {"key": "value"}

        # Test empty list merge
        save_to_json([], file_path)
        result = save_to_json_with_merge([1, 2, 3], file_path)
        assert result is True
        assert load_json(file_path) == [1, 2, 3]


class TestIntegration:
    """Integration tests combining multiple helper functions."""

    def test_save_load_roundtrip(self, tmp_path):
        """Test complete save/load roundtrip."""
        data = {
            "string": "test",
            "number": safe_int("42", 0),
            "nested": {"deep": {"value": safe_int("100", 0, minv=50, maxv=150)}},
        }
        file_path = tmp_path / "roundtrip.json"

        # Save data
        save_result = save_to_json(data, file_path)
        assert save_result is True

        # Load data
        loaded_data = load_json(file_path)
        assert loaded_data == data

        # Ensure loaded_data is not None before subscripting
        assert loaded_data is not None
        # Verify safe_int processed values
        assert loaded_data["number"] == 42
        assert loaded_data["nested"]["deep"]["value"] == 100

    def test_merge_workflow(self, tmp_path):
        """Test a complete merge workflow."""
        file_path = tmp_path / "workflow.json"

        # Step 1: Save initial config
        initial_config = {
            "database": {"host": "localhost", "port": safe_int("5432", 5432, minv=1, maxv=10000)},
            "features": ["auth", "logging"],
        }
        save_to_json(initial_config, file_path)

        # Step 2: Update with user settings
        user_settings = {
            "database": {"ssl": True, "timeout": safe_int("30", 10)},
            "ui": {"theme": "dark"},  # Remove features to avoid list overwriting
        }
        save_to_json_with_merge(user_settings, file_path)

        # Step 3: Verify final configuration
        final_config = load_json(file_path)
        expected = {
            "database": {"host": "localhost", "port": 5432, "ssl": True, "timeout": 30},
            "features": ["auth", "logging"],  # Preserved from initial
            "ui": {"theme": "dark"},
        }
        assert final_config == expected

    def test_error_recovery(self, tmp_path):
        """Test error recovery in complex scenarios."""
        file_path = tmp_path / "error_recovery.json"

        # Create file with valid data
        valid_data = {"status": "ok", "count": safe_int("5", 1)}
        save_to_json(valid_data, file_path)

        # Corrupt the file
        with file_path.open("w", encoding="utf-8") as f:
            f.write("{ corrupted")

        # Try to merge - should handle corruption gracefully
        new_data = {"status": "recovered", "timestamp": "2024-01-01"}
        result = save_to_json_with_merge(new_data, file_path)
        assert result is True

        # Verify recovery
        recovered_data = load_json(file_path)
        assert recovered_data == new_data
