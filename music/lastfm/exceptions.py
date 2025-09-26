"""
Custom exceptions for Last.fm API integration.
"""


class LastFmAPIError(Exception):
    """Base exception for Last.fm API errors."""

    def __init__(self, message, error_code=None, response=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.response = response


class LastFmAuthenticationError(LastFmAPIError):
    """Exception raised for authentication failures."""
    pass


class LastFmConnectionError(LastFmAPIError):
    """Exception raised for network/connection issues."""
    pass


class LastFmRateLimitError(LastFmAPIError):
    """Exception raised when API rate limit is exceeded."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class LastFmInvalidResponseError(LastFmAPIError):
    """Exception raised when API returns invalid/unexpected data."""
    pass


class LastFmUserNotFoundError(LastFmAPIError):
    """Exception raised when specified user doesn't exist."""
    pass