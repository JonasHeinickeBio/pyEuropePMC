import pytest
from pyeuropepmc.search import SearchClient

SAMPLE_RESULTS = [
    {"id": "1", "title": "First Article", "author": "Alice"},
    {"id": "2", "title": "Second Article", "author": "Bob"},
]

@pytest.fixture
def client():
    return SearchClient()

def test_export_dataframe(client):
    df = client.export_results(SAMPLE_RESULTS, format="dataframe")
    assert df.shape[0] == 2
    assert "title" in df.columns

def test_export_csv(client, tmp_path):
    csv_str = client.export_results(SAMPLE_RESULTS, format="csv")
    assert "First Article" in csv_str
    file_path = tmp_path / "results.csv"
    client.export_results(SAMPLE_RESULTS, format="csv", path=str(file_path))
    assert file_path.read_text().startswith("id,title,author")

def test_export_excel(client, tmp_path):
    excel_bytes = client.export_results(SAMPLE_RESULTS, format="excel")
    assert isinstance(excel_bytes, bytes)
    file_path = tmp_path / "results.xlsx"
    client.export_results(SAMPLE_RESULTS, format="excel", path=str(file_path))
    assert file_path.exists()
    assert file_path.stat().st_size > 0

def test_export_json(client, tmp_path):
    json_str = client.export_results(SAMPLE_RESULTS, format="json")
    assert "First Article" in json_str
    file_path = tmp_path / "results.json"
    client.export_results(SAMPLE_RESULTS, format="json", path=str(file_path))
    assert file_path.read_text().startswith("[")

def test_export_markdown(client):
    md = client.export_results(SAMPLE_RESULTS, format="markdown")
    assert "|   id " in md
    assert "First Article" in md
