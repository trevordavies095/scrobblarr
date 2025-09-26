import logging
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q, Max, Min
from django.db import models
from django.utils import timezone
from django.http import Http404
from django.core.cache import cache
from datetime import timedelta, datetime
from music.models import Artist, Album, Track, Scrobble
from core.exceptions import (
    APIError, DataValidationError, InvalidTimePeriodError,
    InvalidDateFormatError, InvalidDateRangeError, InvalidLimitError,
    InvalidGranularityError
)
from .cache import cached_api_response, cache_expensive_computation, QueryOptimizer
from .decorators import (
    validate_recent_tracks_params,
    validate_top_artists_params,
    validate_top_albums_params,
    validate_top_tracks_params,
    validate_chart_data_params
)
from .throttling import StatsSummaryThrottle, ChartDataThrottle
from .serializers import (
    ArtistListSerializer, ArtistDetailSerializer, ArtistStory14Serializer,
    AlbumListSerializer, AlbumDetailSerializer, AlbumStory15Serializer,
    TrackListSerializer, TrackDetailSerializer,
    ScrobbleListSerializer, RecentTracksSerializer,
    TopAlbumsSerializer, TopTracksSerializer,
    ScrobblesChartSerializer, StatisticsSummarySerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class RecentTracksPagination(PageNumberPagination):
    """
    Custom pagination for Recent Tracks API to match Story 9 requirements.
    """
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 50

    def get_page_size(self, request):
        """Get page size with Story 9 validation (min 1, max 50, default 10)."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return Story 9 compliant response format."""
        return Response({
            'results': data,
            'count': len(data),
            'has_next': self.page.has_next() if self.page else False,
            'has_previous': self.page.has_previous() if self.page else False,
        })


class TopArtistsPagination(PageNumberPagination):
    """
    Custom pagination for Top Artists API to match Story 10 requirements.
    """
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100

    def get_page_size(self, request):
        """Get page size with Story 10 validation (min 1, max 100, default 10)."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return Story 10 compliant response format."""
        period = getattr(self, '_period', 'all')
        total_scrobbles = getattr(self, '_total_scrobbles', 0)

        return Response({
            'period': period,
            'results': data,
            'count': len(data),
            'total_scrobbles': total_scrobbles
        })


class TopAlbumsPagination(PageNumberPagination):
    """
    Custom pagination for Top Albums API to match Story 11 requirements.
    """
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100

    def get_page_size(self, request):
        """Get page size with Story 11 validation (min 1, max 100, default 10)."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return Story 11 compliant response format."""
        period = getattr(self, '_period', 'all')
        total_scrobbles = getattr(self, '_total_scrobbles', 0)

        return Response({
            'period': period,
            'results': data,
            'count': len(data),
            'total_scrobbles': total_scrobbles
        })


class TopTracksPagination(PageNumberPagination):
    """
    Custom pagination for Top Tracks API to match Story 12 requirements.
    """
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100

    def get_page_size(self, request):
        """Get page size with Story 12 validation (min 1, max 100, default 10)."""
        if self.page_size_query_param:
            try:
                page_size = int(request.query_params[self.page_size_query_param])
                if page_size < 1:
                    return 1
                elif page_size > self.max_page_size:
                    return self.max_page_size
                return page_size
            except (KeyError, ValueError):
                pass
        return self.page_size

    def get_paginated_response(self, data):
        """Return Story 12 compliant response format."""
        period = getattr(self, '_period', 'all')
        total_scrobbles = getattr(self, '_total_scrobbles', 0)

        return Response({
            'period': period,
            'results': data,
            'count': len(data),
            'total_scrobbles': total_scrobbles
        })


class StatsViewSet(viewsets.ViewSet):
    """
    Stats API viewset for music analytics with error handling and rate limiting
    """
    pagination_class = StandardResultsSetPagination
    throttle_classes = [StatsSummaryThrottle, ChartDataThrottle]
    throttle_scope = None  # Will be overridden by specific methods

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger('stats.api')

    def get_time_filter(self, request):
        """Get time filter based on period parameter or custom date range."""
        # Check for custom date range first
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        if from_date or to_date:
            return self.parse_date_range(from_date, to_date, request)

        # Use period-based filtering
        period = request.query_params.get('period', 'all')
        now = timezone.now()

        time_filters = {
            '7d': now - timedelta(days=7),
            '30d': now - timedelta(days=30),
            '90d': now - timedelta(days=90),
            '180d': now - timedelta(days=180),
            '365d': now - timedelta(days=365),
            'all': None
        }

        if period not in time_filters:
            self.logger.warning(
                f"Invalid period parameter provided: {period}",
                extra={
                    'period': period,
                    'valid_periods': list(time_filters.keys()),
                    'request_path': request.path
                }
            )
            # Return default instead of raising error
            period = 'all'

        return time_filters.get(period, time_filters['all'])

    def parse_date_range(self, from_date, to_date, request):
        """Parse custom date range from query parameters."""
        try:
            from .validators import validate_date_format, validate_date_range

            parsed_from = validate_date_format(from_date, 'from_date') if from_date else None
            parsed_to = validate_date_format(to_date, 'to_date') if to_date else None

            if parsed_to:
                # Set to end of day for to_date
                parsed_to = parsed_to.replace(hour=23, minute=59, second=59)

            # Validation: from_date should be before to_date
            validate_date_range(parsed_from, parsed_to)

            # Return tuple (from_date, to_date) instead of single date
            return (parsed_from, parsed_to)

        except ValueError as e:
            self.logger.warning(
                f"Invalid date format provided: from_date={from_date}, to_date={to_date}",
                extra={'exception': str(e), 'request_path': request.path}
            )
            raise APIError(
                "Invalid date format. Use YYYY-MM-DD format.",
                status_code=400,
                error_code="INVALID_DATE_FORMAT"
            )

    def get_period_display(self, request):
        """Get the period string for response display."""
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

        if from_date or to_date:
            if from_date and to_date:
                return f"{from_date} to {to_date}"
            elif from_date:
                return f"from {from_date}"
            elif to_date:
                return f"until {to_date}"

        # Return the validated period (use new validation)
        from .validators import validate_time_period
        period = request.query_params.get('period', 'all')
        return validate_time_period(period)

    def get_granularity(self, request, time_filter):
        """Get granularity for chart data - auto or manual override."""
        # Check for manual override with proper validation
        from .validators import validate_granularity
        manual_granularity = request.query_params.get('granularity')
        validated_granularity = validate_granularity(manual_granularity)

        if validated_granularity:
            return validated_granularity

        # Auto-granularity based on time range
        return self._calculate_auto_granularity(request, time_filter)

    def _calculate_auto_granularity(self, request, time_filter):
        """Calculate automatic granularity based on time range."""
        # For custom date ranges
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            if from_date and to_date:
                days = (to_date.date() - from_date.date()).days
            elif from_date:
                # From date to now
                days = (timezone.now().date() - from_date.date()).days
            elif to_date:
                # Assume 1 year if only to_date provided
                days = 365
            else:
                days = 365
        else:
            # Map period strings to days
            period = request.query_params.get('period', 'all')
            period_to_days = {
                '7d': 7,
                '30d': 30,
                '90d': 90,
                '180d': 180,
                '365d': 365,
                'all': 1000  # Treat 'all' as very long period for yearly
            }
            days = period_to_days.get(period, 365)

        # Auto-granularity logic
        if days <= 31:
            return 'daily'
        elif days <= 365:
            return 'monthly'
        else:
            return 'yearly'

    def _get_date_trunc_format(self, granularity):
        """Get SQLite date format string for granularity."""
        formats = {
            'daily': '%Y-%m-%d',
            'monthly': '%Y-%m',
            'yearly': '%Y'
        }
        return formats.get(granularity, '%Y-%m')

    def _get_date_trunc_function(self, granularity):
        """Get Django date truncation function for safe SQL generation."""
        from django.db.models.functions import TruncDate, TruncMonth, TruncYear

        trunc_functions = {
            'daily': TruncDate,
            'monthly': TruncMonth,
            'yearly': TruncYear
        }
        return trunc_functions.get(granularity, TruncMonth)

    def _build_period_info(self, period_value, granularity):
        """Build start_date and end_date for a chart period."""
        if granularity == 'daily':
            start_date = end_date = period_value
        elif granularity == 'monthly':
            # Parse YYYY-MM format
            year, month = map(int, period_value.split('-'))
            start_date = f"{year:04d}-{month:02d}-01"

            # Calculate last day of month
            if month == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month + 1, 1)
            last_day = (next_month - timedelta(days=1)).day
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        elif granularity == 'yearly':
            # Parse YYYY format
            year = int(period_value)
            start_date = f"{year:04d}-01-01"
            end_date = f"{year:04d}-12-31"
        else:
            start_date = end_date = period_value

        return start_date, end_date

    def list(self, request):
        """API overview with available endpoints."""
        return Response({
            "message": "Scrobblarr Music Analytics API",
            "endpoints": {
                "recent_tracks": "/api/recent-tracks/",
                "top_artists": "/api/top-artists/?period=30d",
                "top_albums": "/api/top-albums/?period=30d",
                "top_tracks": "/api/top-tracks/?period=30d",
                "scrobbles_chart": "/api/scrobbles/chart/?period=30d&granularity=monthly",
                "summary": "/api/stats/summary/",
                "artists": "/api/artists/{id}/",
                "albums": "/api/albums/{id}/",
                "tracks": "/api/tracks/{id}/"
            },
            "time_periods": ["7d", "30d", "90d", "180d", "365d", "all"],
            "granularity_options": ["daily", "monthly", "yearly"]
        })

    def is_valid_uuid(self, value):
        """Check if a string is a valid UUID (for MBID lookup)."""
        import uuid
        try:
            # Convert to string in case it's passed as another type
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError):
            return False

    def generate_artist_chart_data(self, request, artist, time_filter):
        """Generate chart data for a specific artist using existing chart infrastructure."""
        import time
        start_time = time.time()

        try:
            self.logger.info(f"Starting chart data generation for artist {artist.name}", extra={
                'artist_id': artist.id, 'time_filter': str(time_filter)
            })

            period_display = self.get_period_display(request)
            granularity = self.get_granularity(request, time_filter)

            self.logger.info(f"Chart parameters determined", extra={
                'granularity': granularity, 'period_display': period_display,
                'elapsed_ms': int((time.time() - start_time) * 1000)
            })

            # Validate granularity
            valid_granularities = ['daily', 'monthly', 'yearly']
            if granularity not in valid_granularities:
                self.logger.warning(
                    f"Invalid granularity for artist chart: {granularity}",
                    extra={'granularity': granularity, 'artist_id': artist.id}
                )
                granularity = 'monthly'  # Default fallback

            # Get Django date truncation function for safe SQL generation
            trunc_function = self._get_date_trunc_function(granularity)

            # Build the query with artist filtering using optimized queryset
            # Add default time limit to prevent extremely slow queries
            from datetime import datetime, timedelta
            from django.utils import timezone

            scrobbles_qs = QueryOptimizer.get_optimized_scrobbles_queryset().filter(
                track__artist=artist
            ).only('id', 'timestamp')

            # Apply performance limits - but respect explicit "All Time" requests
            if not time_filter:
                period_param = request.query_params.get('period', 'all')
                if period_param != 'all':
                    # Only apply 2-year limit for non-explicit requests (e.g., missing period param)
                    two_years_ago = timezone.now() - timedelta(days=730)
                    scrobbles_qs = scrobbles_qs.filter(timestamp__gte=two_years_ago)
                    self.logger.info("Applied default 2-year limit for performance", extra={
                        'cutoff_date': two_years_ago.strftime('%Y-%m-%d')
                    })
                else:
                    # User explicitly requested "All Time" - show all historical data
                    self.logger.info("All Time period requested - showing complete historical data")

            # Apply time filtering
            if time_filter:
                if isinstance(time_filter, tuple):
                    # Custom date range: (from_date, to_date)
                    from_date, to_date = time_filter
                    if from_date:
                        scrobbles_qs = scrobbles_qs.filter(timestamp__gte=from_date)
                    if to_date:
                        scrobbles_qs = scrobbles_qs.filter(timestamp__lte=to_date)
                else:
                    # Period-based filtering: single datetime
                    scrobbles_qs = scrobbles_qs.filter(timestamp__gte=time_filter)

            # Aggregate by period using Django's safe date truncation functions
            self.logger.info("Starting database query for artist chart data", extra={
                'elapsed_ms': int((time.time() - start_time) * 1000)
            })

            from django.db.models import Count
            # Add performance limit - max 500 data points to prevent timeouts
            chart_query = scrobbles_qs.annotate(
                period=trunc_function('timestamp')
            ).values('period').annotate(
                scrobble_count=Count('id')
            ).order_by('period')

            # Apply limit and execute query
            chart_data = list(chart_query[:500])

            self.logger.info(f"Database query completed for artist chart", extra={
                'data_points': len(chart_data),
                'elapsed_ms': int((time.time() - start_time) * 1000)
            })

            # Limit data points to prevent performance issues (max 366 for daily)
            if len(chart_data) > 366:
                chart_data = chart_data[-366:]
                self.logger.info("Limited artist chart data to prevent performance issues", extra={
                    'original_count': len(chart_data) + 366,
                    'limited_count': 366
                })

            # Format for Chart.js with proper date ranges
            formatted_data = []
            for item in chart_data:
                period_obj = item['period']

                # Convert datetime object to string and generate date ranges
                if granularity == 'daily':
                    period_str = period_obj.strftime('%Y-%m-%d') if hasattr(period_obj, 'strftime') else str(period_obj)
                    start_date = end_date = period_str
                elif granularity == 'monthly':
                    period_str = period_obj.strftime('%Y-%m') if hasattr(period_obj, 'strftime') else str(period_obj)
                    year, month = period_str.split('-')
                    start_date = f"{year}-{month}-01"
                    # Get last day of month
                    import calendar
                    last_day = calendar.monthrange(int(year), int(month))[1]
                    end_date = f"{year}-{month}-{last_day:02d}"
                else:  # yearly
                    period_str = period_obj.strftime('%Y') if hasattr(period_obj, 'strftime') else str(period_obj)
                    start_date = f"{period_str}-01-01"
                    end_date = f"{period_str}-12-31"

                formatted_data.append({
                    'period': period_str,
                    'scrobble_count': item['scrobble_count'],
                    'start_date': start_date,
                    'end_date': end_date
                })

            return {
                'period': period_display,
                'granularity': granularity,
                'data': formatted_data,
                'total_scrobbles': sum(item['scrobble_count'] for item in formatted_data)
            }

        except Exception as e:
            self.logger.error(
                f"Error generating artist chart data",
                extra={'artist_id': artist.id, 'exception': str(e)},
                exc_info=True
            )
            # Return empty chart data on error
            return {
                'period': self.get_period_display(request),
                'granularity': 'monthly',
                'data': [],
                'total_scrobbles': 0
            }

    def generate_album_chart_data(self, request, album):
        """Generate chart data for a specific album using existing chart infrastructure."""
        try:
            period_display = self.get_period_display(request)
            granularity = self.get_granularity(request, None)  # No time filter for now

            # Validate granularity
            valid_granularities = ['daily', 'monthly', 'yearly']
            if granularity not in valid_granularities:
                self.logger.warning(
                    f"Invalid granularity for album chart: {granularity}",
                    extra={'granularity': granularity, 'album_id': album.id}
                )
                granularity = 'monthly'  # Default fallback

            # Get Django date truncation function for safe SQL generation
            trunc_function = self._get_date_trunc_function(granularity)

            # Build the query with album filtering using optimized queryset
            scrobbles_qs = QueryOptimizer.get_optimized_scrobbles_queryset().filter(
                track__album=album
            ).only('id', 'timestamp')

            # Aggregate by period using Django's safe date truncation functions
            from django.db.models import Count
            chart_data = list(scrobbles_qs.annotate(
                period=trunc_function('timestamp')
            ).values('period').annotate(
                scrobble_count=Count('id')
            ).order_by('period'))

            # Limit data points to prevent performance issues (max 366 for daily)
            if len(chart_data) > 366:
                chart_data = chart_data[-366:]

            # Format for Chart.js with proper date ranges
            formatted_data = []
            for item in chart_data:
                period_obj = item['period']

                # Convert datetime object to string and generate date ranges
                if granularity == 'daily':
                    period_str = period_obj.strftime('%Y-%m-%d') if hasattr(period_obj, 'strftime') else str(period_obj)
                    start_date = end_date = period_str
                elif granularity == 'monthly':
                    period_str = period_obj.strftime('%Y-%m') if hasattr(period_obj, 'strftime') else str(period_obj)
                    year, month = period_str.split('-')
                    start_date = f"{year}-{month}-01"
                    # Get last day of month
                    import calendar
                    last_day = calendar.monthrange(int(year), int(month))[1]
                    end_date = f"{year}-{month}-{last_day:02d}"
                else:  # yearly
                    period_str = period_obj.strftime('%Y') if hasattr(period_obj, 'strftime') else str(period_obj)
                    start_date = f"{period_str}-01-01"
                    end_date = f"{period_str}-12-31"

                formatted_data.append({
                    'period': period_str,
                    'scrobble_count': item['scrobble_count'],
                    'start_date': start_date,
                    'end_date': end_date
                })

            return {
                'period': period_display,
                'granularity': granularity,
                'data': formatted_data,
                'total_scrobbles': sum(item['scrobble_count'] for item in formatted_data)
            }

        except Exception as e:
            self.logger.error(
                f"Error generating album chart data",
                extra={'album_id': album.id, 'exception': str(e)},
                exc_info=True
            )
            # Return empty chart data on error
            return {
                'period': 'all',
                'granularity': 'monthly',
                'data': [],
                'total_scrobbles': 0
            }

    @action(detail=False)
    @cached_api_response(timeout=300, cache_backend='api_cache')
    @validate_recent_tracks_params()
    def recent_tracks(self, request):
        """
        Get recent listening activity.

        Story 9 compliant endpoint with default limit 10, supports ?limit=N (max 50).

        **Query Parameters:**
        - `limit`: Number of results (1-50, default: 10)

        **Error Responses:**
        - 400: Invalid limit parameter

        **Example Error:**
        ```json
        {
          "error": {
            "code": "INVALID_LIMIT",
            "message": "Invalid limit '100'. Must be between 1 and 50.",
            "details": {
              "parameter": "limit",
              "provided": "100",
              "min_value": 1,
              "max_value": 50
            }
          }
        }
        ```
        """
        # Use optimized queryset from QueryOptimizer
        scrobbles = QueryOptimizer.get_optimized_scrobbles_queryset()

        # Use validated limit from decorator
        limit = request.validated_params['limit']

        paginator = RecentTracksPagination()
        page = paginator.paginate_queryset(scrobbles, request)

        if page is not None:
            serializer = RecentTracksSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = RecentTracksSerializer(scrobbles, many=True)
        return Response(serializer.data)

    @action(detail=False)
    @cached_api_response(timeout=1800, cache_backend='api_cache')
    def top_artists(self, request):
        """Get top artists by play count with time filtering (Story 10 compliant)."""
        try:
            time_filter = self.get_time_filter(request)
            period_display = self.get_period_display(request)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise

        # Build filter conditions for custom date ranges or single date
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            filter_conditions = Q()

            if from_date:
                filter_conditions &= Q(tracks__scrobbles__timestamp__gte=from_date)
            if to_date:
                filter_conditions &= Q(tracks__scrobbles__timestamp__lte=to_date)
        else:
            filter_conditions = Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()

        # Optimize with select_related for foreign key lookups
        artists = Artist.objects.select_related().prefetch_related(
            'tracks', 'albums'
        ).annotate(
            scrobble_count=Count(
                'tracks__scrobbles',
                filter=filter_conditions,
                distinct=True
            ),
            track_count=Count('tracks', distinct=True),
            album_count=Count('albums', distinct=True),
            last_scrobbled=Max(
                'tracks__scrobbles__timestamp',
                filter=filter_conditions
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        # Calculate total scrobbles for period
        total_scrobbles = Scrobble.objects.filter(
            **self._build_scrobble_filter(time_filter)
        ).count()

        paginator = TopArtistsPagination()
        paginator._period = period_display
        paginator._total_scrobbles = total_scrobbles

        page = paginator.paginate_queryset(artists, request)

        if page is not None:
            serializer = ArtistListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback for non-paginated response (shouldn't happen with pagination)
        serializer = ArtistListSerializer(artists, many=True)
        return Response({
            'period': period_display,
            'results': serializer.data,
            'count': len(serializer.data),
            'total_scrobbles': total_scrobbles
        })

    def _build_scrobble_filter(self, time_filter):
        """Build filter dict for Scrobble queryset based on time_filter."""
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            filter_kwargs = {}

            if from_date:
                filter_kwargs['timestamp__gte'] = from_date
            if to_date:
                filter_kwargs['timestamp__lte'] = to_date

            return filter_kwargs
        elif time_filter:
            return {'timestamp__gte': time_filter}
        else:
            return {}

    @action(detail=False)
    @cached_api_response(timeout=1800, cache_backend='api_cache')
    def top_albums(self, request):
        """Get top albums by play count with time filtering (Story 11 compliant)."""
        try:
            time_filter = self.get_time_filter(request)
            period_display = self.get_period_display(request)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise

        # Build filter conditions for custom date ranges or single date
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            filter_conditions = Q()

            if from_date:
                filter_conditions &= Q(tracks__scrobbles__timestamp__gte=from_date)
            if to_date:
                filter_conditions &= Q(tracks__scrobbles__timestamp__lte=to_date)
        else:
            filter_conditions = Q(tracks__scrobbles__timestamp__gte=time_filter) if time_filter else Q()

        albums = Album.objects.select_related('artist').annotate(
            scrobble_count=Count(
                'tracks__scrobbles',
                filter=filter_conditions,
                distinct=True
            ),
            track_count=Count('tracks', distinct=True),
            last_scrobbled=Max(
                'tracks__scrobbles__timestamp',
                filter=filter_conditions
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        # Calculate total scrobbles for period
        total_scrobbles = Scrobble.objects.filter(
            **self._build_scrobble_filter(time_filter)
        ).count()

        paginator = TopAlbumsPagination()
        paginator._period = period_display
        paginator._total_scrobbles = total_scrobbles

        page = paginator.paginate_queryset(albums, request)

        if page is not None:
            serializer = TopAlbumsSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback for non-paginated response (shouldn't happen with pagination)
        serializer = TopAlbumsSerializer(albums, many=True)
        return Response({
            'period': period_display,
            'results': serializer.data,
            'count': len(serializer.data),
            'total_scrobbles': total_scrobbles
        })

    @action(detail=False)
    @cached_api_response(timeout=1800, cache_backend='api_cache')
    def top_tracks(self, request):
        """Get top tracks by play count with time filtering (Story 12 compliant)."""
        try:
            time_filter = self.get_time_filter(request)
            period_display = self.get_period_display(request)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise

        # Build filter conditions for custom date ranges or single date
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            filter_conditions = Q()

            if from_date:
                filter_conditions &= Q(scrobbles__timestamp__gte=from_date)
            if to_date:
                filter_conditions &= Q(scrobbles__timestamp__lte=to_date)
        else:
            filter_conditions = Q(scrobbles__timestamp__gte=time_filter) if time_filter else Q()

        tracks = Track.objects.select_related('artist', 'album').annotate(
            scrobble_count=Count(
                'scrobbles',
                filter=filter_conditions
            ),
            last_scrobbled=Max(
                'scrobbles__timestamp',
                filter=filter_conditions
            )
        ).filter(scrobble_count__gt=0).order_by('-scrobble_count')

        # Calculate total scrobbles for period
        total_scrobbles = Scrobble.objects.filter(
            **self._build_scrobble_filter(time_filter)
        ).count()

        paginator = TopTracksPagination()
        paginator._period = period_display
        paginator._total_scrobbles = total_scrobbles

        page = paginator.paginate_queryset(tracks, request)

        if page is not None:
            serializer = TopTracksSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Fallback for non-paginated response (shouldn't happen with pagination)
        serializer = TopTracksSerializer(tracks, many=True)
        return Response({
            'period': period_display,
            'results': serializer.data,
            'count': len(serializer.data),
            'total_scrobbles': total_scrobbles
        })

    @action(detail=False, url_path='scrobbles/chart')
    @cached_api_response(timeout=3600, cache_backend='api_cache')
    def chart_data(self, request):
        """Get scrobbles over time chart data (Story 13 compliant)."""
        try:
            time_filter = self.get_time_filter(request)
            period_display = self.get_period_display(request)
            granularity = self.get_granularity(request, time_filter)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise

        # Validate granularity
        if request.query_params.get('granularity') and request.query_params.get('granularity') not in ['daily', 'monthly', 'yearly']:
            raise APIError(
                "Invalid granularity. Use: daily, monthly, yearly",
                status_code=400,
                error_code="INVALID_GRANULARITY"
            )

        # Build base queryset with time filtering using optimized queryset
        base_queryset = QueryOptimizer.get_optimized_scrobbles_queryset().only(
            'id', 'timestamp'
        )

        # Apply time filtering
        if isinstance(time_filter, tuple):
            from_date, to_date = time_filter
            if from_date:
                base_queryset = base_queryset.filter(timestamp__gte=from_date)
            if to_date:
                base_queryset = base_queryset.filter(timestamp__lte=to_date)
        elif time_filter:
            base_queryset = base_queryset.filter(timestamp__gte=time_filter)

        # Get date truncation format
        date_format = self._get_date_trunc_format(granularity)

        # Perform database aggregation using SQLite's strftime
        from django.db.models import Count
        chart_data = base_queryset.extra(
            select={
                'period': f"strftime('{date_format}', timestamp)"
            }
        ).values('period').annotate(
            scrobble_count=Count('id')
        ).order_by('period')

        # Convert to list and limit data points (max 366 for daily leap year)
        chart_results = list(chart_data)
        if len(chart_results) > 366:
            # If too many points, sample evenly
            step = len(chart_results) // 366 + 1
            chart_results = chart_results[::step]

        # Fill gaps and build response data
        response_data = []
        for item in chart_results:
            period_value = item['period']
            scrobble_count = item['scrobble_count']

            if period_value:  # Skip null periods
                start_date, end_date = self._build_period_info(period_value, granularity)
                response_data.append({
                    'period': period_value,
                    'scrobble_count': scrobble_count,
                    'start_date': start_date,
                    'end_date': end_date
                })

        # Calculate total scrobbles for the period
        total_scrobbles = base_queryset.count()

        # Serialize the data
        serializer = ScrobblesChartSerializer(response_data, many=True)

        return Response({
            'period': period_display,
            'granularity': granularity,
            'data': serializer.data,
            'total_scrobbles': total_scrobbles
        })

    @action(detail=True)
    @cached_api_response(timeout=1800, cache_backend='api_cache')
    def artists(self, request, pk=None):
        """Get artist detail with statistics (Story 14 compliant)."""
        try:
            # Support both ID and MBID lookup
            if self.is_valid_uuid(pk):
                # MBID lookup
                # Lightweight query - don't prefetch all scrobbles for performance
                artist = get_object_or_404(
                    Artist.objects.select_related().only('id', 'name', 'mbid', 'url'),
                    mbid=pk
                )
                lookup_type = 'mbid'
            else:
                # ID lookup
                # Lightweight query - don't prefetch all scrobbles for performance
                artist = get_object_or_404(
                    Artist.objects.select_related().only('id', 'name', 'mbid', 'url'),
                    pk=pk
                )
                lookup_type = 'id'

            self.logger.info(
                f"Artist detail requested",
                extra={
                    'artist_lookup': pk,
                    'lookup_type': lookup_type,
                    'artist_name': artist.name
                }
            )

            # Get time filtering parameters
            time_filter = self.get_time_filter(request)
            period_display = self.get_period_display(request)

            # Get limit parameter for top lists
            limit = min(int(request.query_params.get('limit', 10)), 50)

            # Generate chart data for this artist
            chart_data = self.generate_artist_chart_data(request, artist, time_filter)

            # Create serializer with Story 14 compliance
            serializer = ArtistStory14Serializer(
                artist,
                time_filter=time_filter,
                period_display=period_display,
                limit=limit,
                context={'chart_data': chart_data}
            )

            return Response(serializer.data)

        except Http404:
            self.logger.warning(
                f"Artist not found",
                extra={'artist_lookup': pk, 'lookup_type': lookup_type if 'lookup_type' in locals() else 'unknown'}
            )
            raise APIError(f"Artist with {'MBID' if self.is_valid_uuid(pk) else 'ID'} {pk} not found", status_code=404)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise
        except Exception as e:
            self.logger.error(
                f"Error retrieving artist detail",
                extra={'artist_lookup': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving artist data", status_code=500)

    @action(detail=True)
    @cached_api_response(timeout=1800, cache_backend='api_cache')
    def albums(self, request, pk=None):
        """Get album detail with track listings (Story 15 compliant)."""
        try:
            # Support both ID and MBID lookup
            if self.is_valid_uuid(pk):
                # MBID lookup
                album = get_object_or_404(
                    Album.objects.select_related('artist').prefetch_related('tracks'),
                    mbid=pk
                )
                lookup_type = 'mbid'
            else:
                # ID lookup
                album = get_object_or_404(
                    Album.objects.select_related('artist').prefetch_related('tracks'),
                    pk=pk
                )
                lookup_type = 'id'

            self.logger.info(
                f"Album detail requested",
                extra={
                    'album_lookup': pk,
                    'lookup_type': lookup_type,
                    'album_name': album.name,
                    'artist_name': album.artist.name
                }
            )

            # Get track ordering parameter (album_order or scrobble_count)
            track_ordering = request.query_params.get('ordering', 'scrobble_count')
            if track_ordering not in ['album_order', 'scrobble_count']:
                track_ordering = 'scrobble_count'

            # Generate chart data for this album
            chart_data = self.generate_album_chart_data(request, album)

            # Create serializer with Story 15 compliance
            serializer = AlbumStory15Serializer(
                album,
                track_ordering=track_ordering,
                context={'chart_data': chart_data}
            )

            return Response(serializer.data)

        except Http404:
            self.logger.warning(
                f"Album not found",
                extra={'album_lookup': pk, 'lookup_type': lookup_type if 'lookup_type' in locals() else 'unknown'}
            )
            raise APIError(f"Album with {'MBID' if self.is_valid_uuid(pk) else 'ID'} {pk} not found", status_code=404)
        except APIError:
            # Re-raise APIError to return proper HTTP status codes
            raise
        except Exception as e:
            self.logger.error(
                f"Error retrieving album detail",
                extra={'album_lookup': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving album data", status_code=500)

    @action(detail=True)
    @cached_api_response(timeout=900, cache_backend='api_cache')
    def tracks(self, request, pk=None):
        """Get track detail with scrobble history."""
        try:
            track = get_object_or_404(
                Track.objects.select_related('artist', 'album').prefetch_related('scrobbles'),
                pk=pk
            )
            self.logger.info(
                f"Track detail requested",
                extra={
                    'track_id': pk,
                    'track_name': track.name,
                    'artist_name': track.artist.name,
                    'album_name': track.album.name if track.album else None
                }
            )
            serializer = TrackDetailSerializer(track)
            return Response(serializer.data)
        except Http404:
            self.logger.warning(f"Track not found", extra={'track_id': pk})
            raise APIError(f"Track with ID {pk} not found", status_code=404)
        except Exception as e:
            self.logger.error(
                f"Error retrieving track detail",
                extra={'track_id': pk, 'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving track data", status_code=500)

    @action(detail=False)
    @cached_api_response(timeout=1800, cache_backend='api_cache', use_data_version=True)
    def summary(self, request):
        """
        Get overall listening statistics summary (Story 16 compliant).
        Returns totals, date range, top all-time items, and listening averages.

        **Rate Limiting:** 100 requests per hour per user

        **Error Responses:**
        - 429: Rate limit exceeded
        - 500: Internal server error

        **Example Rate Limit Error:**
        ```json
        {
          "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "Rate limit exceeded for statistics summary endpoint",
            "details": {
              "resource": "stats_summary",
              "retry_after": 3600
            }
          }
        }
        ```
        """
        try:
            # Generate cache key based on latest scrobble timestamp for smart invalidation
            latest_scrobble = Scrobble.objects.order_by('-timestamp').first()
            if not latest_scrobble:
                # Handle empty dataset case
                empty_summary_data = {
                    'totals': {
                        'scrobbles': 0,
                        'artists': 0,
                        'albums': 0,
                        'tracks': 0
                    },
                    'date_range': {
                        'first_scrobble': None,
                        'last_scrobble': None,
                        'total_days': 0
                    },
                    'top_all_time': {
                        'artist': None,
                        'album': None,
                        'track': None
                    },
                    'averages': {
                        'per_day': 0,
                        'per_month': 0,
                        'per_year': 0
                    }
                }
                serializer = StatisticsSummarySerializer(empty_summary_data)
                return Response(serializer.data)

            # Create cache key based on latest scrobble timestamp
            latest_timestamp = latest_scrobble.timestamp.isoformat()
            cache_key = f"stats_summary_{hash(latest_timestamp)}"

            # Try to get cached data
            cached_data = cache.get(cache_key)
            if cached_data:
                self.logger.info(
                    "Statistics summary served from cache",
                    extra={'cache_key': cache_key}
                )
                serializer = StatisticsSummarySerializer(cached_data)
                return Response(serializer.data)

            self.logger.info(
                "Calculating statistics summary (cache miss)",
                extra={'cache_key': cache_key}
            )

            # Calculate summary statistics
            summary_data = self._calculate_summary_statistics()

            # Cache the results for 15 minutes (900 seconds)
            cache.set(cache_key, summary_data, 900)

            serializer = StatisticsSummarySerializer(summary_data)
            return Response(serializer.data)

        except Exception as e:
            self.logger.error(
                "Error generating statistics summary",
                extra={'exception': str(e)},
                exc_info=True
            )
            raise APIError("Error retrieving statistics summary", status_code=500)

    @cache_expensive_computation(timeout=3600, invalidate_on_new_data=True)
    def _calculate_summary_statistics(self):
        """Calculate comprehensive summary statistics for Story 16 compliance."""
        # Basic totals using efficient database aggregations
        total_scrobbles = Scrobble.objects.count()
        unique_artists = Artist.objects.filter(tracks__scrobbles__isnull=False).distinct().count()
        unique_albums = Album.objects.filter(tracks__scrobbles__isnull=False).distinct().count()
        unique_tracks = Track.objects.filter(scrobbles__isnull=False).distinct().count()

        # Date range calculation
        date_range_data = Scrobble.objects.aggregate(
            first_scrobble=Min('timestamp'),
            last_scrobble=Max('timestamp')
        )

        first_scrobble = date_range_data['first_scrobble']
        last_scrobble = date_range_data['last_scrobble']

        # Calculate total days
        total_days = 0
        if first_scrobble and last_scrobble:
            total_days = (last_scrobble.date() - first_scrobble.date()).days + 1

        # Top all-time items (most played)
        top_artist = (
            Artist.objects
            .annotate(play_count=Count('tracks__scrobbles'))
            .order_by('-play_count')
            .first()
        )

        top_album = (
            Album.objects
            .annotate(play_count=Count('tracks__scrobbles'))
            .order_by('-play_count')
            .first()
        )

        top_track = (
            Track.objects
            .annotate(play_count=Count('scrobbles'))
            .order_by('-play_count')
            .first()
        )

        # Calculate averages (handle division by zero)
        per_day_avg = round(total_scrobbles / total_days, 1) if total_days > 0 else 0
        per_month_avg = round(total_scrobbles / (total_days / 30.44), 1) if total_days > 0 else 0
        per_year_avg = round(total_scrobbles / (total_days / 365.25), 1) if total_days > 0 else 0

        return {
            'totals': {
                'scrobbles': total_scrobbles,
                'artists': unique_artists,
                'albums': unique_albums,
                'tracks': unique_tracks
            },
            'date_range': {
                'first_scrobble': first_scrobble.isoformat() + 'Z' if first_scrobble else None,
                'last_scrobble': last_scrobble.isoformat() + 'Z' if last_scrobble else None,
                'total_days': total_days
            },
            'top_all_time': {
                'artist': top_artist.name if top_artist else None,
                'album': top_album.name if top_album else None,
                'track': top_track.name if top_track else None
            },
            'averages': {
                'per_day': per_day_avg,
                'per_month': per_month_avg,
                'per_year': per_year_avg
            }
        }