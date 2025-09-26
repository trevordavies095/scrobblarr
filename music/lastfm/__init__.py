"""
Last.fm API integration package for Scrobblarr.

This package provides Last.fm API client functionality including:
- API authentication and credential management
- Connection testing and validation
- Scrobble data fetching and synchronization
"""

from .client import LastFmClient
from .exceptions import (
    LastFmAPIError,
    LastFmAuthenticationError,
    LastFmConnectionError,
    LastFmRateLimitError,
)

__all__ = [
    'LastFmClient',
    'LastFmAPIError',
    'LastFmAuthenticationError',
    'LastFmConnectionError',
    'LastFmRateLimitError',
]