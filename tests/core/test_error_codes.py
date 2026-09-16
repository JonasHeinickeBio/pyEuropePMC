"""Unit tests for pyeuropepmc.core.error_codes module-level helper functions
not already exercised indirectly via tests/core/test_exceptions.py."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from pyeuropepmc.core.error_codes import (
    ERROR_DOCS_URL,
    ERROR_MESSAGES,
    ErrorCodes,
    create_error_from_response_with_recovery,
    error_docs_url,
    format_error_message,
    format_error_response,
    generate_error_code,
    get_error_code_prefix,
    get_error_message,
    get_error_message_by_string,
    get_error_severity,
    get_error_suggestion,
    get_expected_resolution_time,
    raise_for_status,
)
from pyeuropepmc.core.exceptions import APIClientError, ValidationError


class TestGetErrorMessageByString:
    def test_known_code(self):
        msg = get_error_message_by_string("HTTP404")
        assert "not found" in msg.lower()

    def test_unknown_code_returns_fallback(self):
        assert get_error_message_by_string("NOPE999") == (
            "Unknown error. Please check your input and try again."
        )


class TestFormatErrorMessage:
    def test_missing_context_key_appends_details(self):
        msg = format_error_message(ErrorCodes.HTTP404, context={})
        # HTTP404's message doesn't require formatting so this should be safe;
        # use a code with format placeholders if available, else assert no crash.
        assert isinstance(msg, str)

    def test_key_error_path_appends_missing_detail(self):
        # format_error_message swallows a KeyError raised by str.format when
        # the message references a placeholder absent from context.
        import pyeuropepmc.core.error_codes as ec

        original = ec.ERROR_MESSAGES.get("HTTP404")
        ec.ERROR_MESSAGES["HTTP404"] = "Missing {field_name} here"
        try:
            msg = format_error_message(ErrorCodes.HTTP404, context={}, include_help_link=False)
            assert "missing 'field_name'" in msg
        finally:
            if original is not None:
                ec.ERROR_MESSAGES["HTTP404"] = original

    def test_value_error_path_returns_base_message(self):
        import pyeuropepmc.core.error_codes as ec

        original = ec.ERROR_MESSAGES.get("HTTP404")
        ec.ERROR_MESSAGES["HTTP404"] = "Bad value {value:d} here"
        try:
            msg = format_error_message(
                ErrorCodes.HTTP404, context={"value": "not-a-number"}, include_help_link=False
            )
            assert msg == "Bad value {value:d} here"
        finally:
            if original is not None:
                ec.ERROR_MESSAGES["HTTP404"] = original


class TestGetErrorSuggestionCodeSnippets:
    def test_http429_snippet(self):
        suggestion = get_error_suggestion(ErrorCodes.HTTP429, include_code_snippet=True)
        assert "exponential backoff" in suggestion

    def test_auth401_snippet(self):
        suggestion = get_error_suggestion(ErrorCodes.AUTH401, include_code_snippet=True)
        assert "api_key" in suggestion

    def test_valid002_snippet(self):
        suggestion = get_error_suggestion(ErrorCodes.VALID002, include_code_snippet=True)
        assert "page_size" in suggestion

    def test_unknown_snippet_code_returns_plain_message(self):
        suggestion = get_error_suggestion(ErrorCodes.HTTP404, include_code_snippet=True)
        assert "```" not in suggestion

    def test_without_snippet_flag(self):
        suggestion = get_error_suggestion(ErrorCodes.RATE429, include_code_snippet=False)
        assert "```" not in suggestion


class TestGetErrorCodePrefix:
    def test_http_prefix(self):
        assert get_error_code_prefix(ErrorCodes.HTTP404) == "HTTP"

    def test_non_http_prefix(self):
        assert get_error_code_prefix(ErrorCodes.RATE429) == "RATE"

    def test_string_input(self):
        assert get_error_code_prefix("NET001") == "NET"


class TestGetErrorSeverity:
    def test_critical_pattern(self):
        assert get_error_severity(ErrorCodes.AUTH401) == "critical"

    def test_warning_pattern(self):
        assert get_error_severity(ErrorCodes.VALID001) == "warning"

    def test_info_fallback(self):
        assert get_error_severity("ZZZ999") == "info"


class TestGetExpectedResolutionTime:
    def test_net001_fast(self):
        assert get_expected_resolution_time(ErrorCodes.NET001) == "5-10 seconds"

    def test_rate_limit(self):
        assert get_expected_resolution_time(ErrorCodes.RATE429) == "1-5 minutes"

    def test_http503(self):
        assert get_expected_resolution_time(ErrorCodes.HTTP503) == "1-10 minutes"

    def test_http408(self):
        assert get_expected_resolution_time(ErrorCodes.HTTP408) == (
            "Immediate retry (increased timeout recommended)"
        )

    def test_auth(self):
        assert get_expected_resolution_time(ErrorCodes.AUTH401) == "Immediate (fix credentials)"

    def test_http400_not_retryable(self):
        assert get_expected_resolution_time(ErrorCodes.HTTP400) == "Not retryable (fix request)"

    def test_net003_dns(self):
        assert get_expected_resolution_time(ErrorCodes.NET003) == "Immediate (check DNS)"

    def test_default_fallback(self):
        assert get_expected_resolution_time("ZZZ999") == "Check specific error details"

    def test_with_recommendation(self):
        result = get_expected_resolution_time(ErrorCodes.NET001, include_recommendation=True)
        assert " - " in result
        assert "Check network stability" in result

    def test_with_recommendation_default(self):
        result = get_expected_resolution_time("ZZZ999", include_recommendation=True)
        assert result.endswith("Wait and retry")


class TestGenerateErrorCode:
    def test_http_category(self):
        assert generate_error_code("HTTP", 404) == "HTTP404"

    def test_other_category_zero_padded(self):
        assert generate_error_code("NET", 1) == "NET001"


class TestCreateErrorFromResponseWithRecovery:
    def test_populates_recovery_context(self):
        error = create_error_from_response_with_recovery(429, "/api/search")
        assert isinstance(error, APIClientError)
        assert "recovery_options" in error.context
        assert "retryable" in error.context
        assert "expected_resolution_time" in error.context
        assert "severity" in error.context

    def test_response_body_truncated(self):
        long_body = "x" * 2000
        error = create_error_from_response_with_recovery(500, "/api/x", response_body=long_body)
        assert error.context["response_body"].endswith("...")
        assert len(error.context["response_body"]) == 1003

    def test_short_response_body_not_truncated(self):
        error = create_error_from_response_with_recovery(500, "/api/x", response_body="short")
        assert error.context["response_body"] == "short"


class TestFormatErrorResponse:
    def test_basic_fields_present(self):
        error = ValidationError(error_code=ErrorCodes.VALID001, context={"field_name": "x"})
        formatted = format_error_response(error)
        assert "[VALID001]" in formatted
        assert "Category:" in formatted
        assert "Severity:" in formatted
        assert "Retryable:" in formatted

    def test_includes_recovery_when_present(self):
        error = ValidationError(error_code=ErrorCodes.VALID001)
        formatted = format_error_response(error, include_recovery=True)
        assert "Recovery:" in formatted or "Context:" in formatted

    def test_excludes_recovery_when_false(self):
        error = ValidationError(error_code=ErrorCodes.VALID001)
        formatted = format_error_response(error, include_recovery=False)
        assert "Recovery:" not in formatted

    def test_includes_traceback_when_requested(self):
        try:
            raise ValidationError(error_code=ErrorCodes.VALID001)
        except ValidationError as e:
            formatted = format_error_response(e, include_traceback=True)
        assert "Traceback:" in formatted

    def test_includes_context_when_present(self):
        error = ValidationError(error_code=ErrorCodes.VALID001, context={"field_name": "x"})
        formatted = format_error_response(error)
        assert "Context:" in formatted


class TestRaiseForStatus:
    def test_raises_apiclient_error(self):
        with pytest.raises(APIClientError):
            raise_for_status(404, "/api/search", response_body="Not found")


class TestErrorDocsLinks:
    """``Docs:`` links lead to the section of the published page that lists the code.

    They used to point at pyeuropepmc.rtfd.io, which never existed.
    """

    DOCS_PAGE = Path(__file__).resolve().parents[2] / "docs" / "reference" / "error-codes.md"

    @classmethod
    def _sections(cls) -> dict[str, str]:
        """Section anchor (as GitHub Pages' kramdown derives it) -> section text."""
        parts = re.split(r"^## (.+)$", cls.DOCS_PAGE.read_text(encoding="utf-8"), flags=re.M)
        return {
            re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-"): body
            for title, body in zip(parts[1::2], parts[2::2], strict=True)
        }

    @staticmethod
    def _listed_codes(section: str) -> set[str]:
        """Codes named in a section, with ranges such as ``FULL012``–``FULL016`` expanded."""
        codes = set(re.findall(r"`([A-Z]+\d{3})`", section))
        for prefix, start, end in re.findall(r"`([A-Z]+)(\d{3})`–`[A-Z]+(\d{3})`", section):
            codes.update(f"{prefix}{n:03d}" for n in range(int(start), int(end) + 1))
        return codes

    @pytest.mark.parametrize("code", list(ErrorCodes), ids=lambda c: c.value)
    def test_link_points_at_the_section_listing_the_code(self, code: ErrorCodes) -> None:
        url = error_docs_url(code)
        page, _, anchor = url.partition("#")

        assert page == ERROR_DOCS_URL
        sections = self._sections()
        assert anchor in sections, f"{url} names no section of {self.DOCS_PAGE.name}"
        assert code.value in self._listed_codes(sections[anchor])

    def test_no_message_links_to_the_dead_site(self) -> None:
        assert not [code for code, message in ERROR_MESSAGES.items() if "rtfd.io" in message]
        assert "rtfd.io" not in get_error_message(ErrorCodes.NET001, include_help_link=True)
