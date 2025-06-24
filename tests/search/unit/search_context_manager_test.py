import logging

import pytest

from pyeuropepmc.search import EuropePMCError, SearchClient

logging.basicConfig(level=logging.INFO)


@pytest.mark.unit
def test_enter_returns_self() -> None:
    client = SearchClient()
    with client as entered:
        assert entered is client


@pytest.mark.unit
def test_enter_allows_method_chaining() -> None:
    client = SearchClient()
    with client as entered:
        # Should be able to call a method (e.g., __repr__) on the returned object
        repr_str = entered.__repr__()
        assert isinstance(repr_str, str)


@pytest.mark.unit
def test_init_sets_correct_rate_limit_delay() -> None:
    """Test that SearchClient initializes with correct rate limit delay."""
    client = SearchClient(rate_limit_delay=2.5)
    assert client.rate_limit_delay == 2.5
    client.close()


@pytest.mark.unit
def test_init_default_rate_limit_delay() -> None:
    """Test that SearchClient uses default rate limit delay when not specified."""
    client = SearchClient()
    assert client.rate_limit_delay == 1.0
    client.close()


@pytest.mark.unit
def test_repr_returns_string() -> None:
    """Test that __repr__ returns a proper string representation."""
    client = SearchClient(rate_limit_delay=0.5)
    repr_str = repr(client)
    assert isinstance(repr_str, str)
    assert "SearchClient" in repr_str
    assert "0.5" in repr_str
    client.close()


@pytest.mark.unit
def test_close_method() -> None:
    """Test that close method works properly."""
    client = SearchClient()
    assert not client.is_closed
    client.close()
    assert client.is_closed


@pytest.mark.unit
def test_context_manager_closes_session() -> None:
    """Test that context manager properly closes session."""
    with SearchClient() as client:
        assert not client.is_closed
    assert client.is_closed


@pytest.mark.unit
def test_europepmc_error_exception() -> None:
    """Test that EuropePMCError can be raised and caught."""
    with pytest.raises(EuropePMCError):
        raise EuropePMCError("Test error message")
