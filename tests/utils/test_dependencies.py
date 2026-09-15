"""Unit tests for pyeuropepmc.utils.dependencies."""

from __future__ import annotations

import pytest

from pyeuropepmc.utils.dependencies import (
    DEPENDENCY_GROUPS,
    FEATURE_TO_GROUP,
    is_dependency_available,
    require_dependency,
    skip_if_dependencies_missing,
    skip_if_dependency_missing,
)


def test_reexports_match_optional_imports():
    from pyeuropepmc._optional_imports import DEPENDENCY_GROUPS as D2, FEATURE_TO_GROUP as F2

    assert DEPENDENCY_GROUPS is D2
    assert FEATURE_TO_GROUP is F2


class TestIsDependencyAvailable:
    def test_available_package(self):
        assert is_dependency_available("requests") is True

    def test_missing_package(self):
        assert is_dependency_available("nonexistent_package_zzz_123") is False

    def test_hyphenated_name_normalized(self):
        # "requests" would come back true whether or not this normalizes,
        # but a name that only exists as an underscore module confirms
        # the dash -> underscore replacement runs.
        assert is_dependency_available("python-dotenv".replace("python-", "")) is True


class TestRequireDependency:
    def test_present_does_not_raise(self):
        require_dependency("requests", "http calls")

    def test_missing_raises_with_pip_install(self):
        with pytest.raises(ImportError, match="pip install nonexistent_package_zzz_123"):
            require_dependency("nonexistent_package_zzz_123", "some feature")

    def test_missing_raises_with_install_group(self):
        with pytest.raises(ImportError, match=r"pip install pyeuropepmc\[standard\]"):
            require_dependency(
                "nonexistent_package_zzz_123", "some feature", install_group="standard"
            )


class TestSkipIfDependencyMissing:
    def test_present_runs_function(self):
        @skip_if_dependency_missing("requests", "http")
        def fn():
            return "ran"

        assert fn() == "ran"

    def test_missing_skips(self):
        @skip_if_dependency_missing("nonexistent_package_zzz_123", "some feature")
        def fn():
            raise AssertionError("should not run")

        with pytest.raises(pytest.skip.Exception):
            fn()

    def test_missing_skips_with_group_hint(self):
        @skip_if_dependency_missing(
            "nonexistent_package_zzz_123", "some feature", install_group="standard"
        )
        def fn():
            raise AssertionError("should not run")

        with pytest.raises(pytest.skip.Exception):
            fn()


class TestSkipIfDependenciesMissing:
    def test_all_present_runs(self):
        @skip_if_dependencies_missing(["requests"], "http")
        def fn():
            return "ran"

        assert fn() == "ran"

    def test_any_missing_skips(self):
        @skip_if_dependencies_missing(["requests", "nonexistent_package_zzz_123"], "mixed feature")
        def fn():
            raise AssertionError("should not run")

        with pytest.raises(pytest.skip.Exception):
            fn()

    def test_any_missing_skips_with_group(self):
        @skip_if_dependencies_missing(
            ["nonexistent_package_zzz_123"], "feature", install_group="standard"
        )
        def fn():
            raise AssertionError("should not run")

        with pytest.raises(pytest.skip.Exception):
            fn()
