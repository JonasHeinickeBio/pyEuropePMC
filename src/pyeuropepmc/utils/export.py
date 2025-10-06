import json
import logging
import tempfile
from typing import Any

import pandas as pd


def to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert parsed results to a pandas DataFrame."""
    try:
        df = pd.DataFrame(results)
        return df
    except Exception as e:
        logging.error(f"Failed to convert results to DataFrame: {e}")
        raise


def to_csv(results: list[dict[str, Any]], path: str | None = None) -> str:
    """Export results to CSV. If path is given, write to file, else return as string."""
    try:
        df = to_dataframe(results)
        csv_str: str = df.to_csv(index=False)
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(csv_str)
        return csv_str
    except Exception as e:
        logging.error(f"Failed to export results to CSV: {e}")
        raise


def to_excel(results: list[dict[str, Any]], path: str | None = None) -> bytes:
    """Export results to Excel. If path is given, write to file, else return bytes."""
    try:
        df = to_dataframe(results)
        if path is not None:
            with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False)
            with open(path, "rb") as f:
                excel_bytes = f.read()
            return excel_bytes
        else:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                with pd.ExcelWriter(tmp_path, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False)
                with open(tmp_path, "rb") as f:
                    excel_bytes = f.read()
            finally:
                import os

                os.remove(tmp_path)
            return excel_bytes
    except Exception as e:
        logging.error(f"Failed to export results to Excel: {e}")
        raise


def to_json(results: list[dict[str, Any]], path: str | None = None, pretty: bool = False) -> str:
    """Export results to JSON. If path is given, write to file, else return as string."""
    try:
        json_str: str = (
            json.dumps(results, indent=2, ensure_ascii=False)
            if pretty
            else json.dumps(results, ensure_ascii=False)
        )
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_str)
        return json_str
    except Exception as e:
        logging.error(f"Failed to export results to JSON: {e}")
        raise


def to_markdown_table(results: list[dict[str, Any]]) -> str:
    """Export results to a Markdown table string."""
    try:
        if not results:
            return ""
        df = to_dataframe(results)
        markdown: str = df.to_markdown(index=False)
        return markdown
    except Exception as e:
        logging.error(f"Failed to export results to Markdown table: {e}")
        return ""


def filter_fields(results: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    """Return results with only specified fields."""
    try:
        filtered = [{k: v for k, v in r.items() if k in fields} for r in results]
        return filtered
    except Exception as e:
        logging.error(f"Failed to filter fields: {e}")
        raise


def map_fields(results: list[dict[str, Any]], field_map: dict[str, str]) -> list[dict[str, Any]]:
    """Return results with fields renamed according to field_map."""
    try:
        mapped = [{field_map.get(k, k): v for k, v in r.items()} for r in results]
        return mapped
    except Exception as e:
        logging.error(f"Failed to map fields: {e}")
        raise
