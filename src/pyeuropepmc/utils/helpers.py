import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union


def deep_merge_dicts(original: Dict[Any, Any], new: Dict[Any, Any]) -> Dict[Any, Any]:
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
        raise TypeError("Both arguments must be dictionaries")

    # Create a copy to avoid modifying the original
    result = original.copy()

    for key, value in new.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def save_to_json_with_merge(data: Any, output_file: Union[str, Path]) -> bool:
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


def save_to_json(data: Any, output_file: Union[str, Path]) -> bool:
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

        with output_file.open("w", encoding="utf-8") as outfile:
            json.dump(data, outfile, indent=2, ensure_ascii=False)
        logging.info(f"Data saved to '{output_file}'")
        return True
    except IOError as e:
        logging.error(f"IOError saving data to '{output_file}': {e}")
    except TypeError as e:
        logging.error(f"TypeError: Could not serialize data to JSON for '{output_file}': {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while saving data to '{output_file}': {e}")
    return False


def load_json(file_path: Union[str, Path]) -> Optional[Any]:
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
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error(f"Error: JSON file not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error: Invalid JSON format in {file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error loading {file_path}: {e}")
        return None


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
