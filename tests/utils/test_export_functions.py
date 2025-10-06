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
