"""
Custom exception handlers for DRF API responses.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from .exceptions import APIError


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF that handles our custom APIError exceptions.
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)

    # Handle our custom APIError exceptions
    if isinstance(exc, APIError):
        error_data = {
            'error': {
                'code': exc.error_code or 'API_ERROR',
                'message': str(exc.message),
                'details': exc.details
            }
        }
        return Response(error_data, status=exc.status_code)

    # Return the default DRF response for other exceptions
    return response