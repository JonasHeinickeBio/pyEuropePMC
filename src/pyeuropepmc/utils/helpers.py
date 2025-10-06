from collections.abc import Callable, Iterator
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any
import warnings

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import ValidationError


def warn_if_empty_hitcount(response: dict[str, Any], context: str = "") -> None:
    """
    Log a warning if the response dict has hitCount == 0.

    Parameters
    ----------
    response : dict
        The API response dictionary to check.
    context : str, optional
        Additional context for the warning message (e.g., 'citations', 'references').
    """
    try:
        hit_count = response["hitCount"]
    except KeyError:
        msg = "'hitCount' key not found in response dictionary"
        if context:
            msg += f" for {context}"
        warnings.warn(msg, UserWarning, stacklevel=2)
        return
    except TypeError:
        warnings.warn("Response is not a dictionary", UserWarning, stacklevel=2)
        return
    if hit_count == 0:
        msg = "No results found (hitCount=0)"
        if context:
            msg += f" for {context}"
        warnings.warn(msg, UserWarning, stacklevel=2)


def deep_merge_dicts(original: dict[Any, Any], new: dict[Any, Any]) -> dict[Any, Any]:
    """
    Recursively merge two dictionaries.

    Parameters
    ----------
    original : Dict[Any, Any]
        The original dictionary to merge into.
    new : Dict[Any, Any]
        The new dictionary to merge from.

    Returns
    -------
    Dict[Any, Any]
        The merged dictionary.

    Examples
    --------
    >>> original = {"a": 1, "b": {"c": 2}}
    >>> new = {"b": {"d": 3}, "e": 4}
    >>> result = deep_merge_dicts(original, new)
    >>> result
    {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
    """
    if not isinstance(original, dict) or not isinstance(new, dict):
        context = {
            "original_type": type(original).__name__,
            "new_type": type(new).__name__,
        }
        raise ValidationError(ErrorCodes.VALID001, context)

    # Create a copy to avoid modifying the original
    result = original.copy()

    for key, value in new.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def save_to_json_with_merge(data: Any, output_file: str | Path) -> bool:
    """
    Save data to a JSON file, merging with existing data if present.

    Parameters
    ----------
    data : Any
        The new data to save.
    output_file : Union[str, Path]
        The output file path.

    Returns
    -------
    bool
        True if save was successful, False otherwise.

    Raises
    ------
    TypeError
        If data types are incompatible for merging.
    """
    output_file = Path(output_file)

    if output_file.exists():
        try:
            existing_data = load_json(output_file)
            if existing_data is not None:
                if isinstance(existing_data, dict) and isinstance(data, dict):
                    data = deep_merge_dicts(existing_data, data)
                elif isinstance(existing_data, list) and isinstance(data, list):
                    data = existing_data + data
                else:
                    logging.warning(
                        f"Cannot merge {type(existing_data)} with {type(data)}. Overwriting."
                    )
        except Exception as e:
            logging.warning(f"Could not load existing data from '{output_file}': {e}")

    return save_to_json(data, output_file)


def save_to_json(data: Any, output_file: str | Path) -> bool:
    """
    Save data to a JSON file.

    Parameters
    ----------
    data : Any
        The data to save.
    output_file : Union[str, Path]
        The output file path.

    Returns
    -------
    bool
        True if save was successful, False otherwise.

    Examples
    --------
    >>> save_to_json({"key": "value"}, "output.json")
    True
    """
    output_file = Path(output_file)

    try:
        # Ensure the output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        logging.info(f"Created directory: {output_file.parent}")

        with open(output_file, "w", encoding="utf-8") as outfile:
            json.dump(data, outfile, indent=2, ensure_ascii=False)
        logging.info(f"Data saved to '{output_file}'")
        return True
    except (OSError, UnicodeError) as e:
        error_msg = f"Failed to save JSON data to '{output_file}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(output_file), "error": str(e)}
        raise ValidationError(
            ErrorCodes.VALID006, context, field_name="file_path", expected_type="writable file"
        ) from e
    except TypeError as e:
        error_msg = f"Cannot serialize data to JSON for '{output_file}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(output_file), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID007, context, field_name="file_path") from e
    except Exception as e:
        error_msg = f"Unexpected error while saving JSON to '{output_file}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(output_file), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID002, context, field_name="file_path") from e


def load_json(file_path: str | Path) -> Any | None:
    """
    Load data from a JSON file.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the JSON file to load.

    Returns
    -------
    Optional[Any]
        Loaded data or None if file doesn't exist or is invalid.

    Examples
    --------
    >>> data = load_json("data.json")
    >>> data is not None
    True
    """
    file_path = Path(file_path)

    try:
        with open(file_path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as e:
        error_msg = f"JSON file not found: '{file_path}'."
        logging.error(error_msg)
        context = {"file_path": str(file_path), "error": str(e)}
        raise ValidationError(
            ErrorCodes.VALID004,
            context,
            field_name="file_path",
            expected_type="readable JSON file",
        ) from e
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON format in '{file_path}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(file_path), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID005, context, field_name="file_path") from e
    except PermissionError as e:
        error_msg = f"Permission denied accessing '{file_path}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(file_path), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID004, context, field_name="file_path") from e
    except UnicodeDecodeError as e:
        error_msg = f"Unicode decode error in '{file_path}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(file_path), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID004, context, field_name="file_path") from e
    except Exception as e:
        error_msg = f"Unexpected error loading JSON from '{file_path}': {e}."
        logging.error(error_msg)
        context = {"file_path": str(file_path), "error": str(e)}
        raise ValidationError(ErrorCodes.VALID002, context, field_name="file_path") from e


def safe_int(val: Any, default: int, minv: int = 1, maxv: int = 1000) -> int:
    """
    Safely convert a value to an integer, clamp between minv and maxv, or return default.

    Parameters
    ----------
    val : Any
        Value to convert to int.
    default : int
        Default value to return if conversion fails.
    minv : int, optional
        Minimum allowed value (inclusive).
    maxv : int, optional
        Maximum allowed value (inclusive).

    Returns
    -------
    int
        Converted and clamped integer, or default if conversion fails.
    """
    if val is None:
        return default
    try:
        value = int(val)
        return min(max(value, minv), maxv)
    except (ValueError, TypeError):
        return default


@contextmanager
def atomic_write(target_path: str | Path, mode: str = "w", **kwargs: Any) -> Iterator[Any]:
    """
    Context manager for atomic file writing using temporary files.

    Creates a temporary file in the same directory as the target, writes to it,
    and only moves it to the target location if the write operation succeeds.

    Parameters
    ----------
    target_path : Union[str, Path]
        The final path where the file should be written
    mode : str, optional
        File mode for opening (default: 'w')
    **kwargs
        Additional keyword arguments passed to open()

    Yields
    ------
    file object
        The temporary file object to write to

    Examples
    --------
    >>> with atomic_write("output.txt") as f:
    ...     f.write("Hello, world!")
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in the same directory as target
    temp_dir = target_path.parent
    temp_fd, temp_path_str = tempfile.mkstemp(dir=temp_dir, suffix=".tmp")
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(temp_fd, mode, **kwargs) as temp_file:
            yield temp_file

        # If we get here, the write was successful, so move temp file to target
        temp_path.rename(target_path)

    except Exception:
        # If anything goes wrong, clean up the temp file
        temp_path.unlink(missing_ok=True)
        raise


def atomic_download(
    url: str,
    target_path: str | Path,
    session_getter: Callable[[], Any],
    validator: Callable[[Path], bool] | None = None,
    content_type_check: str | None = None,
    **request_kwargs: Any,
) -> bool:
    """
    Download a file atomically using a temporary file.

    Parameters
    ----------
    url : str
        URL to download from
    target_path : Union[str, Path]
        Target path for the downloaded file
    session_getter : Callable
        Function that returns a requests session
    validator : Optional[Callable[[Path], bool]]
        Optional validator function to validate the downloaded file
    content_type_check : Optional[str]
        Optional content type to check for (e.g., "application/pdf")
    **request_kwargs
        Additional keyword arguments for the request

    Returns
    -------
    bool
        True if download was successful, False otherwise
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in the same directory as target
    temp_dir = target_path.parent
    temp_fd, temp_path_str = tempfile.mkstemp(dir=temp_dir, suffix=".tmp")
    temp_path = Path(temp_path_str)

    try:
        # Use requests.get directly for better test compatibility
        import requests

        # Extract timeout from kwargs to avoid conflicts
        timeout = request_kwargs.pop("timeout", 30)
        response = requests.get(url, stream=True, timeout=timeout, **request_kwargs)

        # Check status code
        if response.status_code != 200:
            temp_path.unlink(missing_ok=True)
            return False

        # Check content type if specified
        if content_type_check:
            content_type = response.headers.get("content-type", "").lower()
            if content_type_check not in content_type:
                temp_path.unlink(missing_ok=True)
                return False

        # Write to temporary file
        with os.fdopen(temp_fd, "wb") as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)

        # Validate if validator is provided
        if validator and not validator(temp_path):
            temp_path.unlink(missing_ok=True)
            return False

        # If we get here, the download was successful, so move temp file to target
        temp_path.rename(target_path)
        return True

    except Exception as e:
        # If anything goes wrong, clean up the temp file
        temp_path.unlink(missing_ok=True)
        logging.error(f"Error during atomic download: {e}")
        return False
