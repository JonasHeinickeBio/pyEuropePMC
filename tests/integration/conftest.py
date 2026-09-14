"""Integration test configuration.

Integration tests hit live APIs and are skipped by default.
Run with: pytest --run-integration

The ``--run-integration`` option itself is registered in tests/conftest.py:
pytest only honours ``pytest_addoption`` from initial conftests, so defining it
here made it unreachable from any run not started inside this directory.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration (requires live API access)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return  # Run all tests
    skip_integration = pytest.mark.skip(reason="use --run-integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
