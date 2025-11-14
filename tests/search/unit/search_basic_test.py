import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.clients.search import SearchClient

logging.basicConfig(level=logging.INFO)


# --- Test for simple JSON search ---
@pytest.mark.unit
def test_search_json(search_cancer_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_cancer_json
        mock_response.text = json.dumps(search_cancer_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer")
        assert result == search_cancer_json


# --- Test for XML search ---
@pytest.mark.unit
def test_search_xml(search_cancer_xml) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.text = search_cancer_xml
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", format="xml")
        assert result == search_cancer_xml


# --- Test for DC (Dublin Core) XML search ---
@pytest.mark.unit
def test_search_dc_xml(search_cancer_dc_xml) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.text = search_cancer_dc_xml
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", format="dc")
        assert result == search_cancer_dc_xml


# --- Test for resultType='core' ---
@pytest.mark.unit
def test_search_core(search_cancer_core_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_cancer_core_json
        mock_response.text = json.dumps(search_cancer_core_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", resultType="core")
        assert result == search_cancer_core_json


# --- Test for resultType='idlist' ---
@pytest.mark.unit
def test_search_idlist(search_cancer_idlist_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_cancer_idlist_json
        mock_response.text = json.dumps(search_cancer_idlist_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", resultType="idlist")
        assert result == search_cancer_idlist_json


# --- Test for large result set (page_size=1000) ---
@pytest.mark.unit
def test_search_large_result_set(search_1000results_cancer_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_1000results_cancer_json
        mock_response.text = json.dumps(search_1000results_cancer_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", page_size=1000)
        assert result == search_1000results_cancer_json


# --- Test for no results ---
@pytest.mark.unit
def test_search_no_results(search_no_results_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_no_results_json
        mock_response.text = json.dumps(search_no_results_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("asdkfjhasdkfjhasdf")
        assert result == search_no_results_json
        if isinstance(result, dict):
            assert result.get("resultList", {}).get("result") == []


# --- Test for sorted search ---
@pytest.mark.unit
def test_search_sorted_cited(search_cancer_sorted_cited_json) -> None:
    client = SearchClient()
    with patch.object(client, "_get") as mock_get:
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = search_cancer_sorted_cited_json
        mock_response.text = json.dumps(search_cancer_sorted_cited_json)
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.search("cancer", sort="CITED")
        assert result == search_cancer_sorted_cited_json
