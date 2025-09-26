"""
Tests for Last.fm API integration (Story 31).
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.conf import settings

from music.lastfm.config import LastFmConfig, get_lastfm_config
from music.lastfm.client import LastFmClient
from music.lastfm.exceptions import (
    LastFmAPIError,
    LastFmAuthenticationError,
    LastFmConnectionError,
    LastFmRateLimitError,
    LastFmUserNotFoundError,
)


class LastFmConfigTest(TestCase):
    """Test Last.fm configuration management."""

    @override_settings(
        LASTFM_API_KEY='test_api_key_12345',
        LASTFM_API_SECRET='test_api_secret_67890',
        LASTFM_USERNAME='testuser',
        SYNC_FREQUENCY='hourly'
    )
    def test_config_properly_configured(self):
        """Test configuration with all required settings."""
        config = LastFmConfig()

        self.assertEqual(config.api_key, 'test_api_key_12345')
        self.assertEqual(config.api_secret, 'test_api_secret_67890')
        self.assertEqual(config.username, 'testuser')
        self.assertEqual(config.sync_frequency, 'hourly')
        self.assertTrue(config.is_configured())

    @override_settings(
        LASTFM_API_KEY='',
        LASTFM_API_SECRET='',
        LASTFM_USERNAME=''
    )
    def test_config_not_configured(self):
        """Test configuration with missing settings."""
        config = LastFmConfig()

        self.assertFalse(config.is_configured())

    @override_settings(
        LASTFM_API_KEY='short',
        LASTFM_API_SECRET='test_api_secret_67890',
        LASTFM_USERNAME='testuser'
    )
    def test_config_validation_short_api_key(self):
        """Test validation fails with short API key."""
        config = LastFmConfig()

        is_valid, error_message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('API key', error_message)

    @override_settings(
        LASTFM_API_KEY='test_api_key_12345',
        LASTFM_API_SECRET='test_api_secret_67890',
        LASTFM_USERNAME='testuser',
        SYNC_FREQUENCY='invalid_frequency'
    )
    def test_config_validation_invalid_frequency(self):
        """Test validation fails with invalid sync frequency."""
        config = LastFmConfig()

        is_valid, error_message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('frequency', error_message.lower())

    @override_settings(LASTFM_API_KEY='test_api_key_12345')
    def test_masked_api_key(self):
        """Test API key masking for display."""
        config = LastFmConfig()

        masked = config.get_masked_api_key()

        self.assertIn('***', masked)
        self.assertNotEqual(masked, config.api_key)
        self.assertTrue(masked.startswith('tes'))
        self.assertTrue(masked.endswith('345'))

    def test_masked_api_key_empty(self):
        """Test API key masking when not configured."""
        config = LastFmConfig()

        masked = config.get_masked_api_key()

        self.assertEqual(masked, "Not configured")

    @override_settings(
        LASTFM_API_KEY='test_api_key_12345',
        LASTFM_API_SECRET='test_api_secret_67890',
        LASTFM_USERNAME='testuser'
    )
    def test_get_status(self):
        """Test configuration status reporting."""
        config = LastFmConfig()

        status = config.get_status()

        self.assertTrue(status['configured'])
        self.assertTrue(status['has_api_key'])
        self.assertTrue(status['has_api_secret'])
        self.assertTrue(status['has_username'])
        self.assertEqual(status['username'], 'testuser')
        self.assertIn('***', status['masked_api_key'])


class LastFmClientTest(TestCase):
    """Test Last.fm API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = LastFmConfig()
        self.config._api_key = 'test_api_key_12345'
        self.config._api_secret = 'test_api_secret_67890'
        self.config._username = 'testuser'

    def test_client_initialization(self):
        """Test client initialization."""
        client = LastFmClient(self.config)

        self.assertEqual(client.config, self.config)
        self.assertIsNone(client._session)

    def test_client_context_manager(self):
        """Test client can be used as context manager."""
        with LastFmClient(self.config) as client:
            self.assertIsNotNone(client)
            self.assertEqual(client.config, self.config)

    @patch('music.lastfm.client.requests.Session')
    def test_get_session_creates_session(self, mock_session_class):
        """Test session creation with retry configuration."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        session = client._get_session()

        self.assertIsNotNone(session)
        mock_session_class.assert_called_once()
        mock_session.mount.assert_called()

    @patch('music.lastfm.client.requests.Session')
    def test_make_request_success(self, mock_session_class):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user': {'name': 'testuser'}}
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        result = client._make_request('user.getInfo', {'user': 'testuser'})

        self.assertIn('user', result)
        self.assertEqual(result['user']['name'], 'testuser')

    @patch('music.lastfm.client.requests.Session')
    def test_make_request_api_error(self, mock_session_class):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': 6,
            'message': 'User not found'
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)

        with self.assertRaises(LastFmUserNotFoundError) as context:
            client._make_request('user.getInfo', {'user': 'nonexistent'})

        self.assertIn('User not found', str(context.exception))

    @patch('music.lastfm.client.requests.Session')
    def test_make_request_authentication_error(self, mock_session_class):
        """Test authentication error handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': 4,
            'message': 'Authentication Failed'
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)

        with self.assertRaises(LastFmAuthenticationError):
            client._make_request('user.getInfo', {'user': 'testuser'})

    @patch('music.lastfm.client.requests.Session')
    def test_make_request_rate_limit_error(self, mock_session_class):
        """Test rate limit error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'Retry-After': '60'}
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)

        with self.assertRaises(LastFmRateLimitError) as context:
            client._make_request('user.getInfo', {'user': 'testuser'})

        self.assertEqual(context.exception.retry_after, 60)

    @patch('music.lastfm.client.requests.Session')
    def test_get_user_info_success(self, mock_session_class):
        """Test successful user info retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'user': {
                'name': 'testuser',
                'realname': 'Test User',
                'url': 'https://www.last.fm/user/testuser',
                'country': 'US',
                'playcount': '12345',
                'registered': {'unixtime': '1234567890'},
                'subscriber': '0'
            }
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        user_info = client.get_user_info('testuser')

        self.assertEqual(user_info['name'], 'testuser')
        self.assertEqual(user_info['playcount'], 12345)
        self.assertFalse(user_info['subscriber'])

    @patch('music.lastfm.client.requests.Session')
    def test_test_connection_success(self, mock_session_class):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'user': {
                'name': 'testuser',
                'playcount': '12345'
            }
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        success, error_message = client.test_connection()

        self.assertTrue(success)
        self.assertIsNone(error_message)

    @patch('music.lastfm.client.requests.Session')
    def test_test_connection_failure(self, mock_session_class):
        """Test failed connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': 6,
            'message': 'User not found'
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        success, error_message = client.test_connection()

        self.assertFalse(success)
        self.assertIsNotNone(error_message)
        self.assertIn('not found', error_message.lower())

    @patch('music.lastfm.client.requests.Session')
    def test_get_recent_tracks(self, mock_session_class):
        """Test recent tracks retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'recenttracks': {
                'track': [
                    {
                        'name': 'Test Track',
                        'artist': {'#text': 'Test Artist'}
                    }
                ]
            }
        }
        mock_response.elapsed.total_seconds.return_value = 0.5

        mock_session = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = LastFmClient(self.config)
        result = client.get_recent_tracks('testuser', limit=50)

        self.assertIn('recenttracks', result)

    def test_build_signature(self):
        """Test API signature building."""
        client = LastFmClient(self.config)

        params = {
            'method': 'user.getInfo',
            'user': 'testuser',
            'api_key': 'test_key'
        }

        signature = client._build_signature(params)

        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 32)