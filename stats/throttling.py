"""
Custom throttling classes for stats API endpoints.

Provides specialized rate limiting for different types of endpoints
based on their computational cost and usage patterns.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from core.exceptions import RateLimitExceededError


class StatsSummaryThrottle(UserRateThrottle):
    """Throttling for expensive summary endpoints."""
    scope = 'stats_summary'

    def throttle_failure(self):
        """
        Called when a request is throttled.
        Raises our custom RateLimitExceededError for consistent error handling.
        """
        wait = self.wait()
        raise RateLimitExceededError(
            message="Rate limit exceeded for statistics summary endpoint",
            resource="stats_summary",
            retry_after=wait
        )


class ChartDataThrottle(UserRateThrottle):
    """Throttling for chart data endpoints."""
    scope = 'chart_data'

    def throttle_failure(self):
        """
        Called when a request is throttled.
        Raises our custom RateLimitExceededError for consistent error handling.
        """
        wait = self.wait()
        raise RateLimitExceededError(
            message="Rate limit exceeded for chart data endpoint",
            resource="chart_data",
            retry_after=wait
        )


class ExpensiveQueryThrottle(UserRateThrottle):
    """Throttling for computationally expensive queries."""
    scope = 'expensive_query'

    def throttle_failure(self):
        """
        Called when a request is throttled.
        Raises our custom RateLimitExceededError for consistent error handling.
        """
        wait = self.wait()
        raise RateLimitExceededError(
            message="Rate limit exceeded for expensive queries",
            resource="expensive_query",
            retry_after=wait
        )


class AnonStatsSummaryThrottle(AnonRateThrottle):
    """Throttling for anonymous users accessing summary endpoints."""
    scope = 'stats_summary'
    rate = '50/hour'  # More restrictive for anonymous users

    def throttle_failure(self):
        """
        Called when a request is throttled.
        Raises our custom RateLimitExceededError for consistent error handling.
        """
        wait = self.wait()
        raise RateLimitExceededError(
            message="Rate limit exceeded for anonymous users on statistics summary",
            resource="stats_summary_anon",
            retry_after=wait
        )


class AnonChartDataThrottle(AnonRateThrottle):
    """Throttling for anonymous users accessing chart data."""
    scope = 'chart_data'
    rate = '100/hour'  # More restrictive for anonymous users

    def throttle_failure(self):
        """
        Called when a request is throttled.
        Raises our custom RateLimitExceededError for consistent error handling.
        """
        wait = self.wait()
        raise RateLimitExceededError(
            message="Rate limit exceeded for anonymous users on chart data",
            resource="chart_data_anon",
            retry_after=wait
        )