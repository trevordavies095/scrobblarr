"""
Caching utilities for stats API endpoints.

Story 18: API Performance Optimization
Provides smart caching with invalidation based on data freshness.
"""
import hashlib
import logging
from functools import wraps
from django.core.cache import cache, caches
from django.utils import timezone
from music.models import Scrobble

logger = logging.getLogger('stats.cache')


class CacheManager:
    """
    Smart cache manager with data-aware invalidation.
    """

    def __init__(self):
        self.api_cache = caches['api_cache']
        self.query_cache = caches['query_cache']
        self.default_cache = cache

    def get_latest_scrobble_timestamp(self):
        """Get the timestamp of the latest scrobble for cache invalidation."""
        latest = self.query_cache.get('latest_scrobble_timestamp')
        if latest is None:
            try:
                latest_scrobble = Scrobble.objects.order_by('-timestamp').first()
                latest = latest_scrobble.timestamp if latest_scrobble else timezone.now()
                self.query_cache.set('latest_scrobble_timestamp', latest, 60)  # Cache for 1 minute
            except Exception as e:
                logger.warning(f"Failed to get latest scrobble timestamp: {e}")
                latest = timezone.now()
        return latest

    def generate_cache_key(self, endpoint, params, data_version=None):
        """
        Generate a cache key based on endpoint, parameters, and data freshness.

        Args:
            endpoint (str): API endpoint name
            params (dict): Query parameters
            data_version (datetime): Data version for cache invalidation

        Returns:
            str: Generated cache key
        """
        if data_version is None:
            data_version = self.get_latest_scrobble_timestamp()

        # Sort params for consistent key generation
        sorted_params = sorted(params.items()) if params else []

        # Create hash from endpoint, params, and data version
        key_data = f"{endpoint}:{sorted_params}:{data_version.isoformat()}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]

        return f"stats:{endpoint}:{key_hash}"

    def get_cached_result(self, cache_key, cache_backend='api_cache'):
        """Get cached result from specified backend."""
        try:
            cache_backend_obj = getattr(self, cache_backend, self.api_cache)
            result = cache_backend_obj.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
            return result
        except Exception as e:
            logger.warning(f"Cache get failed for key {cache_key}: {e}")
            return None

    def set_cached_result(self, cache_key, data, timeout=None, cache_backend='api_cache'):
        """Set cached result in specified backend."""
        try:
            cache_backend_obj = getattr(self, cache_backend, self.api_cache)
            cache_backend_obj.set(cache_key, data, timeout)
            logger.debug(f"Cache set for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Cache set failed for key {cache_key}: {e}")

    def invalidate_endpoint_cache(self, endpoint_pattern):
        """Invalidate all cache keys matching an endpoint pattern."""
        # Note: File-based cache doesn't support pattern-based deletion
        # This is a limitation we can improve with Redis if needed
        logger.info(f"Cache invalidation requested for pattern: {endpoint_pattern}")


# Global cache manager instance
cache_manager = CacheManager()


def cached_api_response(timeout=3600, cache_backend='api_cache', use_data_version=True):
    """
    Decorator for caching API responses with smart invalidation.

    Args:
        timeout (int): Cache timeout in seconds
        cache_backend (str): Cache backend to use
        use_data_version (bool): Whether to include data version in cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Generate cache key
            endpoint = f"{self.__class__.__name__}.{func.__name__}"
            params = dict(request.query_params) if hasattr(request, 'query_params') else {}

            data_version = None
            if use_data_version:
                data_version = cache_manager.get_latest_scrobble_timestamp()

            cache_key = cache_manager.generate_cache_key(endpoint, params, data_version)

            # Try to get cached result
            cached_result = cache_manager.get_cached_result(cache_key, cache_backend)
            if cached_result is not None:
                logger.info(f"Serving cached response for {endpoint}")
                return cached_result

            # Execute function and cache result
            result = func(self, request, *args, **kwargs)

            # Only cache successful responses
            if hasattr(result, 'status_code') and result.status_code == 200:
                cache_manager.set_cached_result(cache_key, result, timeout, cache_backend)
                logger.info(f"Cached new response for {endpoint}")

            return result
        return wrapper
    return decorator


def cached_query_result(timeout=300, key_prefix='query'):
    """
    Decorator for caching database query results.

    Args:
        timeout (int): Cache timeout in seconds
        key_prefix (str): Prefix for cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            func_name = f"{func.__module__}.{func.__name__}"
            args_key = hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()[:8]
            cache_key = f"{key_prefix}:{func_name}:{args_key}"

            # Try to get cached result
            cached_result = cache_manager.get_cached_result(cache_key, 'query_cache')
            if cached_result is not None:
                logger.debug(f"Query cache hit: {func_name}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set_cached_result(cache_key, result, timeout, 'query_cache')
            logger.debug(f"Query result cached: {func_name}")

            return result
        return wrapper
    return decorator


def cache_expensive_computation(timeout=1800, invalidate_on_new_data=True):
    """
    Decorator for caching expensive computations like statistics calculations.

    Args:
        timeout (int): Cache timeout in seconds (default: 30 minutes)
        invalidate_on_new_data (bool): Whether to invalidate when new scrobbles are added
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            func_signature = f"{func.__module__}.{func.__name__}"

            if invalidate_on_new_data:
                data_version = cache_manager.get_latest_scrobble_timestamp()
                cache_key = f"computation:{func_signature}:{data_version.isoformat()}"
            else:
                args_hash = hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()[:8]
                cache_key = f"computation:{func_signature}:{args_hash}"

            # Try to get cached result
            cached_result = cache_manager.get_cached_result(cache_key, 'api_cache')
            if cached_result is not None:
                logger.info(f"Expensive computation cache hit: {func.__name__}")
                return cached_result

            # Execute function and cache result
            logger.info(f"Executing expensive computation: {func.__name__}")
            result = func(*args, **kwargs)
            cache_manager.set_cached_result(cache_key, result, timeout, 'api_cache')

            return result
        return wrapper
    return decorator


class QueryOptimizer:
    """
    Query optimization utilities for common patterns.
    """

    @staticmethod
    def get_optimized_scrobbles_queryset():
        """Get an optimized queryset for scrobbles with related data."""
        return Scrobble.objects.select_related(
            'track',
            'track__artist',
            'track__album'
        ).order_by('-timestamp')

    @staticmethod
    def get_time_filtered_scrobbles(time_filter):
        """Get time-filtered scrobbles with optimal query."""
        queryset = QueryOptimizer.get_optimized_scrobbles_queryset()

        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            if from_date and to_date:
                return queryset.filter(timestamp__range=(from_date, to_date))
            elif from_date:
                return queryset.filter(timestamp__gte=from_date)
            elif to_date:
                return queryset.filter(timestamp__lte=to_date)
        elif time_filter:
            return queryset.filter(timestamp__gte=time_filter)

        return queryset


def clear_stats_cache():
    """Clear all stats-related cached data."""
    try:
        cache_manager.query_cache.clear()
        logger.info("Stats cache cleared successfully")
    except Exception as e:
        logger.error(f"Failed to clear stats cache: {e}")


def warm_cache_for_common_queries():
    """Pre-populate cache with common query results."""
    logger.info("Warming cache for common queries...")
    # This would be called by a management command or background task
    pass