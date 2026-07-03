import pytest
import pandas as pd

from pyeuropepmc.utils import export

SAMPLE_RESULTS = [
    {"id": "1", "title": "First Article", "author": "Alice"},
    {"id": "2", "title": "Second Article", "author": "Bob"},
]

def test_to_dataframe():
    df = export.to_dataframe(SAMPLE_RESULTS)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "title", "author"]
    assert len(df) == 2

def test_to_csv(tmp_path):
    csv_str = export.to_csv(SAMPLE_RESULTS)
    assert "First Article" in csv_str
    file_path = tmp_path / "results.csv"
    export.to_csv(SAMPLE_RESULTS, str(file_path))
    assert file_path.read_text().startswith("id,title,author")

def test_to_excel(tmp_path):
    excel_bytes = export.to_excel(SAMPLE_RESULTS)
    assert isinstance(excel_bytes, bytes)
    file_path = tmp_path / "results.xlsx"
    export.to_excel(SAMPLE_RESULTS, str(file_path))
    assert file_path.exists()
    assert file_path.stat().st_size > 0

def test_to_json(tmp_path):
    json_str = export.to_json(SAMPLE_RESULTS)
    assert "First Article" in json_str
    file_path = tmp_path / "results.json"
    export.to_json(SAMPLE_RESULTS, str(file_path))
    assert file_path.read_text().startswith("[")

def test_to_markdown_table():
    md = export.to_markdown_table(SAMPLE_RESULTS)
    assert "|   id " in md
    assert "First Article" in md

def test_filter_fields():
    filtered = export.filter_fields(SAMPLE_RESULTS, ["id", "author"])
    assert all("title" not in r for r in filtered)
    assert all("id" in r and "author" in r for r in filtered)

def test_map_fields():
    field_map = {"id": "identifier", "author": "writer"}
    mapped = export.map_fields(SAMPLE_RESULTS, field_map)
    assert all("identifier" in r and "writer" in r for r in mapped)
    assert all("id" not in r and "author" not in r for r in mapped)


def test_to_json_pretty():
    """Test to_json with pretty=True (line 66)."""
    json_str = export.to_json(SAMPLE_RESULTS, pretty=True)
    assert "First Article" in json_str
    # Pretty-printed JSON has indentation
    assert "  " in json_str


def test_to_markdown_table_empty():
    """Test to_markdown_table with empty results (line 82)."""
    md = export.to_markdown_table([])
    assert md == ""


def test_to_dataframe_failure(monkeypatch):
    """Test to_dataframe exception handler (lines 14-16)."""
    import pandas as pd

    def failing_df(*args, **kwargs):
        raise ValueError("mock failure")

    monkeypatch.setattr(pd, "DataFrame", failing_df)
    with pytest.raises(ValueError):
        export.to_dataframe([{"a": 1}])
    # Note: caplog not used to keep test simple


def test_to_csv_failure(monkeypatch):
    """Test to_csv exception handler (lines 28-30)."""
    import pandas as pd

    def failing_df(*args, **kwargs):
        raise ValueError("mock failure")

    monkeypatch.setattr(pd, "DataFrame", failing_df)
    with pytest.raises(ValueError):
        export.to_csv([{"a": 1}])


def test_to_excel_failure(monkeypatch):
    """Test to_excel exception handler (lines 56-58)."""
    import pandas as pd

    def failing_df(*args, **kwargs):
        raise ValueError("mock failure")

    monkeypatch.setattr(pd, "DataFrame", failing_df)
    with pytest.raises(ValueError):
        export.to_excel([{"a": 1}])


def test_to_json_failure(monkeypatch):
    """Test to_json exception handler (lines 73-75)."""
    import json

    def failing_dumps(*args, **kwargs):
        raise TypeError("mock failure")

    monkeypatch.setattr(json, "dumps", failing_dumps)
    with pytest.raises(TypeError):
        export.to_json([{"a": 1}])


def test_to_markdown_table_failure(monkeypatch):
    """Test to_markdown_table exception handler returns '' (lines 86-88)."""
    import pandas as pd

    def failing_df(*args, **kwargs):
        raise ValueError("mock failure")

    monkeypatch.setattr(pd, "DataFrame", failing_df)
    md = export.to_markdown_table([{"a": 1}])
    assert md == ""


def test_filter_fields_failure():
    """Test filter_fields exception handler (lines 96-98)."""
    with pytest.raises(AttributeError):
        export.filter_fields(["not_a_dict"], ["a"])


def test_map_fields_failure():
    """Test map_fields exception handler (lines 106-108)."""
    with pytest.raises(AttributeError):
        export.map_fields(["not_a_dict"], {"a": "b"})
