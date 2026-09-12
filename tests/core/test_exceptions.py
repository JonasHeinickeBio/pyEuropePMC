"""Unit tests for pyeuropepmc.core.exceptions.

Covers PyEuropePMCError's diagnostic/reporting methods, every exception
subclass's context-building __init__, create_error_from_response's status
code -> exception mapping, and raise_for_status.
"""

from __future__ import annotations

import pytest

from pyeuropepmc.core.error_codes import ErrorCodes
from pyeuropepmc.core.exceptions import (
    APIClientError,
    APIError,
    ClientError,
    ConfigurationError,
    EuropePMCError,
    FileError,
    FullTextError,
    ModelError,
    ParsingError,
    PyEuropePMCError,
    QueryBuilderError,
    RateLimitError,
    SearchError,
    UnpaywallError,
    ValidationError,
    create_error_from_response,
    raise_for_status,
)


class TestPyEuropePMCErrorInit:
    def test_requires_error_code_or_message(self):
        with pytest.raises(ValueError, match="error_code.*message"):
            PyEuropePMCError()

    def test_message_only(self):
        err = PyEuropePMCError(message="custom message")
        assert err.message == "custom message"
        assert err.error_code == ErrorCodes.GENERIC001

    def test_error_code_only_looks_up_message(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert "not found" in err.message.lower()

    def test_endpoint_and_status_code_added_to_context(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404, endpoint="/search", status_code=404)
        assert err.context["endpoint"] == "/search"
        assert err.context["status_code"] == 404
        assert err.endpoint == "/search"
        assert err.status_code == 404

    def test_default_error_code_search(self):
        assert SearchError(message="x")._get_default_error_code() == ErrorCodes.GENERIC003

    def test_default_error_code_fulltext(self):
        assert FullTextError(message="x")._get_default_error_code() == ErrorCodes.GENERIC004

    def test_default_error_code_parsing(self):
        assert ParsingError(message="x")._get_default_error_code() == ErrorCodes.GENERIC005

    def test_default_error_code_validation(self):
        assert ValidationError(message="x")._get_default_error_code() == ErrorCodes.GENERIC006

    def test_default_error_code_configuration(self):
        assert ConfigurationError(message="x")._get_default_error_code() == ErrorCodes.GENERIC007

    def test_default_error_code_apiclient(self):
        assert APIClientError(message="x")._get_default_error_code() == ErrorCodes.GENERIC002

    def test_default_error_code_generic_fallback(self):
        assert ClientError(message="x")._get_default_error_code() == ErrorCodes.GENERIC001


class TestPyEuropePMCErrorDunder:
    def test_str_includes_error_code_prefix(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert str(err).startswith("[HTTP404]")

    def test_repr(self):
        err = PyEuropePMCError(message="x", error_code=ErrorCodes.GENERIC001)
        r = repr(err)
        assert "PyEuropePMCError" in r
        assert "error_code=" in r
        assert "context=" in r


class TestGetUserFriendlyMessage:
    def test_without_severity(self):
        err = PyEuropePMCError(message="oops")
        assert err.get_user_friendly_message() == "oops"

    def test_with_severity_prefix(self):
        err = PyEuropePMCError(message="oops", error_code=ErrorCodes.HTTP404)
        msg = err.get_user_friendly_message(include_severity=True)
        assert "oops" in msg


class TestGetUserFriendlySummary:
    def test_keys_present(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        summary = err.get_user_friendly_summary()
        assert set(summary.keys()) == {
            "title",
            "message",
            "action",
            "recovery_options",
            "severity",
            "retryable",
        }
        assert summary["title"].startswith("Error:")


class TestErrorCategoryAndSeverity:
    def test_get_error_category(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_error_category(), str)

    def test_get_severity_level(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_severity_level(), int)

    def test_get_severity(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_severity(), str)


class TestActionableAdvice:
    def test_without_category(self):
        err = PyEuropePMCError(message="base advice", error_code=ErrorCodes.GENERIC001)
        assert err.get_actionable_advice(include_category=False) == "base advice"

    def test_with_known_category_appends_advice(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        advice = err.get_actionable_advice()
        category = err.get_error_category()
        if category in {
            "Network",
            "HTTP",
            "Authentication",
            "Rate Limiting",
            "Search",
            "Full Text",
            "Parsing",
            "Validation",
            "Configuration",
            "Content Availability",
            "License",
        }:
            assert "Action:" in advice
        else:
            assert advice == err.message


class TestRetryableAndSuggestion:
    def test_is_retryable_returns_bool(self):
        err = PyEuropePMCError(error_code=ErrorCodes.RATE429)
        assert isinstance(err.is_retryable(), bool)

    def test_get_suggestion(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_suggestion(), str)

    def test_get_suggestion_with_code_snippet(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_suggestion(include_code_snippet=True), str)

    def test_get_recovery_options(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_recovery_options(), list)

    def test_get_classification(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_classification(), dict)

    def test_get_expected_resolution_time(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        assert isinstance(err.get_expected_resolution_time(), str)


class TestToDict:
    def test_full_dict(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404, endpoint="/x", status_code=404)
        d = err.to_dict()
        assert d["error_code"] == "HTTP404"
        assert d["endpoint"] == "/x"
        assert d["status_code"] == 404
        assert "context" in d
        assert "recovery_options" in d
        assert "severity_level" in d
        assert "classification" in d

    def test_without_context_and_recovery(self):
        err = PyEuropePMCError(error_code=ErrorCodes.HTTP404)
        d = err.to_dict(include_context=False, include_recovery=False)
        assert "context" not in d
        assert "recovery_options" not in d
        assert "severity_level" not in d
        assert "classification" not in d

    def test_without_endpoint_or_status_code(self):
        err = PyEuropePMCError(message="x")
        d = err.to_dict()
        assert "endpoint" not in d
        assert "status_code" not in d


class TestCreateErrorFromResponse:
    @pytest.mark.parametrize(
        "status_code",
        [401, 403, 404, 429, 500, 503, 400, 422, 999],
    )
    def test_returns_api_client_error_for_all_status_codes(self, status_code):
        err = create_error_from_response(status_code, endpoint="/x")
        assert isinstance(err, PyEuropePMCError)

    def test_generic_status_code_returns_base_error(self):
        err = create_error_from_response(200)
        assert type(err) is PyEuropePMCError

    def test_custom_error_code_and_message_passed_through(self):
        err = create_error_from_response(404, error_code=ErrorCodes.HTTP404, message="custom")
        assert err.message == "custom"


class TestRaiseForStatus:
    def test_raises_appropriate_error(self):
        with pytest.raises(PyEuropePMCError):
            raise_for_status(404, endpoint="/x")


class TestSearchErrorContext:
    def test_all_kwargs_populate_context_and_attrs(self):
        err = SearchError(message="x", query="cancer", search_type="cites", page=2, page_size=25)
        assert err.context["query"] == "cancer"
        assert err.context["search_type"] == "cites"
        assert err.context["page"] == 2
        assert err.context["page_size"] == 25
        assert err.query == "cancer"
        assert err.search_type == "cites"
        assert err.page == 2
        assert err.page_size == 25

    def test_no_kwargs_leaves_context_minimal(self):
        err = SearchError(message="x")
        assert "query" not in err.context


class TestFullTextErrorContext:
    def test_all_kwargs(self):
        err = FullTextError(
            message="x", pmcid="PMC123", format_type="pdf", operation="download", doi="10.1/x"
        )
        assert err.context["pmcid"] == "PMC123"
        assert err.context["format_type"] == "pdf"
        assert err.context["operation"] == "download"
        assert err.context["doi"] == "10.1/x"
        assert err.pmcid == "PMC123"
        assert err.format_type == "pdf"
        assert err.operation == "download"
        assert err.doi == "10.1/x"


class TestParsingErrorContext:
    def test_original_data_truncated(self):
        long_data = "x" * 300
        err = ParsingError(
            message="x", data_type="json", parser_type="p", line_number=5, original_data=long_data
        )
        assert err.context["original_data"].endswith("...")
        assert len(err.context["original_data"]) == 203
        assert err.data_type == "json"
        assert err.parser_type == "p"
        assert err.line_number == 5
        assert err.original_data == long_data

    def test_short_original_data_not_truncated(self):
        err = ParsingError(message="x", original_data="short")
        assert err.context["original_data"] == "short"


class TestValidationErrorContext:
    def test_all_kwargs(self):
        err = ValidationError(
            message="x",
            field_name="page_size",
            expected_type="int",
            actual_value="abc",
            min_value=1,
            max_value=100,
            allowed_values=[1, 2, 3],
        )
        assert err.context["field_name"] == "page_size"
        assert err.context["expected_type"] == "int"
        assert err.context["actual_value"] == "abc"
        assert err.context["min_value"] == "1"
        assert err.context["max_value"] == "100"
        assert err.context["allowed_values"] == "1, 2, 3"
        assert err.details == err.context

    def test_long_actual_value_truncated(self):
        err = ValidationError(message="x", actual_value="y" * 200)
        assert len(err.context["actual_value"]) == 100


class TestConfigurationErrorContext:
    def test_all_kwargs(self):
        err = ConfigurationError(
            message="x",
            config_key="api_key",
            config_section="auth",
            env_var="EPMC_API_KEY",
            required_dependency="requests",
        )
        assert err.context["config_key"] == "api_key"
        assert err.context["config_section"] == "auth"
        assert err.context["env_var"] == "EPMC_API_KEY"
        assert err.context["required_dependency"] == "requests"


class TestRateLimitErrorContext:
    def test_retry_after(self):
        err = RateLimitError(message="x", retry_after=30)
        assert err.context["retry_after"] == 30
        assert err.retry_after == 30

    def test_is_subclass_of_api_client_error(self):
        assert isinstance(RateLimitError(message="x"), APIClientError)


class TestQueryBuilderErrorContext:
    def test_all_kwargs(self):
        err = QueryBuilderError(message="x", query_part="AND", position=5, expected="term")
        assert err.context["query_part"] == "AND"
        assert err.context["position"] == 5
        assert err.context["expected"] == "term"


class TestUnpaywallErrorContext:
    def test_all_kwargs(self):
        err = UnpaywallError(message="x", doi="10.1/x", unpaywall_url="http://api.unpaywall.org/x")
        assert err.context["doi"] == "10.1/x"
        assert err.context["unpaywall_url"] == "http://api.unpaywall.org/x"


class TestClientErrorContext:
    def test_all_kwargs(self):
        err = ClientError(message="x", client_type="search", config_keys=["a", "b"])
        assert err.context["client_type"] == "search"
        assert err.context["config_keys"] == "a, b"
        assert err.config_keys == ["a", "b"]


class TestAPIErrorContext:
    def test_all_kwargs(self):
        err = APIError(message="x", endpoint="/search", request_id="req1", response_status=500)
        assert err.context["endpoint"] == "/search"
        assert err.context["request_id"] == "req1"
        assert err.context["response_status"] == 500
        assert err.status_code == 500


class TestFileErrorContext:
    def test_all_kwargs(self):
        err = FileError(message="x", file_path="/tmp/a.pdf", operation="write", file_size=1024)
        assert err.context["file_path"] == "/tmp/a.pdf"
        assert err.context["operation"] == "write"
        assert err.context["file_size"] == 1024
        assert err.file_path == "/tmp/a.pdf"

    def test_zero_file_size_included(self):
        err = FileError(message="x", file_size=0)
        assert err.context["file_size"] == 0


class TestModelErrorContext:
    def test_all_kwargs(self):
        err = ModelError(
            message="x",
            model_type="PaperEntity",
            field_name="doi",
            expected_type="str",
            actual_value=123,
        )
        assert err.context["model_type"] == "PaperEntity"
        assert err.context["field_name"] == "doi"
        assert err.context["expected_type"] == "str"
        assert err.context["actual_value"] == "123"


class TestLegacyAlias:
    def test_europepmc_error_is_search_error(self):
        assert EuropePMCError is SearchError
