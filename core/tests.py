"""
Tests for core error handling, logging, and health checks.
"""
import json
import logging
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, Client
from django.http import HttpRequest, HttpResponse
from django.db import connection
from django.urls import reverse
from rest_framework.test import APITestCase

from .exceptions import (
    ScrobblarrError, DataValidationError, ImportError, APIError,
    ExternalServiceError, DataIntegrityError, ConfigurationError,
    TaskError, RateLimitError
)
from .middleware import LoggingMiddleware, ErrorHandlingMiddleware, SecurityMiddleware
from music.models import Artist, Album, Track, Scrobble


class CustomExceptionTests(TestCase):
    """Test custom exception classes."""

    def setUp(self):
        self.logger_patcher = patch('core.exceptions.logging.getLogger')
        self.mock_logger = self.logger_patcher.start()

    def tearDown(self):
        self.logger_patcher.stop()

    def test_scrobblarr_error_creation(self):
        """Test basic ScrobblarrError creation and logging."""
        error = ScrobblarrError(
            message="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            logger_name="test_logger"
        )

        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(error.details, {"key": "value"})
        self.mock_logger.return_value.error.assert_called_once()

    def test_data_validation_error(self):
        """Test DataValidationError with field information."""
        error = DataValidationError(
            message="Invalid data",
            field="email",
            value="invalid-email"
        )

        self.assertEqual(error.message, "Invalid data")
        self.assertEqual(error.error_code, "VALIDATION_ERROR")
        self.assertEqual(error.field, "email")
        self.assertEqual(error.value, "invalid-email")
        self.assertIn("field", error.details)
        self.assertIn("value", error.details)

    def test_import_error(self):
        """Test ImportError with row and file information."""
        error = ImportError(
            message="Import failed",
            row_number=42,
            file_path="/path/to/file.csv"
        )

        self.assertEqual(error.message, "Import failed")
        self.assertEqual(error.error_code, "IMPORT_ERROR")
        self.assertEqual(error.row_number, 42)
        self.assertEqual(error.file_path, "/path/to/file.csv")
        self.assertIn("row_number", error.details)
        self.assertIn("file_path", error.details)

    def test_api_error(self):
        """Test APIError with status code."""
        error = APIError(
            message="API error",
            status_code=400
        )

        self.assertEqual(error.message, "API error")
        self.assertEqual(error.error_code, "API_ERROR")
        self.assertEqual(error.status_code, 400)
        self.assertIn("status_code", error.details)


class LoggingMiddlewareTests(TestCase):
    """Test logging middleware functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LoggingMiddleware(lambda request: HttpResponse("OK"))

    @patch('core.middleware.logging.getLogger')
    def test_process_request_logging(self, mock_get_logger):
        """Test that requests are properly logged."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/test/')
        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, 'request_id'))
        self.assertTrue(hasattr(request, 'start_time'))
        mock_logger.info.assert_called_once()

    @patch('core.middleware.logging.getLogger')
    def test_process_response_logging(self, mock_get_logger):
        """Test that responses are properly logged."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/test/')
        request.request_id = "test-id"
        request.start_time = 0

        response = HttpResponse("OK", status=200)

        with patch('time.time', return_value=1):
            result = self.middleware.process_response(request, response)

        self.assertEqual(result, response)
        mock_logger.log.assert_called()

    @patch('core.middleware.logging.getLogger')
    def test_process_exception_logging(self, mock_get_logger):
        """Test that exceptions are properly logged."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/api/test/')
        request.request_id = "test-id"
        exception = Exception("Test exception")

        result = self.middleware.process_exception(request, exception)

        mock_logger.error.assert_called_once()
        # Should return JSON error for API endpoints
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 500)


    def test_get_client_ip(self):
        """Test client IP extraction."""
        # Test with X-Forwarded-For header
        request = self.factory.get('/test/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.1, 10.0.0.1'
        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

        # Test with REMOTE_ADDR
        request = self.factory.get('/test/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')


class ErrorHandlingMiddlewareTests(TestCase):
    """Test error handling middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ErrorHandlingMiddleware(lambda request: HttpResponse("OK"))

    @patch('core.middleware.logging.getLogger')
    def test_scrobblarr_error_handling(self, mock_get_logger):
        """Test handling of ScrobblarrError."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/api/test/')
        request.request_id = "test-id"
        error = APIError("Test API error", status_code=400)

        result = self.middleware.process_exception(request, error)

        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 400)
        mock_logger.warning.assert_called_once()

        # Check JSON response content
        response_data = json.loads(result.content)
        self.assertEqual(response_data['error'], "Test API error")
        self.assertEqual(response_data['error_code'], "API_ERROR")

    @patch('core.middleware.logging.getLogger')
    def test_non_api_error_handling(self, mock_get_logger):
        """Test that non-API requests don't get JSON responses."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/some-page/')
        request.request_id = "test-id"
        error = ScrobblarrError("Test error")

        result = self.middleware.process_exception(request, error)

        # Should return None for non-API requests
        self.assertIsNone(result)
        mock_logger.warning.assert_called_once()


class SecurityMiddlewareTests(TestCase):
    """Test security middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityMiddleware(lambda request: HttpResponse("OK"))

    @patch('core.middleware.logging.getLogger')
    def test_suspicious_path_logging(self, mock_get_logger):
        """Test logging of suspicious request paths."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        suspicious_paths = [
            '/wp-admin/',
            '/wp-login.php',
            '/phpmyadmin/',
            '/admin.php',
            '/.env'
        ]

        for path in suspicious_paths:
            request = self.factory.get(path)
            self.middleware.process_request(request)

        # Should log warning for each suspicious path
        self.assertEqual(mock_logger.warning.call_count, len(suspicious_paths))

    @patch('core.middleware.logging.getLogger')
    def test_normal_path_no_logging(self, mock_get_logger):
        """Test that normal paths don't trigger security warnings."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        request = self.factory.get('/api/artists/')
        result = self.middleware.process_request(request)

        self.assertIsNone(result)
        mock_logger.warning.assert_not_called()


class HealthCheckTests(APITestCase):
    """Test health check endpoints."""

    def setUp(self):
        self.client = Client()
        # Create test data
        self.artist = Artist.objects.create(name="Test Artist")
        self.album = Album.objects.create(name="Test Album", artist=self.artist)
        self.track = Track.objects.create(name="Test Track", artist=self.artist, album=self.album)

    def test_health_check_healthy(self):
        """Test health check returns healthy status."""
        response = self.client.get(reverse('core:health_check'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
        self.assertIn('checks', data)
        self.assertIn('response_time_ms', data)

        # Check individual health checks
        self.assertEqual(data['checks']['database']['status'], 'healthy')
        self.assertEqual(data['checks']['data']['status'], 'healthy')
        self.assertIn('counts', data['checks']['data'])

    def test_readiness_check(self):
        """Test readiness check endpoint."""
        response = self.client.get(reverse('core:readiness_check'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'ready')
        self.assertIn('timestamp', data)

    def test_liveness_check(self):
        """Test liveness check endpoint."""
        response = self.client.get(reverse('core:liveness_check'))

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data['status'], 'alive')
        self.assertIn('timestamp', data)

    @patch('django.db.connection.cursor')
    def test_health_check_database_failure(self, mock_cursor):
        """Test health check with database failure."""
        mock_cursor.side_effect = Exception("Database connection failed")

        response = self.client.get(reverse('core:health_check'))

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['status'], 'unhealthy')
        self.assertEqual(data['checks']['database']['status'], 'unhealthy')

    @patch('django.db.connection.cursor')
    def test_readiness_check_no_migrations(self, mock_cursor):
        """Test readiness check with no migrations."""
        mock_cursor.return_value.__enter__.return_value.fetchone.return_value = [0]

        response = self.client.get(reverse('core:readiness_check'))

        self.assertEqual(response.status_code, 503)
        data = response.json()

        self.assertEqual(data['status'], 'not_ready')
        self.assertIn('Database not initialized', data['message'])


class LoggingIntegrationTests(TestCase):
    """Integration tests for logging functionality."""

    def setUp(self):
        self.client = Client()

    def test_health_check_logging(self):
        """Test that health checks are logged."""
        with self.assertLogs('core', level='INFO') as cm:
            response = self.client.get(reverse('core:health_check'))

        # Should have logged health check request and completion
        self.assertTrue(any('Health check requested' in log for log in cm.output))
        self.assertTrue(any('Health check completed' in log for log in cm.output))