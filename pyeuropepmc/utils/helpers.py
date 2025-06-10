from typing import Any
import os
import json
import logging

def deep_merge_dicts(original: dict, new: dict) -> dict:
    """Recursively merge two dictionaries."""
    for key, value in new.items():
        if key in original and isinstance(original[key], dict) and isinstance(value, dict):
            original[key] = deep_merge_dicts(original[key], value)
        else:
            original[key] = value
    return original


def save_to_json_with_merge(data: Any, output_file: str) -> None:
    """Save data to a JSON file, merging with existing data if present.

    Args:
        data (Any): The new data to save.
        output_file (str): The output file path.
    """
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as infile:
                existing_data = json.load(infile)
            if isinstance(existing_data, dict) and isinstance(data, dict):
                data = deep_merge_dicts(existing_data, data)
            else:
                logging.warning(f"Existing data in '{output_file}' is not a dict. Overwriting.")
        except Exception as e:
            logging.warning(f"Could not load existing data from '{output_file}': {e}")
    save_to_json(data, output_file)


def save_to_json(data: Any, output_file: str) -> None:
    """Save data to a JSON file.

    Args:
        data (Any): The new data to save.
        output_file (str): The output file path.
    """
    try:
        # Ensure the output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"Created directory: {output_dir}")

        with open(output_file, 'w') as outfile:
            json.dump(data, outfile, indent=2)
        logging.info(f"Data saved to '{output_file}'")
    except IOError as e:
        logging.error(f"IOError saving data to '{output_file}': {e}")
    except TypeError as e:
        logging.error(f"TypeError: Could not serialize data to JSON for '{output_file}': {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while saving data to '{output_file}': {e}")


def load_json(file_path: str) -> Any:
    """Load data from a JSON file.

    Args:
        file_path (str): Path to the JSON file.

    Returns:
        Optional[Dict[str, Union[List[str], Dict[str, List[str]]]]]: Parsed JSON data or None if an error occurs.
    """
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.error("Error: JSON file not found.")
        return None
    except json.JSONDecodeError:
        logging.error("Error: Invalid JSON format.")
        return None

