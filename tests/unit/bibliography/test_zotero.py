import pytest
from unittest.mock import patch, MagicMock
from pyeuropepmc.features.bibliography.zotero import ZoteroClient, ZOTERO_AVAILABLE


class TestZoteroClientInit:
    def test_import_error_when_not_available(self):
        with patch("pyeuropepmc.features.bibliography.zotero.ZOTERO_AVAILABLE", False):
            with pytest.raises(ImportError, match="pyzotero"):
                ZoteroClient(library_id="123", api_key="key")

    def test_warning_when_no_api_key(self):
        with patch("pyeuropepmc.features.bibliography.zotero.ZOTERO_AVAILABLE", True):
            with patch("pyeuropepmc.features.bibliography.zotero.os.getenv", return_value=""):
                with patch("pyeuropepmc.features.bibliography.zotero.logger") as mock_logger:
                    ZoteroClient(library_id="123")
                    mock_logger.warning.assert_called_once()

    def test_no_warning_with_api_key(self):
        with patch("pyeuropepmc.features.bibliography.zotero.ZOTERO_AVAILABLE", True):
            with patch("pyeuropepmc.features.bibliography.zotero.logger") as mock_logger:
                ZoteroClient(library_id="123", api_key="valid_key")
                mock_logger.warning.assert_not_called()


class TestZoteroClientApiError:
    def test_search_raises_on_missing_credentials(self):
        with patch("pyeuropepmc.features.bibliography.zotero.ZOTERO_AVAILABLE", True):
            with patch("pyeuropepmc.features.bibliography.zotero._PyZotero") as MockPyZotero:
                mock_instance = MockPyZotero.return_value
                mock_instance.items.side_effect = Exception("Invalid API key")
                client = ZoteroClient(library_id="123", api_key="bad_key")
                with pytest.raises(Exception, match="Invalid API key"):
                    client.search(query="test")
