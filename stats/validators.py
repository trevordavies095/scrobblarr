"""
Parameter validation utilities for stats API endpoints.

Provides validation functions for common API parameters like time periods,
date formats, limits, and custom validation logic.
"""
from datetime import datetime
from django.utils import timezone
from core.exceptions import (
    InvalidTimePeriodError,
    InvalidDateFormatError,
    InvalidDateRangeError,
    InvalidLimitError,
    InvalidGranularityError
)


def validate_time_period(period_value):
    """
    Validate time period parameter.

    Args:
        period_value (str): Time period value to validate

    Returns:
        str: Validated period value

    Raises:
        InvalidTimePeriodError: If period is invalid
    """
    if period_value is None:
        return 'all'  # Default value

    valid_periods = ['7d', '30d', '90d', '180d', '365d', 'all']

    if period_value not in valid_periods:
        raise InvalidTimePeriodError(period_value)

    return period_value


def validate_date_format(date_string, parameter_name):
    """
    Validate date format for API parameters.

    Args:
        date_string (str): Date string to validate
        parameter_name (str): Name of the parameter for error reporting

    Returns:
        datetime: Parsed datetime object

    Raises:
        InvalidDateFormatError: If date format is invalid
    """
    if not date_string:
        return None

    try:
        # Parse YYYY-MM-DD format
        parsed_date = datetime.strptime(date_string, '%Y-%m-%d')
        # Make timezone aware
        return timezone.make_aware(parsed_date)
    except ValueError:
        raise InvalidDateFormatError(parameter_name, date_string)


def validate_date_range(from_date, to_date):
    """
    Validate date range parameters.

    Args:
        from_date (datetime): Start date
        to_date (datetime): End date

    Raises:
        InvalidDateRangeError: If date range is invalid
    """
    if from_date and to_date and from_date > to_date:
        raise InvalidDateRangeError("from_date must be before to_date")


def validate_limit(limit_value, parameter_name='limit', min_value=1, max_value=100, default=10):
    """
    Validate limit/pagination parameters.

    Args:
        limit_value: Limit value to validate
        parameter_name (str): Name of the parameter for error reporting
        min_value (int): Minimum allowed value
        max_value (int): Maximum allowed value
        default (int): Default value if limit_value is None

    Returns:
        int: Validated limit value

    Raises:
        InvalidLimitError: If limit is invalid
    """
    if limit_value is None:
        return default

    try:
        limit_int = int(limit_value)
    except (ValueError, TypeError):
        raise InvalidLimitError(parameter_name, limit_value, min_value, max_value)

    if limit_int < min_value or limit_int > max_value:
        raise InvalidLimitError(parameter_name, limit_value, min_value, max_value)

    return limit_int


def validate_granularity(granularity_value):
    """
    Validate granularity parameter for chart data.

    Args:
        granularity_value (str): Granularity value to validate

    Returns:
        str: Validated granularity value or None for auto-detection

    Raises:
        InvalidGranularityError: If granularity is invalid
    """
    if not granularity_value:
        return None  # Auto-detection

    valid_granularities = ['daily', 'monthly', 'yearly']

    if granularity_value not in valid_granularities:
        raise InvalidGranularityError(granularity_value)

    return granularity_value


def validate_pagination_params(limit=None, offset=None, max_limit=100):
    """
    Validate pagination parameters.

    Args:
        limit: Limit value
        offset: Offset value
        max_limit (int): Maximum allowed limit

    Returns:
        tuple: (validated_limit, validated_offset)

    Raises:
        InvalidLimitError: If parameters are invalid
    """
    validated_limit = validate_limit(limit, 'limit', max_value=max_limit)

    if offset is not None:
        try:
            validated_offset = int(offset)
            if validated_offset < 0:
                raise InvalidLimitError('offset', offset, min_value=0, max_value=float('inf'))
        except (ValueError, TypeError):
            raise InvalidLimitError('offset', offset, min_value=0, max_value=float('inf'))
    else:
        validated_offset = 0

    return validated_limit, validated_offset


def validate_date_params(from_date_str=None, to_date_str=None):
    """
    Validate date range parameters together.

    Args:
        from_date_str (str): From date string
        to_date_str (str): To date string

    Returns:
        tuple: (from_date, to_date) as datetime objects or None

    Raises:
        InvalidDateFormatError: If date format is invalid
        InvalidDateRangeError: If date range is invalid
    """
    from_date = validate_date_format(from_date_str, 'from_date') if from_date_str else None
    to_date = validate_date_format(to_date_str, 'to_date') if to_date_str else None

    # Validate date range if both dates are provided
    if from_date and to_date:
        validate_date_range(from_date, to_date)

    return from_date, to_date


def validate_story_compliance(endpoint_name, **params):
    """
    Validate parameters for specific story compliance.

    Args:
        endpoint_name (str): Name of the endpoint/story
        **params: Parameters to validate

    Returns:
        dict: Validated parameters
    """
    validated = {}

    if endpoint_name in ['recent_tracks']:  # Story 9
        validated['limit'] = validate_limit(
            params.get('limit'),
            max_value=50,
            default=10
        )

    elif endpoint_name in ['top_artists', 'top_albums', 'top_tracks']:  # Stories 10-12
        validated['period'] = validate_time_period(params.get('period'))
        validated['limit'] = validate_limit(
            params.get('limit'),
            max_value=100,
            default=10
        )
        from_date, to_date = validate_date_params(
            params.get('from_date'),
            params.get('to_date')
        )
        validated['from_date'] = from_date
        validated['to_date'] = to_date

    elif endpoint_name == 'chart_data':  # Story 13
        validated['period'] = validate_time_period(params.get('period'))
        validated['granularity'] = validate_granularity(params.get('granularity'))
        from_date, to_date = validate_date_params(
            params.get('from_date'),
            params.get('to_date')
        )
        validated['from_date'] = from_date
        validated['to_date'] = to_date

    return validated