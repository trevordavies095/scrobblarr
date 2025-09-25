"""
Performance monitoring and profiling utilities for Story 18.

Provides tools for monitoring API endpoint performance, database query profiling,
and performance metrics collection.
"""
import time
import logging
from functools import wraps
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from contextlib import contextmanager

logger = logging.getLogger('stats.performance')


class PerformanceMonitor:
    """
    Performance monitoring utility for tracking API response times and database queries.
    """

    def __init__(self):
        self.metrics_cache_timeout = 3600  # 1 hour

    def record_api_performance(self, endpoint, response_time, query_count=0, cache_hit=False):
        """Record performance metrics for an API endpoint."""
        cache_key = f"perf_metrics_{endpoint}"

        # Get existing metrics or initialize
        metrics = cache.get(cache_key, {
            'total_requests': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'avg_time': 0,
            'cache_hits': 0,
            'total_queries': 0,
            'last_updated': None
        })

        # Update metrics
        metrics['total_requests'] += 1
        metrics['total_time'] += response_time
        metrics['min_time'] = min(metrics['min_time'], response_time)
        metrics['max_time'] = max(metrics['max_time'], response_time)
        metrics['avg_time'] = metrics['total_time'] / metrics['total_requests']
        metrics['total_queries'] += query_count
        metrics['last_updated'] = timezone.now().isoformat()

        if cache_hit:
            metrics['cache_hits'] += 1

        # Cache updated metrics
        cache.set(cache_key, metrics, self.metrics_cache_timeout)

        # Log performance if it exceeds thresholds
        if response_time > 500:  # 500ms threshold
            logger.warning(
                f"Slow API response",
                extra={
                    'endpoint': endpoint,
                    'response_time': response_time,
                    'query_count': query_count,
                    'cache_hit': cache_hit
                }
            )

    def get_performance_summary(self, endpoint=None):
        """Get performance summary for specific endpoint or all endpoints."""
        if endpoint:
            cache_key = f"perf_metrics_{endpoint}"
            return cache.get(cache_key)

        # Get all performance metrics (simplified - would need pattern matching in Redis)
        summary = {
            'total_endpoints': 0,
            'overall_avg_time': 0,
            'slowest_endpoint': None,
            'fastest_endpoint': None,
            'cache_hit_rate': 0
        }

        # This would be more sophisticated with Redis pattern matching
        # For now, return a placeholder
        logger.info("Performance summary requested")
        return summary


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


@contextmanager
def query_profiler(endpoint_name):
    """Context manager for profiling database queries."""
    initial_query_count = len(connection.queries)
    start_time = time.time()

    try:
        yield
    finally:
        end_time = time.time()
        query_count = len(connection.queries) - initial_query_count
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds

        # Log query performance if in DEBUG mode
        if settings.DEBUG and query_count > 10:
            logger.warning(
                f"High query count for {endpoint_name}",
                extra={
                    'endpoint': endpoint_name,
                    'query_count': query_count,
                    'response_time': response_time
                }
            )

        # Record performance metrics
        performance_monitor.record_api_performance(
            endpoint_name,
            response_time,
            query_count
        )


def performance_profile(endpoint_name):
    """Decorator for profiling API endpoint performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            with query_profiler(endpoint_name):
                return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def analyze_slow_queries(threshold_ms=100):
    """Analyze slow queries from Django's query log."""
    if not settings.DEBUG:
        logger.warning("Query analysis requires DEBUG=True")
        return []

    slow_queries = []
    for query in connection.queries:
        query_time = float(query['time']) * 1000  # Convert to ms
        if query_time > threshold_ms:
            slow_queries.append({
                'sql': query['sql'],
                'time_ms': query_time
            })

    return slow_queries


class DatabaseProfiler:
    """Database query profiling utility."""

    @staticmethod
    def profile_queryset(queryset, description="Query"):
        """Profile a Django queryset execution."""
        initial_query_count = len(connection.queries)
        start_time = time.time()

        # Force evaluation
        result_count = len(list(queryset))

        end_time = time.time()
        query_count = len(connection.queries) - initial_query_count
        execution_time = (end_time - start_time) * 1000

        logger.info(
            f"Database query profile: {description}",
            extra={
                'query_count': query_count,
                'execution_time_ms': execution_time,
                'result_count': result_count,
                'time_per_result': execution_time / result_count if result_count > 0 else 0
            }
        )

        return {
            'query_count': query_count,
            'execution_time_ms': execution_time,
            'result_count': result_count
        }

    @staticmethod
    def explain_query(queryset):
        """Get query execution plan (SQLite EXPLAIN QUERY PLAN)."""
        if not settings.DEBUG:
            return "Query explain requires DEBUG=True"

        sql, params = queryset.query.sql_with_params()

        with connection.cursor() as cursor:
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
            plan = cursor.fetchall()

            return [
                {
                    'id': row[0],
                    'parent': row[1],
                    'notused': row[2],
                    'detail': row[3]
                } for row in plan
            ]


def performance_test_endpoint(endpoint_view, test_params=None, iterations=10):
    """Performance test utility for API endpoints."""
    from django.test import RequestFactory

    factory = RequestFactory()
    response_times = []

    for i in range(iterations):
        # Create test request
        request = factory.get('/', test_params or {})

        start_time = time.time()
        try:
            response = endpoint_view(request)
            end_time = time.time()

            response_time = (end_time - start_time) * 1000
            response_times.append(response_time)

        except Exception as e:
            logger.error(f"Performance test failed: {e}")
            continue

    if response_times:
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)

        return {
            'iterations': len(response_times),
            'avg_time_ms': avg_time,
            'min_time_ms': min_time,
            'max_time_ms': max_time,
            'all_times': response_times
        }

    return None


# Performance middleware for automatic profiling
class PerformanceMiddleware:
    """Middleware for automatic performance monitoring."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip profiling for static files and admin
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return self.get_response(request)

        start_time = time.time()
        initial_query_count = len(connection.queries)

        response = self.get_response(request)

        end_time = time.time()
        query_count = len(connection.queries) - initial_query_count
        response_time = (end_time - start_time) * 1000

        # Record performance metrics for API endpoints
        if request.path.startswith('/api/'):
            performance_monitor.record_api_performance(
                request.path,
                response_time,
                query_count,
                cache_hit=False  # Would need to detect this properly
            )

        # Add performance headers
        response['X-Response-Time'] = f"{response_time:.2f}ms"
        response['X-Query-Count'] = str(query_count)

        return response