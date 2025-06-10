import pytest
from unittest.mock import patch, MagicMock
from aid_pais_knowledgegraph.py_europepmc.base import BaseAPIClient

@pytest.fixture
def client():
    client_instance = BaseAPIClient(rate_limit_delay=1)
    yield client_instance
    client_instance.close()

@patch('time.sleep')
def test_get_success(mock_sleep, client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 200

    with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
        response = client._get('test_endpoint', params={'q': 'test'})
        mock_get.assert_called_once_with(
            client.BASE_URL + 'test_endpoint',
            params={'q': 'test'},
            timeout=client.DEFAULT_TIMEOUT,
            stream=False
        )
        assert response == mock_response

@patch('time.sleep')
def test_get_failure(mock_sleep, client):
    with patch.object(client.session, 'get', side_effect=Exception("Network error")):
        with pytest.raises(Exception) as exc_info:
            client._get('bad_endpoint')
        assert str(exc_info.value) == "Network error"

@patch('time.sleep')
def test_post_success(mock_sleep, client):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.status_code = 201

    with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
        response = client._post('test_endpoint', data={'key': 'value'})
        mock_post.assert_called_once_with(
            client.BASE_URL + 'test_endpoint',
            data={'key': 'value'},
            timeout=client.DEFAULT_TIMEOUT
        )
        assert response == mock_response

@patch('time.sleep')
def test_post_failure(mock_sleep, client):
    with patch.object(client.session, 'post', side_effect=Exception("Network error")):
        with pytest.raises(Exception) as exc_info:
            client._post('bad_endpoint', data={'fail': True})
        assert str(exc_info.value) == "Network error"

def test_close(client):
    with patch.object(client.session, 'close') as mock_close:
        client.close()
        mock_close.assert_called_once()