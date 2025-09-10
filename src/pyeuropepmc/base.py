import logging
import time
from typing import Any

import backoff
import requests

from pyeuropepmc.error_codes import ErrorCodes
from pyeuropepmc.exceptions import APIClientError, ValidationError

__all__ = ["BaseAPIClient", "APIClientError"]


class BaseAPIClient:
    BASE_URL: str = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    DEFAULT_TIMEOUT: int = 15
    logger = logging.getLogger(__name__)

    def __init__(self, rate_limit_delay: float = 1.0) -> None:
        self.rate_limit_delay: float = rate_limit_delay
        self.session: requests.Session | None = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "pyeuropepmc/1.0.0 "
                    "(https://github.com/JonasHeinickeBio/pyEuropePMC; "
                    "jonas.heinicke@helmholtz-hzi.de)"
                )
            }
        )

    def __repr__(self) -> str:
        """Return a string representation of the client."""
        status = "closed" if self.is_closed else "active"
        return (
            f"{self.__class__.__name__}(rate_limit_delay={self.rate_limit_delay}, status={status})"
        )

    @backoff.on_exception(
        backoff.expo,
        (requests.ConnectionError, requests.Timeout, requests.HTTPError),
        max_tries=5,
        jitter=None,
        on_backoff=lambda details: BaseAPIClient.logger.warning(
            f"Backing off {details.get('wait', 'unknown')}s after {details['tries']} tries "
            f"calling {details['target'].__name__} with args {details['args']}, "
            f"kwargs {details['kwargs']}"
        ),
        on_giveup=lambda details: BaseAPIClient.logger.error(
            f"Giving up after {details['tries']} tries calling {details['target'].__name__}"
        ),
    )
    def _get(
        self, endpoint: str, params: dict[str, Any] | None = None, stream: bool = False
    ) -> requests.Response:
        """
        Robust GET request with retries and backoff.
        Raises APIClientError on failure.
        """
        if self.is_closed or self.session is None:
            raise APIClientError(ErrorCodes.FULL007)

        url: str = self.BASE_URL + endpoint
        try:
            self.logger.debug(f"GET request to {url} with params={params} and stream={stream}")
            response: requests.Response = self.session.get(
                url, params=params, timeout=self.DEFAULT_TIMEOUT, stream=stream
            )
            response.raise_for_status()
            self.logger.info(f"GET request to {url} succeeded with status {response.status_code}")
            return response
        except requests.HTTPError as e:
            # Map HTTP status codes to appropriate error codes
            status_code = e.response.status_code if e.response is not None else "unknown"

            # Select appropriate error code based on status
            if status_code == 404:
                error_code = ErrorCodes.HTTP404
            elif status_code == 403:
                error_code = ErrorCodes.HTTP403
            elif status_code == 500:
                error_code = ErrorCodes.HTTP500
            elif status_code == 429:
                error_code = ErrorCodes.RATE429
            else:
                error_code = ErrorCodes.NET001  # Generic network error

            context = {
                "url": url,
                "status_code": status_code,
                "endpoint": endpoint,
            }

            self.logger.error("[BaseAPIClient] GET request failed")
            raise APIClientError(error_code, context) from e
        except requests.RequestException as e:
            context = {
                "url": url,
                "error": str(e),
            }
            self.logger.error("[BaseAPIClient] Network request failed")
            raise APIClientError(ErrorCodes.NET001, context) from e
        finally:
            time.sleep(self.rate_limit_delay)

    def _get_error_context(self, endpoint: str, status_code: Any) -> str:
        """
        Provide context-specific error descriptions based on endpoint and status code.
        """
        endpoint_lower = endpoint.lower()

        # Handle XML endpoint errors
        if "fulltextxml" in endpoint_lower:
            return self._get_xml_error_context(endpoint, status_code)

        # Handle PDF endpoint errors
        if "pdf=render" in endpoint_lower:
            return self._get_pdf_render_error_context(status_code)

        if "ptpmcrender.fcgi" in endpoint_lower:
            return self._get_pdf_backend_error_context(status_code)

        # Generic error context
        return self._get_generic_error_context(status_code)

    def _get_xml_error_context(self, endpoint: str, status_code: Any) -> str:
        """Get error context for XML endpoints."""
        pmcid = endpoint.split("/")[0].replace("PMC", "")

        # Convert status_code to int for comparison if it's a string
        try:
            status_num = int(status_code) if status_code != "unknown" else 0
        except Exception as e:
            # Use ValidationError for type/format issues
            context = {
                "status_code": status_code,
                "original_exception": str(e),
            }
            raise ValidationError(
                ErrorCodes.VALID002,
                context=context,
                field_name="status_code",
                actual_value=status_code,
            ) from e

        error_messages = {
            404: (
                f"XML full text not available for PMC{pmcid} via REST API. "
                f"This typically means: (1) Article is not open access, "
                f"(2) Article doesn't have XML format available, "
                f"(3) PMC ID is invalid/doesn't exist, or "
                f"(4) Article is only available in bulk archives. "
                f"Attempting bulk FTP archive fallback..."
            ),
            403: (
                f"Access denied for PMC{pmcid} XML content. "
                f"Article may be access-restricted, under embargo, or require special "
                f"permissions. Attempting bulk FTP archive fallback..."
            ),
            500: (
                "Internal server error from Europe PMC REST API. "
                "The service may be temporarily experiencing issues. "
                "Attempting bulk FTP archive fallback..."
            ),
        }
        return error_messages.get(
            status_num,
            f"XML request failed for PMC{pmcid} with status {status_code}. "
            f"Attempting bulk FTP archive fallback...",
        )

    def _get_pdf_render_error_context(self, status_code: Any) -> str:
        """Get error context for PDF render endpoints."""
        error_messages = {
            404: (
                "PDF not available via render endpoint. "
                "Article may not have PDF format or may be access-restricted. "
                "Attempting backend service fallback..."
            ),
            403: (
                "PDF access denied via render endpoint. "
                "Article may be under embargo or require special permissions. "
                "Attempting alternative download methods..."
            ),
            500: (
                "PDF render service experiencing internal errors. "
                "Attempting backend service fallback..."
            ),
        }
        return error_messages.get(
            status_code,
            f"PDF render request failed with status {status_code}. Attempting fallback methods...",
        )

    def _get_pdf_backend_error_context(self, status_code: Any) -> str:
        """Get error context for PDF backend endpoints."""
        error_messages = {
            404: (
                "PDF not available via backend service. "
                "Article may not have PDF format available. "
                "Attempting ZIP archive fallback..."
            ),
            403: (
                "PDF access denied via backend service. "
                "Article may be access-restricted. "
                "Attempting ZIP archive fallback..."
            ),
            500: (
                "PDF backend service experiencing internal errors. "
                "Attempting ZIP archive fallback..."
            ),
        }
        return error_messages.get(
            status_code,
            f"PDF backend request failed with status {status_code}. "
            f"Attempting ZIP archive fallback...",
        )

    def _get_generic_error_context(self, status_code: Any) -> str:
        """Get generic error context for unknown endpoints."""
        error_messages = {
            404: (
                "Resource not found. The requested content may not exist, "
                "may have been moved, or the endpoint URL may be incorrect."
            ),
            403: (
                "Access forbidden. The content may be access-restricted, "
                "require authentication, or your IP may be blocked."
            ),
            500: (
                "Internal server error. The Europe PMC service may be "
                "temporarily experiencing issues. Try again later."
            ),
            429: (
                "Rate limit exceeded. Too many requests sent in a short time. "
                "Please wait before making more requests."
            ),
            502: (
                "Bad gateway. The Europe PMC service may be temporarily unavailable. "
                "Try again in a few minutes."
            ),
            503: (
                "Service unavailable. The Europe PMC service is temporarily down "
                "for maintenance. Try again later."
            ),
        }
        return error_messages.get(
            status_code,
            f"Request failed with HTTP status {status_code}. "
            f"Check the Europe PMC API documentation for more information.",
        )

    @backoff.on_exception(
        backoff.expo,
        (requests.ConnectionError, requests.Timeout, requests.HTTPError),
        max_tries=5,
        jitter=None,
        on_backoff=lambda details: BaseAPIClient.logger.warning(
            f"Backing off {details.get('wait', 'unknown')}s after {details['tries']} tries "
            f"calling {details['target'].__name__} with args {details['args']}, "
            f"kwargs {details['kwargs']}"
        ),
        on_giveup=lambda details: BaseAPIClient.logger.error(
            f"Giving up after {details['tries']} tries calling {details['target'].__name__}"
        ),
    )
    def _post(
        self, endpoint: str, data: dict[str, Any], headers: dict[str, str] | None = None
    ) -> requests.Response:
        """
        Robust POST request with retries and backoff.
        Raises APIClientError on failure.
        """
        if self.is_closed or self.session is None:
            raise APIClientError(ErrorCodes.FULL007)

        url: str = self.BASE_URL + endpoint
        try:
            self.logger.debug(f"POST request to {url} with data={data} and headers={headers}")
            response: requests.Response = self.session.post(
                url, data=data, headers=headers, timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            self.logger.info(f"POST request to {url} succeeded with status {response.status_code}")
            return response
        except requests.HTTPError as e:
            # Map HTTP status codes to appropriate error codes
            status_code = e.response.status_code if e.response else "unknown"

            # Select appropriate error code based on status
            if status_code == 404:
                error_code = ErrorCodes.HTTP404
            elif status_code == 403:
                error_code = ErrorCodes.HTTP403
            elif status_code == 500:
                error_code = ErrorCodes.HTTP500
            elif status_code == 429:
                error_code = ErrorCodes.RATE429
            else:
                error_code = ErrorCodes.NET001  # Generic network error

            context = {
                "url": url,
                "status_code": status_code,
                "endpoint": endpoint,
                "method": "POST",
            }

            self.logger.error("[BaseAPIClient] POST request failed")
            raise APIClientError(error_code, context) from e
        except requests.RequestException as e:
            context = {
                "url": url,
                "error": str(e),
                "method": "POST",
            }
            self.logger.error("[BaseAPIClient] Network POST request failed")
            raise APIClientError(ErrorCodes.NET001, context) from e
        finally:
            time.sleep(self.rate_limit_delay)

    def __enter__(self) -> "BaseAPIClient":
        """Enter the runtime context for the context manager."""
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None
    ) -> None:
        """Exit the runtime context and clean up resources."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if hasattr(self, "session") and self.session:
            self.logger.debug("Closing session")
            self.session.close()
            self.session = None  # Mark as closed

    @property
    def is_closed(self) -> bool:
        """Check if the session is closed."""
        return not hasattr(self, "session") or self.session is None
