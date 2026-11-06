"""Finding the bulk XML archive of a PMC ID from the server's folder listing (hermetic)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient

LISTING = """
<tr><td><a href="PMC3000001_PMC3010000.xml.gz">PMC3000001_PMC3010000.xml.gz</a></td></tr>
<tr><td><a href="PMC3010001_PMC3019986.xml.gz">PMC3010001_PMC3019986.xml.gz</a></td></tr>
<tr><td><a href="PMC3020039_PMC3029998.xml.gz">PMC3020039_PMC3029998.xml.gz</a></td></tr>
<tr><td><a href="AccNoSupplData/">AccNoSupplData/</a></td></tr>
<tr><td><a href="PMC9_PMC1.xml.gz">PMC9_PMC1.xml.gz</a></td></tr>
"""


def _page(status=200, text=LISTING):
    response = MagicMock()
    response.status_code = status
    response.text = text
    return response


@pytest.fixture
def client():
    return FullTextClient(enable_cache=False)


def test_the_archive_is_the_listed_range_that_holds_the_id(client):
    with patch("requests.get", return_value=_page()):
        assert client._determine_bulk_archive_range(3005000) == (3000001, 3010000)
        assert client._determine_bulk_archive_range(3019986) == (3010001, 3019986)
        assert client._determine_bulk_archive_range(3020039) == (3020039, 3029998)


@pytest.mark.parametrize("pmcid", [2999999, 3019987, 3020038, 3030000])
def test_an_id_in_a_gap_or_outside_the_listing_has_no_archive(client, pmcid):
    with patch("requests.get", return_value=_page()):
        assert client._determine_bulk_archive_range(pmcid) is None


def test_an_upside_down_name_is_ignored(client):
    with patch("requests.get", return_value=_page()):
        assert (9, 1) not in client._bulk_archive_ranges()


def test_the_listing_is_read_once_per_client(client):
    with patch("requests.get", return_value=_page()) as get:
        client._determine_bulk_archive_range(3005000)
        client._determine_bulk_archive_range(3015000)
    assert get.call_count == 1
    assert get.call_args[0][0] == FullTextClient.FTP_OA_BASE_URL


@pytest.mark.parametrize(
    "failure",
    [_page(503), requests.ConnectionError("down")],
    ids=["http-error", "unreachable"],
)
def test_a_failed_listing_means_no_archive_and_is_asked_again(client, failure):
    broken = (
        {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
    )
    with patch("requests.get", **broken):
        assert client._determine_bulk_archive_range(3005000) is None
    with patch("requests.get", return_value=_page()):
        assert client._determine_bulk_archive_range(3005000) == (3000001, 3010000)


def test_the_archives_come_from_the_ebi_server_not_the_blocked_site():
    assert FullTextClient.FTP_OA_BASE_URL == "https://ftp.ebi.ac.uk/pub/databases/pmc/oa/"
