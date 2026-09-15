"""Regression tests for the ``validate=True`` availability handling.

The refactor that removed the module-level ``SEARCH_QUERY_AVAILABLE`` flag
(b26d697) left the warning body behind but dropped both halves of the logic
around it: the guard that made the warning conditional, and the assignment
that actually disabled validation. The result was a warning that fired
whenever ``validate=True`` -- telling users to install a package they already
had -- while a genuinely missing package was not handled at all.
"""

import warnings

import pytest

from pyeuropepmc.features.literature import query_builder as qb_module
from pyeuropepmc.features.literature.query_builder import QueryBuilder

pytestmark = pytest.mark.unit


class TestValidateWithSearchQueryInstalled:
    """search-query is a declared runtime dependency, so it is installed."""

    def test_no_warning_when_package_is_available(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            QueryBuilder(validate=True)

        messages = [str(w.message) for w in caught]
        assert not [m for m in messages if "search-query package not available" in m], (
            f"warned that an installed package is missing: {messages}"
        )

    def test_validation_stays_enabled_when_package_is_available(self) -> None:
        builder = QueryBuilder(validate=True)
        assert builder._validate is True


class TestValidateWithSearchQueryMissing:
    """The docstring promises validation is disabled automatically."""

    @pytest.fixture
    def missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            qb_module,
            "is_dependency_available",
            lambda package: package not in {"search-query", "search_query"},
        )

    @pytest.mark.usefixtures("missing")
    def test_warns_when_package_is_absent(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            QueryBuilder(validate=True)

        assert any("search-query package not available" in str(w.message) for w in caught)

    @pytest.mark.usefixtures("missing")
    def test_validation_is_disabled_when_package_is_absent(self) -> None:
        builder = QueryBuilder(validate=True)
        assert builder._validate is False

    @pytest.mark.usefixtures("missing")
    def test_build_degrades_instead_of_raising(self) -> None:
        """With validation silently disabled, build() must still return a query."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            builder = QueryBuilder(validate=True).keyword("cancer")

        assert "cancer" in builder.build()


class TestValidateDefaultOff:
    def test_default_does_not_warn(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            QueryBuilder()

        assert not caught
