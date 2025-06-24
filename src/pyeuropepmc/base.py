import logging
import time
from typing import Any, Dict, Optional

import backoff
import requests


class APIClientError(Exception):
    """Custom exception for API client errors."""

    pass


class BaseAPIClient:
    BASE_URL: str = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    DEFAULT_TIMEOUT: int = 15
    logger = logging.getLogger(__name__)

    def __init__(self, rate_limit_delay: float = 1.0) -> None:
        self.rate_limit_delay: float = rate_limit_delay
        self.session: Optional[requests.Session] = requests.Session()

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
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, stream: bool = False
    ) -> requests.Response:
        """
        Robust GET request with retries and backoff.
        Raises APIClientError on failure.
        """
        if self.is_closed or self.session is None:
            raise APIClientError("Session is closed. Cannot make requests.")

        url: str = self.BASE_URL + endpoint
        try:
            self.logger.debug(f"GET request to {url} with params={params} and stream={stream}")
            response: requests.Response = self.session.get(
                url, params=params, timeout=self.DEFAULT_TIMEOUT, stream=stream
            )
            response.raise_for_status()
            self.logger.info(f"GET request to {url} succeeded with status {response.status_code}")
            return response
        except requests.RequestException as e:
            self.logger.error(f"[BaseAPIClient] GET request failed: {e}")
            raise APIClientError(f"GET request to {url} failed: {e}")
        finally:
            time.sleep(self.rate_limit_delay)

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
        self, endpoint: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """
        Robust POST request with retries and backoff.
        Raises APIClientError on failure.
        """
        if self.is_closed or self.session is None:
            raise APIClientError("Session is closed. Cannot make requests.")

        url: str = self.BASE_URL + endpoint
        try:
            self.logger.debug(f"POST request to {url} with data={data} and headers={headers}")
            response: requests.Response = self.session.post(
                url, data=data, headers=headers, timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            self.logger.info(f"POST request to {url} succeeded with status {response.status_code}")
            return response
        except requests.RequestException as e:
            self.logger.error(f"[BaseAPIClient] POST request failed: {e}")
            raise APIClientError(f"POST request to {url} failed: {e}")
        finally:
            time.sleep(self.rate_limit_delay)

    def __enter__(self) -> "BaseAPIClient":
        """Enter the runtime context for the context manager."""
        return self

    def __exit__(
        self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]
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
