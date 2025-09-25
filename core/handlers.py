"""
Custom exception handlers for DRF API responses.

Provides consistent error formatting across all API endpoints following Story 17 specification.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError,
    NotFound,
    MethodNotAllowed,
    ParseError,
    PermissionDenied,
    Throttled
)
from django.http import Http404
from django.conf import settings
import logging

from .exceptions import APIError, ScrobblarrError

logger = logging.getLogger('scrobblarr.errors')


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that provides consistent error formatting.

    Handles:
    - Custom APIError and ScrobblarrError exceptions
    - DRF validation errors
    - Rate limiting (Throttled) errors
    - Standard HTTP errors (404, 405, etc.)
    - Unexpected exceptions with proper logging
    """
    # Get request context for logging
    request = context.get('request')
    request_id = getattr(request, 'request_id', 'unknown') if request else 'unknown'

    # Handle our custom exceptions first
    if isinstance(exc, APIError):
        error_data = {
            'error': {
                'code': exc.error_code or 'API_ERROR',
                'message': str(exc.message),
                'details': exc.details
            }
        }

        # Add request_id for tracing
        if request_id != 'unknown':
            error_data['request_id'] = request_id

        return Response(error_data, status=exc.status_code)

    # Handle other ScrobblarrError exceptions
    if isinstance(exc, ScrobblarrError):
        error_data = {
            'error': {
                'code': exc.error_code or 'APPLICATION_ERROR',
                'message': str(exc.message),
                'details': exc.details
            }
        }

        if request_id != 'unknown':
            error_data['request_id'] = request_id

        return Response(error_data, status=500)

    # Call DRF's default exception handler
    response = exception_handler(exc, context)

    if response is not None:
        # Customize DRF error responses to match our format
        if isinstance(exc, ValidationError):
            error_data = {
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': 'Request validation failed',
                    'details': response.data
                }
            }

        elif isinstance(exc, Throttled):
            error_data = {
                'error': {
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'message': f'Rate limit exceeded. Try again in {exc.wait} seconds.',
                    'details': {
                        'throttle_scope': getattr(exc, 'scope', 'unknown'),
                        'retry_after': exc.wait
                    }
                }
            }

        elif isinstance(exc, NotFound) or isinstance(exc, Http404):
            error_data = {
                'error': {
                    'code': 'NOT_FOUND',
                    'message': 'The requested resource was not found',
                    'details': {}
                }
            }

        elif isinstance(exc, MethodNotAllowed):
            error_data = {
                'error': {
                    'code': 'METHOD_NOT_ALLOWED',
                    'message': f'Method {request.method} not allowed for this endpoint',
                    'details': {
                        'method': request.method,
                        'allowed_methods': exc.detail.get('allowed_methods', [])
                    }
                }
            }

        elif isinstance(exc, ParseError):
            error_data = {
                'error': {
                    'code': 'PARSE_ERROR',
                    'message': 'Malformed request data',
                    'details': {'detail': str(exc.detail)}
                }
            }

        elif isinstance(exc, PermissionDenied):
            error_data = {
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': 'You do not have permission to perform this action',
                    'details': {}
                }
            }

        else:
            # Generic error formatting for other DRF errors
            error_data = {
                'error': {
                    'code': 'API_ERROR',
                    'message': str(exc) if hasattr(exc, 'detail') else 'An API error occurred',
                    'details': response.data if isinstance(response.data, dict) else {'detail': response.data}
                }
            }

        # Add request_id for tracing
        if request_id != 'unknown':
            error_data['request_id'] = request_id

        # Log the error with context
        logger.warning(
            f"API error: {exc.__class__.__name__}: {str(exc)}",
            extra={
                'request_id': request_id,
                'error_code': error_data['error']['code'],
                'status_code': response.status_code,
                'path': request.path if request else 'unknown',
                'method': request.method if request else 'unknown',
                'user': str(request.user) if request and hasattr(request, 'user') else 'unknown'
            }
        )

        return Response(error_data, status=response.status_code)

    # Handle unexpected exceptions not caught by DRF
    logger.error(
        f"Unhandled exception: {exc.__class__.__name__}: {str(exc)}",
        exc_info=True,
        extra={
            'request_id': request_id,
            'path': request.path if request else 'unknown',
            'method': request.method if request else 'unknown',
            'user': str(request.user) if request and hasattr(request, 'user') else 'unknown'
        }
    )

    # Return a properly formatted 500 error
    error_data = {
        'error': {
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'An internal server error occurred',
            'details': {}
        }
    }

    # Include exception details in development
    if settings.DEBUG:
        error_data['error']['details'] = {
            'exception_type': exc.__class__.__name__,
            'exception_message': str(exc)
        }

    if request_id != 'unknown':
        error_data['request_id'] = request_id

    return Response(error_data, status=500)