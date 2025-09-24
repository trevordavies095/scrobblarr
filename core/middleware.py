"""
Middleware for request/response logging and error handling.
"""
import json
import logging
import time
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .exceptions import ScrobblarrError


class LoggingMiddleware(MiddlewareMixin):
    """Middleware for logging HTTP requests and responses."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('scrobblarr.middleware')

    def process_request(self, request):
        """Log incoming requests."""
        # Generate unique request ID for tracing
        request.request_id = str(uuid.uuid4())[:8]
        request.start_time = time.time()

        # Log request details
        self.logger.info(
            f"Request started: {request.method} {request.get_full_path()}",
            extra={
                'request_id': request.request_id,
                'method': request.method,
                'path': request.path,
                'full_path': request.get_full_path(),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': self._get_client_ip(request),
                'content_type': request.content_type,
                'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
            }
        )

        # Log request body for API endpoints (excluding sensitive data)
        if request.path.startswith('/api/') and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if hasattr(request, 'body') and request.body:
                    body_str = request.body.decode('utf-8')
                    # Don't log sensitive information
                    if 'password' not in body_str.lower() and 'token' not in body_str.lower():
                        self.logger.debug(
                            f"Request body: {body_str[:1000]}",
                            extra={'request_id': request.request_id}
                        )
            except Exception:
                pass

    def process_response(self, request, response):
        """Log response details."""
        if hasattr(request, 'start_time'):
            duration = (time.time() - request.start_time) * 1000  # milliseconds
        else:
            duration = 0

        request_id = getattr(request, 'request_id', 'unknown')

        log_data = {
            'request_id': request_id,
            'status_code': response.status_code,
            'duration_ms': round(duration, 2),
            'content_type': response.get('Content-Type', ''),
            'content_length': len(response.content) if hasattr(response, 'content') else 0
        }

        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
            message = f"Request completed with server error: {response.status_code}"
        elif response.status_code >= 400:
            log_level = logging.WARNING
            message = f"Request completed with client error: {response.status_code}"
        elif duration > 5000:  # Slow requests (>5 seconds)
            log_level = logging.WARNING
            message = f"Slow request completed: {duration:.0f}ms"
        else:
            log_level = logging.INFO
            message = f"Request completed successfully: {response.status_code}"

        self.logger.log(log_level, message, extra=log_data)

        # Log response content for errors (API endpoints only)
        if (response.status_code >= 400 and
            request.path.startswith('/api/') and
            hasattr(response, 'content')):
            try:
                content_preview = response.content.decode('utf-8')[:500]
                self.logger.debug(
                    f"Error response content: {content_preview}",
                    extra={'request_id': request_id}
                )
            except Exception:
                pass

        return response

    def process_exception(self, request, exception):
        """Log unhandled exceptions."""
        request_id = getattr(request, 'request_id', 'unknown')

        self.logger.error(
            f"Unhandled exception in request",
            exc_info=True,
            extra={
                'request_id': request_id,
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'method': request.method,
                'path': request.path,
                'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
            }
        )

        # Return JSON error for API endpoints
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'Internal server error',
                'request_id': request_id
            }, status=500)

        return None

    def _get_client_ip(self, request):
        """Get the real client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ErrorHandlingMiddleware(MiddlewareMixin):
    """Middleware for handling custom exceptions and converting them to appropriate HTTP responses."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('scrobblarr.errors')

    def process_exception(self, request, exception):
        """Handle custom exceptions."""
        request_id = getattr(request, 'request_id', 'unknown')

        if isinstance(exception, ScrobblarrError):
            self.logger.warning(
                f"Application error: {exception.message}",
                extra={
                    'request_id': request_id,
                    'error_code': exception.error_code,
                    'error_details': exception.details,
                    'method': request.method,
                    'path': request.path
                }
            )

            # Return JSON error for API endpoints
            if request.path.startswith('/api/'):
                status_code = getattr(exception, 'status_code', 400)
                return JsonResponse({
                    'error': exception.message,
                    'error_code': exception.error_code,
                    'details': exception.details,
                    'request_id': request_id
                }, status=status_code)

        return None


class SecurityMiddleware(MiddlewareMixin):
    """Middleware for security-related logging."""

    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('django.security')

    def process_request(self, request):
        """Log potential security issues."""
        # Log suspicious requests
        suspicious_patterns = [
            'wp-admin', 'wp-login', 'phpmyadmin', 'admin.php',
            'xmlrpc.php', '.env', 'config.php', 'setup.php'
        ]

        path_lower = request.path.lower()
        if any(pattern in path_lower for pattern in suspicious_patterns):
            self.logger.warning(
                f"Suspicious request path: {request.path}",
                extra={
                    'remote_addr': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'method': request.method,
                    'path': request.path
                }
            )

        # Log requests with unusual headers
        if 'HTTP_X_REQUESTED_WITH' in request.META and request.META['HTTP_X_REQUESTED_WITH'] != 'XMLHttpRequest':
            self.logger.info(
                f"Non-AJAX request with X-Requested-With header",
                extra={
                    'x_requested_with': request.META['HTTP_X_REQUESTED_WITH'],
                    'path': request.path
                }
            )

        return None