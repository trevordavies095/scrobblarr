"""
Configuration management for Last.fm API integration.
"""
import logging
from typing import Optional, Dict, Any
from django.conf import settings


logger = logging.getLogger('music.lastfm')


class LastFmConfig:
    """
    Manages Last.fm API configuration and validation.

    Handles environment variables, validation, and secure access
    to Last.fm credentials without exposing them in logs.
    """

    def __init__(self):
        self._api_key = getattr(settings, 'LASTFM_API_KEY', '')
        self._api_secret = getattr(settings, 'LASTFM_API_SECRET', '')
        self._username = getattr(settings, 'LASTFM_USERNAME', '')
        self._sync_frequency = getattr(settings, 'SYNC_FREQUENCY', 'daily')

    @property
    def api_key(self) -> str:
        """Get API key (never log this value)."""
        return self._api_key

    @property
    def api_secret(self) -> str:
        """Get API secret (never log this value)."""
        return self._api_secret

    @property
    def username(self) -> str:
        """Get Last.fm username."""
        return self._username

    @property
    def sync_frequency(self) -> str:
        """Get sync frequency setting."""
        return self._sync_frequency

    def is_configured(self) -> bool:
        """
        Check if Last.fm is properly configured.

        Returns:
            True if API key and username are set, False otherwise
        """
        return bool(self._api_key and self._username)

    def get_masked_api_key(self) -> str:
        """
        Get masked API key for display purposes.

        Returns:
            Masked string like "abc***xyz" or "Not configured"
        """
        if not self._api_key:
            return "Not configured"

        if len(self._api_key) <= 6:
            return "****hidden****"

        return f"{self._api_key[:3]}***{self._api_key[-3:]}"

    def get_status(self) -> Dict[str, Any]:
        """
        Get configuration status summary (safe for logging/display).

        Returns:
            Dictionary with configuration status information
        """
        return {
            'configured': self.is_configured(),
            'has_api_key': bool(self._api_key),
            'has_api_secret': bool(self._api_secret),
            'has_username': bool(self._username),
            'username': self._username if self._username else None,
            'masked_api_key': self.get_masked_api_key(),
            'sync_frequency': self._sync_frequency,
        }

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration completeness.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self._api_key:
            return False, "Last.fm API key is not configured"

        if not self._api_secret:
            return False, "Last.fm API secret is not configured"

        if not self._username:
            return False, "Last.fm username is not configured"

        if len(self._api_key) < 10:
            return False, "Last.fm API key appears to be invalid (too short)"

        if len(self._api_secret) < 10:
            return False, "Last.fm API secret appears to be invalid (too short)"

        valid_frequencies = ['manual', 'hourly', 'daily']
        if self._sync_frequency not in valid_frequencies:
            return False, f"Invalid sync frequency: {self._sync_frequency}"

        return True, None

    def log_status(self):
        """Log configuration status (safely, without credentials)."""
        status = self.get_status()
        logger.info(
            "Last.fm configuration status",
            extra={
                'configured': status['configured'],
                'has_username': status['has_username'],
                'username': status['username'],
                'sync_frequency': status['sync_frequency'],
            }
        )


def get_lastfm_config() -> LastFmConfig:
    """
    Get Last.fm configuration instance.

    Returns:
        LastFmConfig instance
    """
    return LastFmConfig()