"""
Last.fm API client implementation.

Provides a robust wrapper around the Last.fm API with:
- Authentication and credential management
- Rate limiting and retry logic
- Connection testing
- Comprehensive error handling
"""
import logging
import time
import hashlib
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import LastFmConfig
from .exceptions import (
    LastFmAPIError,
    LastFmAuthenticationError,
    LastFmConnectionError,
    LastFmRateLimitError,
    LastFmInvalidResponseError,
    LastFmUserNotFoundError,
)


logger = logging.getLogger('music.lastfm')


class LastFmClient:
    """
    Last.fm API client with authentication, rate limiting, and error handling.

    Implements Last.fm API 2.0 specification with automatic retry logic
    and comprehensive error handling.
    """

    BASE_URL = "https://ws.audioscrobbler.com/2.0/"
    MAX_RETRIES = 3
    RETRY_BACKOFF_FACTOR = 1.5
    REQUEST_TIMEOUT = 30
    RATE_LIMIT_DELAY = 0.2

    def __init__(self, config: Optional[LastFmConfig] = None):
        """
        Initialize Last.fm client.

        Args:
            config: LastFmConfig instance (will create if not provided)
        """
        self.config = config or LastFmConfig()
        self._session = None
        self._last_request_time = 0

        is_valid, error_msg = self.config.validate()
        if not is_valid:
            logger.warning(f"Last.fm client initialized with invalid config: {error_msg}")

    def _get_session(self) -> requests.Session:
        """
        Get or create requests session with retry configuration.

        Returns:
            Configured requests.Session instance
        """
        if self._session is None:
            self._session = requests.Session()

            retry_strategy = Retry(
                total=self.MAX_RETRIES,
                backoff_factor=self.RETRY_BACKOFF_FACTOR,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"],
                raise_on_status=False,
            )

            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)

            self._session.headers.update({
                'User-Agent': 'Scrobblarr/1.0 (Last.fm Analytics)',
            })

        return self._session

    def _respect_rate_limit(self):
        """
        Ensure we respect Last.fm's rate limit (5 requests per second).
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self.RATE_LIMIT_DELAY:
            sleep_time = self.RATE_LIMIT_DELAY - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _build_signature(self, params: Dict[str, Any]) -> str:
        """
        Build API signature for authenticated requests.

        Args:
            params: Request parameters (without api_sig)

        Returns:
            MD5 hash signature string
        """
        sorted_params = sorted(params.items())
        signature_string = ''.join(f"{k}{v}" for k, v in sorted_params)
        signature_string += self.config.api_secret

        return hashlib.md5(signature_string.encode('utf-8')).hexdigest()

    def _make_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        authenticated: bool = False
    ) -> Dict[str, Any]:
        """
        Make request to Last.fm API with error handling.

        Args:
            method: Last.fm API method name
            params: Additional parameters for the request
            authenticated: Whether to sign the request

        Returns:
            Parsed JSON response

        Raises:
            LastFmAPIError: For API errors
            LastFmConnectionError: For network errors
            LastFmRateLimitError: For rate limit errors
        """
        self._respect_rate_limit()

        request_params = params.copy() if params else {}
        request_params.update({
            'method': method,
            'api_key': self.config.api_key,
            'format': 'json',
        })

        if authenticated:
            request_params['api_sig'] = self._build_signature(request_params)

        logger.debug(
            f"Making Last.fm API request: {method}",
            extra={
                'method': method,
                'params_count': len(request_params),
            }
        )

        try:
            session = self._get_session()
            response = session.get(
                self.BASE_URL,
                params=request_params,
                timeout=self.REQUEST_TIMEOUT
            )

            logger.debug(
                f"Last.fm API response received",
                extra={
                    'method': method,
                    'status_code': response.status_code,
                    'response_time_ms': int(response.elapsed.total_seconds() * 1000),
                }
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise LastFmRateLimitError(
                    "Last.fm API rate limit exceeded",
                    retry_after=retry_after
                )

            response.raise_for_status()

            data = response.json()

            if 'error' in data:
                error_code = data.get('error')
                error_message = data.get('message', 'Unknown error')

                logger.error(
                    f"Last.fm API error",
                    extra={
                        'method': method,
                        'error_code': error_code,
                        'error_message': error_message,
                    }
                )

                if error_code in [4, 10, 13]:
                    raise LastFmAuthenticationError(
                        f"Authentication failed: {error_message}",
                        error_code=error_code
                    )
                elif error_code == 6:
                    raise LastFmUserNotFoundError(
                        f"User not found: {error_message}",
                        error_code=error_code
                    )
                else:
                    raise LastFmAPIError(
                        f"Last.fm API error: {error_message}",
                        error_code=error_code,
                        response=data
                    )

            return data

        except requests.exceptions.Timeout as e:
            logger.error(f"Last.fm API request timeout: {method}")
            raise LastFmConnectionError(
                f"Request to Last.fm timed out after {self.REQUEST_TIMEOUT} seconds"
            ) from e

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Last.fm API connection error: {method}")
            raise LastFmConnectionError(
                "Failed to connect to Last.fm API"
            ) from e

        except requests.exceptions.RequestException as e:
            logger.error(f"Last.fm API request failed: {method}", exc_info=True)
            raise LastFmConnectionError(
                f"Request to Last.fm failed: {str(e)}"
            ) from e

        except ValueError as e:
            logger.error(f"Last.fm API returned invalid JSON: {method}")
            raise LastFmInvalidResponseError(
                "Last.fm API returned invalid JSON response"
            ) from e

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """
        Test connection to Last.fm API and validate credentials.

        Returns:
            Tuple of (success, error_message)
        """
        is_valid, error_msg = self.config.validate()
        if not is_valid:
            return False, f"Configuration error: {error_msg}"

        try:
            logger.info(
                "Testing Last.fm API connection",
                extra={'username': self.config.username}
            )

            user_info = self.get_user_info(self.config.username)

            if not user_info:
                return False, "Failed to retrieve user information"

            logger.info(
                "Last.fm connection test successful",
                extra={
                    'username': self.config.username,
                    'playcount': user_info.get('playcount', 0)
                }
            )

            return True, None

        except LastFmUserNotFoundError as e:
            logger.error(f"Last.fm user not found: {self.config.username}")
            return False, f"User '{self.config.username}' not found on Last.fm"

        except LastFmAuthenticationError as e:
            logger.error("Last.fm authentication failed")
            return False, f"Authentication failed: {e.message}"

        except LastFmRateLimitError as e:
            logger.warning("Last.fm rate limit exceeded during connection test")
            return False, f"Rate limit exceeded. Please try again in {e.retry_after} seconds."

        except LastFmConnectionError as e:
            logger.error("Last.fm connection error")
            return False, f"Connection error: {e.message}"

        except LastFmAPIError as e:
            logger.error(f"Last.fm API error during connection test: {e.message}")
            return False, f"API error: {e.message}"

        except Exception as e:
            logger.error("Unexpected error during Last.fm connection test", exc_info=True)
            return False, f"Unexpected error: {str(e)}"

    def get_user_info(self, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Get basic user information from Last.fm.

        Args:
            username: Last.fm username (uses config username if not provided)

        Returns:
            Dictionary with user information

        Raises:
            LastFmAPIError: For API errors
        """
        username = username or self.config.username

        if not username:
            raise LastFmAPIError("No username provided")

        data = self._make_request(
            method='user.getInfo',
            params={'user': username}
        )

        user_data = data.get('user', {})

        return {
            'name': user_data.get('name'),
            'realname': user_data.get('realname'),
            'url': user_data.get('url'),
            'country': user_data.get('country'),
            'playcount': int(user_data.get('playcount', 0)),
            'registered': user_data.get('registered', {}).get('unixtime'),
            'subscriber': bool(int(user_data.get('subscriber', 0))),
        }

    def get_recent_tracks(
        self,
        username: Optional[str] = None,
        from_timestamp: Optional[int] = None,
        to_timestamp: Optional[int] = None,
        limit: int = 200,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get recent tracks for a user.

        Args:
            username: Last.fm username (uses config username if not provided)
            from_timestamp: Unix timestamp to fetch tracks from
            to_timestamp: Unix timestamp to fetch tracks until
            limit: Number of tracks per page (max 200)
            page: Page number for pagination

        Returns:
            Dictionary with tracks and pagination info

        Raises:
            LastFmAPIError: For API errors
        """
        username = username or self.config.username

        if not username:
            raise LastFmAPIError("No username provided")

        if limit > 200:
            limit = 200

        params = {
            'user': username,
            'limit': limit,
            'page': page,
        }

        if from_timestamp:
            params['from'] = from_timestamp

        if to_timestamp:
            params['to'] = to_timestamp

        data = self._make_request(
            method='user.getRecentTracks',
            params=params
        )

        return data

    def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()