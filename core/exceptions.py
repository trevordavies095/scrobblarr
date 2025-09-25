"""
Custom exception classes for Scrobblarr application.

Provides structured error handling with appropriate logging and context.
"""
import logging


class ScrobblarrError(Exception):
    """Base exception for all Scrobblarr errors."""

    def __init__(self, message, error_code=None, details=None, logger_name=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

        # Log the error when it's created
        if logger_name:
            logger = logging.getLogger(logger_name)
            logger.error(
                f"ScrobblarrError: {message}",
                extra={
                    'error_code': error_code,
                    'error_details': details,
                    'error_type': self.__class__.__name__
                }
            )


class DataValidationError(ScrobblarrError):
    """Raised when data validation fails."""

    def __init__(self, message, field=None, value=None, **kwargs):
        super().__init__(message, error_code='VALIDATION_ERROR', **kwargs)
        self.field = field
        self.value = value
        if field:
            self.details.update({'field': field, 'value': value})


class ImportError(ScrobblarrError):
    """Raised when data import operations fail."""

    def __init__(self, message, row_number=None, file_path=None, **kwargs):
        super().__init__(message, error_code='IMPORT_ERROR', **kwargs)
        self.row_number = row_number
        self.file_path = file_path
        if row_number:
            self.details.update({'row_number': row_number})
        if file_path:
            self.details.update({'file_path': file_path})


class APIError(ScrobblarrError):
    """Raised when API operations fail."""

    def __init__(self, message, status_code=500, error_code=None, **kwargs):
        # Use provided error_code or default to 'API_ERROR'
        final_error_code = error_code or 'API_ERROR'
        super().__init__(message, error_code=final_error_code, **kwargs)
        self.status_code = status_code
        self.details.update({'status_code': status_code})


class ExternalServiceError(ScrobblarrError):
    """Raised when external service calls fail (e.g., Last.fm API)."""

    def __init__(self, message, service_name=None, response_code=None, **kwargs):
        super().__init__(message, error_code='EXTERNAL_SERVICE_ERROR', **kwargs)
        self.service_name = service_name
        self.response_code = response_code
        if service_name:
            self.details.update({'service_name': service_name})
        if response_code:
            self.details.update({'response_code': response_code})


class DataIntegrityError(ScrobblarrError):
    """Raised when database integrity constraints are violated."""

    def __init__(self, message, model=None, constraint=None, **kwargs):
        super().__init__(message, error_code='DATA_INTEGRITY_ERROR', **kwargs)
        self.model = model
        self.constraint = constraint
        if model:
            self.details.update({'model': model})
        if constraint:
            self.details.update({'constraint': constraint})


class ConfigurationError(ScrobblarrError):
    """Raised when configuration issues are detected."""

    def __init__(self, message, setting_name=None, **kwargs):
        super().__init__(message, error_code='CONFIGURATION_ERROR', **kwargs)
        self.setting_name = setting_name
        if setting_name:
            self.details.update({'setting_name': setting_name})


class TaskError(ScrobblarrError):
    """Raised when background task execution fails."""

    def __init__(self, message, task_name=None, task_id=None, **kwargs):
        super().__init__(message, error_code='TASK_ERROR', **kwargs)
        self.task_name = task_name
        self.task_id = task_id
        if task_name:
            self.details.update({'task_name': task_name})
        if task_id:
            self.details.update({'task_id': task_id})


class RateLimitError(ScrobblarrError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message, resource=None, retry_after=None, **kwargs):
        super().__init__(message, error_code='RATE_LIMIT_ERROR', **kwargs)
        self.resource = resource
        self.retry_after = retry_after
        if resource:
            self.details.update({'resource': resource})
        if retry_after:
            self.details.update({'retry_after': retry_after})


class InvalidParameterError(APIError):
    """Raised when API parameters are invalid."""

    def __init__(self, message, parameter=None, provided_value=None, allowed_values=None, **kwargs):
        error_code = kwargs.pop('error_code', 'INVALID_PARAMETER')
        super().__init__(message, status_code=400, error_code=error_code, **kwargs)
        self.parameter = parameter
        self.provided_value = provided_value
        self.allowed_values = allowed_values

        if parameter:
            self.details.update({'parameter': parameter})
        if provided_value is not None:
            self.details.update({'provided': provided_value})
        if allowed_values is not None:
            self.details.update({'allowed': allowed_values})


class InvalidTimePeriodError(InvalidParameterError):
    """Raised when an invalid time period is provided."""

    def __init__(self, provided_period, **kwargs):
        allowed_periods = ['7d', '30d', '90d', '180d', '365d', 'all']
        message = f"Time period '{provided_period}' is not supported. Use: {', '.join(allowed_periods)}"
        super().__init__(
            message=message,
            parameter='period',
            provided_value=provided_period,
            allowed_values=allowed_periods,
            error_code='INVALID_TIME_PERIOD',
            **kwargs
        )


class InvalidDateFormatError(InvalidParameterError):
    """Raised when date parameters have invalid format."""

    def __init__(self, parameter, provided_value, **kwargs):
        message = f"Invalid date format for '{parameter}'. Use YYYY-MM-DD format."
        super().__init__(
            message=message,
            parameter=parameter,
            provided_value=provided_value,
            error_code='INVALID_DATE_FORMAT',
            **kwargs
        )


class InvalidDateRangeError(InvalidParameterError):
    """Raised when date range parameters are invalid."""

    def __init__(self, message="Invalid date range", **kwargs):
        super().__init__(
            message=message,
            error_code='INVALID_DATE_RANGE',
            **kwargs
        )


class InvalidLimitError(InvalidParameterError):
    """Raised when limit/pagination parameters are invalid."""

    def __init__(self, parameter, provided_value, min_value=1, max_value=100, **kwargs):
        message = f"Invalid {parameter} '{provided_value}'. Must be between {min_value} and {max_value}."
        super().__init__(
            message=message,
            parameter=parameter,
            provided_value=provided_value,
            error_code='INVALID_LIMIT',
            **kwargs
        )
        self.details.update({
            'min_value': min_value,
            'max_value': max_value
        })


class InvalidGranularityError(InvalidParameterError):
    """Raised when granularity parameter is invalid."""

    def __init__(self, provided_granularity, **kwargs):
        allowed_granularities = ['daily', 'monthly', 'yearly']
        message = f"Invalid granularity '{provided_granularity}'. Use: {', '.join(allowed_granularities)}"
        super().__init__(
            message=message,
            parameter='granularity',
            provided_value=provided_granularity,
            allowed_values=allowed_granularities,
            error_code='INVALID_GRANULARITY',
            **kwargs
        )


class RateLimitExceededError(APIError):
    """Raised when rate limits are exceeded (API-specific)."""

    def __init__(self, message, resource=None, retry_after=None, **kwargs):
        super().__init__(message, status_code=429, error_code='RATE_LIMIT_EXCEEDED', **kwargs)
        self.resource = resource
        self.retry_after = retry_after

        if resource:
            self.details.update({'resource': resource})
        if retry_after:
            self.details.update({'retry_after': retry_after})