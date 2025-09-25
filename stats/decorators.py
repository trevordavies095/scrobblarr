"""
Validation decorators for stats API endpoints.

Provides reusable decorators for common parameter validation patterns,
ensuring consistent error handling and validation logic across endpoints.
"""
from functools import wraps
from .validators import (
    validate_time_period,
    validate_date_params,
    validate_limit,
    validate_granularity,
    validate_story_compliance
)


def validate_time_period_param(default_period='all'):
    """
    Decorator to validate time period parameter.

    Args:
        default_period (str): Default period if not provided

    Usage:
        @validate_time_period_param()
        def my_view(self, request):
            period = request.validated_params['period']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            period = request.query_params.get('period', default_period)
            validated_period = validate_time_period(period)

            # Store validated parameters in request
            if not hasattr(request, 'validated_params'):
                request.validated_params = {}
            request.validated_params['period'] = validated_period

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_date_range_params():
    """
    Decorator to validate date range parameters (from_date, to_date).

    Usage:
        @validate_date_range_params()
        def my_view(self, request):
            from_date = request.validated_params['from_date']
            to_date = request.validated_params['to_date']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            from_date_str = request.query_params.get('from_date')
            to_date_str = request.query_params.get('to_date')

            from_date, to_date = validate_date_params(from_date_str, to_date_str)

            # Store validated parameters in request
            if not hasattr(request, 'validated_params'):
                request.validated_params = {}
            request.validated_params['from_date'] = from_date
            request.validated_params['to_date'] = to_date

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_pagination_param(default_limit=10, max_limit=100):
    """
    Decorator to validate pagination parameters.

    Args:
        default_limit (int): Default limit value
        max_limit (int): Maximum allowed limit

    Usage:
        @validate_pagination_param(max_limit=50)
        def my_view(self, request):
            limit = request.validated_params['limit']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            limit = request.query_params.get('limit')
            validated_limit = validate_limit(
                limit,
                parameter_name='limit',
                max_value=max_limit,
                default=default_limit
            )

            # Store validated parameters in request
            if not hasattr(request, 'validated_params'):
                request.validated_params = {}
            request.validated_params['limit'] = validated_limit

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_granularity_param():
    """
    Decorator to validate granularity parameter for chart endpoints.

    Usage:
        @validate_granularity_param()
        def my_view(self, request):
            granularity = request.validated_params['granularity']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            granularity = request.query_params.get('granularity')
            validated_granularity = validate_granularity(granularity)

            # Store validated parameters in request
            if not hasattr(request, 'validated_params'):
                request.validated_params = {}
            request.validated_params['granularity'] = validated_granularity

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_api_params(endpoint_name):
    """
    Decorator to validate all parameters for a specific API endpoint.
    Provides comprehensive validation based on story requirements.

    Args:
        endpoint_name (str): Name of the endpoint/story for validation rules

    Usage:
        @validate_api_params('recent_tracks')
        def recent_tracks(self, request):
            # All parameters are pre-validated and available in request.validated_params
            limit = request.validated_params['limit']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Get all query parameters
            params = {
                'period': request.query_params.get('period'),
                'limit': request.query_params.get('limit'),
                'from_date': request.query_params.get('from_date'),
                'to_date': request.query_params.get('to_date'),
                'granularity': request.query_params.get('granularity'),
            }

            # Validate based on story compliance
            validated_params = validate_story_compliance(endpoint_name, **params)

            # Store validated parameters in request
            request.validated_params = validated_params

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def validate_params(**validation_config):
    """
    Generic decorator for custom parameter validation.

    Args:
        **validation_config: Configuration for parameter validation

    Example:
        @validate_params(
            period={'required': False, 'default': 'all'},
            limit={'required': False, 'default': 10, 'max': 50}
        )
        def my_view(self, request):
            period = request.validated_params['period']
            limit = request.validated_params['limit']
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            validated_params = {}

            for param_name, config in validation_config.items():
                param_value = request.query_params.get(param_name)

                # Apply validation based on configuration
                if param_name == 'period':
                    default = config.get('default', 'all')
                    validated_params[param_name] = validate_time_period(
                        param_value if param_value else default
                    )
                elif param_name == 'limit':
                    default = config.get('default', 10)
                    max_value = config.get('max', 100)
                    validated_params[param_name] = validate_limit(
                        param_value,
                        parameter_name=param_name,
                        max_value=max_value,
                        default=default
                    )
                elif param_name in ['from_date', 'to_date']:
                    # Handle date validation in pairs
                    if 'from_date' in validation_config and 'to_date' in validation_config:
                        if param_name == 'from_date':
                            from_date_str = request.query_params.get('from_date')
                            to_date_str = request.query_params.get('to_date')
                            from_date, to_date = validate_date_params(from_date_str, to_date_str)
                            validated_params['from_date'] = from_date
                            validated_params['to_date'] = to_date
                elif param_name == 'granularity':
                    validated_params[param_name] = validate_granularity(param_value)

            # Store validated parameters in request
            request.validated_params = validated_params

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


# Story-specific decorators for convenience
def validate_recent_tracks_params():
    """Story 9: Recent Tracks API validation."""
    return validate_api_params('recent_tracks')


def validate_top_artists_params():
    """Story 10: Top Artists API validation."""
    return validate_api_params('top_artists')


def validate_top_albums_params():
    """Story 11: Top Albums API validation."""
    return validate_api_params('top_albums')


def validate_top_tracks_params():
    """Story 12: Top Tracks API validation."""
    return validate_api_params('top_tracks')


def validate_chart_data_params():
    """Story 13: Chart Data API validation."""
    return validate_api_params('chart_data')