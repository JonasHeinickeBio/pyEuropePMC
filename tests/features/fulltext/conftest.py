"""Shared fixtures for the full-text tests."""

import pytest

from pyeuropepmc.features.fulltext.fulltext_client import FullTextClient


@pytest.fixture(autouse=True)
def _no_challenge_cooldown_leak():
    """Keep one test's Cloudflare cooldown from skipping another test's PDF steps.

    The cooldown is class-level on purpose (it outlives a client), so a live
    functional test that really meets the browser check would otherwise make
    every later test skip the Europe PMC endpoints.
    """
    FullTextClient._challenged_hosts.clear()
    yield
    FullTextClient._challenged_hosts.clear()
