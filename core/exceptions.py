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

    def __init__(self, message, status_code=500, **kwargs):
        super().__init__(message, error_code='API_ERROR', **kwargs)
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